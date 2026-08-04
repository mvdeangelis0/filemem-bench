from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from amb.continuous.daemon import run_daemon, should_stop
from amb.continuous.deferred import list_deferred
from amb.continuous.inbox import inject as continuous_inject
from amb.continuous.loop import run_episode
from amb.continuous.memory_browser import ask_over_run, build_map, inventory_tree
from amb.continuous.menu import build_slash_line, pick_command, prompt_args
from amb.continuous.score import compare_episodes, score_run
from amb.continuous.web_trail import list_trail, read_cursor


HELP_TEXT = """
ambc — continuous sandboxed lab agent

Slash commands (interactive):
  /menu                         Arrow-key command picker (also: bare Enter)
  /help                         Show this help
  /status                       Print STATUS.md for the active run
  /inbox                        Show pending INBOX.md
  /deferred [n]                 Show last n deferred tasks (default 20)
  /trail [n]                    Show web trail breadcrumbs (default 15)
  /tree                         List files stored in the active run
  /map                          Write/print OPERATOR_MAP.md (roles + graph + trail)
  /ask <question>               LLM Q&A over the run files (uses /settings llm)
  /inject <text>                Queue for next /run (or write to active run)
  /curriculum                   Queue the standard crystal temp-sweep inject
  /tail [n]                     Show last n action lines (default 15)
  /graph [k]                    Show top-k weighted pathways (default 8)
  /score [--compare <dir>]      Score active run (optionally vs earlier)
  /report                       Print REPORT.md
  /open <relpath>               Print a file under the active run
  /use <run_dir>                Set active run directory
  /ls                           List runs under out dir
  /set <key> <value>            Set session defaults (see /settings)
  /settings                     Show session defaults
  /run [flags]                  Start an episode (uses /settings)
  /daemon [flags]               Run episodes until STOP / max-episodes
  /stop                         Write STOP in out dir (halts daemon)
  /pull                         git pull (repo root)
  /reinstall                    pip install -e ".[dev]" (then /quit + restart ambc)
  /update                       /pull then /reinstall
  /quit  |  /exit               Leave the shell

One-shot (non-interactive):
  ambc                         Enter interactive shell
  ambc help
  ambc run --llm ollama --model qwen2.5:7b-instruct-q4_K_M --max-steps 30
  ambc inject --run <dir> "Focus on humidity"
  ambc score --run <dir>
  ambc status --run <dir>

/run flags: --world --llm --model --max-steps --seed --out --run-id
            --ollama-host --web-allowlist --num-ctx --num-predict --keep-alive
            -v --observer

Settings persist to .ambc_settings.json in the current directory (override with AMBC_SETTINGS).
/set and /use auto-save; /settings shows the file path.
""".strip()


DEFAULT_MODEL = "qwen2.5:7b-instruct-q4_K_M"
SETTINGS_FILENAME = ".ambc_settings.json"
DEFAULT_CURRICULUM = (
    "Run a temperature sweep from 20 to 45 at humidity 50. "
    "After each lab_act, note growth. Do not repeat lab_sense without a new experiment. "
    "Write your best T/H hypothesis to memory/lessons.md when you have evidence."
)

_PERSIST_KEYS = (
    "world",
    "llm",
    "model",
    "max_steps",
    "seed",
    "ollama_host",
    "web_allowlist",
    "verbose",
    "observer",
    "idle_seconds",
    "max_episodes",
    "num_ctx",
    "num_predict",
    "keep_alive",
    "next_inbox",
)


def build_llm(
    *,
    llm_mode: str,
    model: str,
    ollama_host: str | None,
    verbose: bool,
    num_ctx: int | None = None,
    num_predict: int | None = None,
    keep_alive: str | int | None = None,
) -> tuple[Any, str]:
    model_id = model
    if llm_mode == "mock":
        from amb.agents.llm import MockLLM

        return MockLLM([]), (model_id if model_id != "mock" else "mock")
    if llm_mode == "ollama":
        from amb.agents.llm import OllamaLLM

        host = ollama_host or os.environ.get("OLLAMA_HOST") or "http://127.0.0.1:11434"
        if model_id == "mock":
            raise ValueError("--model required for --llm ollama (e.g. deepseek-r1:7b)")
        return (
            OllamaLLM(
                model_id,
                base_url=host,
                verbose=verbose,
                num_ctx=num_ctx,
                num_predict=num_predict,
                keep_alive=keep_alive,
            ),
            model_id,
        )
    raise ValueError(f"unsupported llm {llm_mode}")


def parse_allowlist(raw: str) -> list[str]:
    return [h.strip() for h in raw.split(",") if h.strip()]


def settings_path() -> Path:
    env = os.environ.get("AMBC_SETTINGS")
    if env:
        return Path(env).expanduser()
    return Path.cwd() / SETTINGS_FILENAME


@dataclass
class Session:
    out_dir: Path = field(default_factory=lambda: Path("continuous_runs"))
    run_dir: Path | None = None
    world: str = "crystal"
    llm: str = "ollama"
    model: str = DEFAULT_MODEL
    max_steps: int = 30
    seed: int = 0
    ollama_host: str | None = None
    web_allowlist: str = ""
    verbose: bool = True
    observer: bool = False
    idle_seconds: float = 1.0
    max_episodes: int = 1
    # Ollama speed knobs (RTX 3070 defaults — override with /set)
    num_ctx: int | None = 4096
    num_predict: int | None = 512
    keep_alive: str | None = "30m"
    # Queued for the next /run → written into that episode's INBOX.md at start
    next_inbox: str = ""

    def require_run(self) -> Path:
        if self.run_dir is None or not self.run_dir.exists():
            raise ValueError("no active run — use /run or /use <run_dir>")
        return self.run_dir


def session_snapshot(session: Session) -> dict[str, Any]:
    data: dict[str, Any] = {
        "out": str(session.out_dir),
        "run": str(session.run_dir) if session.run_dir else None,
    }
    for key in _PERSIST_KEYS:
        data[key] = getattr(session, key)
    return data


def apply_snapshot(session: Session, data: dict[str, Any]) -> None:
    if "out" in data and data["out"]:
        session.out_dir = Path(str(data["out"]))
    run = data.get("run")
    if run:
        path = Path(str(run))
        session.run_dir = path if path.exists() else None
    elif "run" in data and data["run"] is None:
        session.run_dir = None
    for key in _PERSIST_KEYS:
        if key not in data:
            continue
        setattr(session, key, data[key])


def save_session(session: Session, *, path: Path | None = None) -> Path:
    dest = path or settings_path()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(session_snapshot(session), indent=2) + "\n", encoding="utf-8")
    return dest


def load_session(session: Session | None = None, *, path: Path | None = None) -> Session:
    """Load persisted settings over defaults (Qwen + Ollama)."""
    sess = session or Session()
    src = path or settings_path()
    if not src.is_file():
        return sess
    try:
        data = json.loads(src.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"warning: could not load {src}: {e}", file=sys.stderr)
        return sess
    if not isinstance(data, dict):
        return sess
    apply_snapshot(sess, data)
    return sess


def _print_file(path: Path) -> None:
    if not path.exists():
        print(f"(missing) {path}")
        return
    text = path.read_text(encoding="utf-8")
    print(text, end="" if text.endswith("\n") else "\n")


def cmd_help(_session: Session, _args: list[str]) -> None:
    print(HELP_TEXT)


def cmd_settings(session: Session, _args: list[str]) -> None:
    snap = session_snapshot(session)
    snap["settings_file"] = str(settings_path())
    pending = (session.next_inbox or "").strip()
    snap["next_inbox_preview"] = (pending[:120] + "…") if len(pending) > 120 else pending
    print(json.dumps(snap, indent=2))


def _parse_optional_int(v: str) -> int | None:
    s = v.strip().lower()
    if s in {"", "none", "null", "default", "-"}:
        return None
    return int(v)


def _parse_keep_alive(v: str) -> str | None:
    s = v.strip()
    if s.lower() in {"", "none", "null", "default", "-"}:
        return None
    return s


def cmd_set(session: Session, args: list[str]) -> None:
    if len(args) < 2:
        raise ValueError("usage: /set <key> <value>")
    key, value = args[0], " ".join(args[1:])
    mapping: dict[str, Callable[[str], None]] = {
        "out": lambda v: setattr(session, "out_dir", Path(v)),
        "world": lambda v: setattr(session, "world", v),
        "llm": lambda v: setattr(session, "llm", v),
        "model": lambda v: setattr(session, "model", v),
        "max_steps": lambda v: setattr(session, "max_steps", int(v)),
        "seed": lambda v: setattr(session, "seed", int(v)),
        "ollama_host": lambda v: setattr(session, "ollama_host", v),
        "web_allowlist": lambda v: setattr(session, "web_allowlist", v),
        "verbose": lambda v: setattr(session, "verbose", v.lower() in {"1", "true", "yes", "on"}),
        "observer": lambda v: setattr(session, "observer", v.lower() in {"1", "true", "yes", "on"}),
        "idle_seconds": lambda v: setattr(session, "idle_seconds", float(v)),
        "max_episodes": lambda v: setattr(session, "max_episodes", int(v)),
        "num_ctx": lambda v: setattr(session, "num_ctx", _parse_optional_int(v)),
        "num_predict": lambda v: setattr(session, "num_predict", _parse_optional_int(v)),
        "keep_alive": lambda v: setattr(session, "keep_alive", _parse_keep_alive(v)),
    }
    if key not in mapping:
        raise ValueError(f"unknown key {key!r}; see /settings")
    mapping[key](value)
    dest = save_session(session)
    print(f"set {key}={value}  (saved {dest})")


def cmd_use(session: Session, args: list[str]) -> None:
    if not args:
        raise ValueError("usage: /use <run_dir>")
    path = Path(args[0])
    if not path.exists():
        raise ValueError(f"not found: {path}")
    session.run_dir = path
    dest = save_session(session)
    print(f"active run: {path}  (saved {dest})")


def cmd_ls(session: Session, _args: list[str]) -> None:
    root = session.out_dir
    if not root.exists():
        print(f"(no out dir yet) {root}")
        return
    runs = sorted([p for p in root.iterdir() if p.is_dir()], key=lambda p: p.name)
    if not runs:
        print("(empty)")
        return
    for p in runs:
        mark = " *" if session.run_dir and p.resolve() == session.run_dir.resolve() else ""
        print(f"{p}{mark}")


def cmd_status(session: Session, _args: list[str]) -> None:
    run = session.require_run()
    _print_file(run / "STATUS.md")


def cmd_inbox(session: Session, _args: list[str]) -> None:
    run = session.require_run()
    text = (run / "INBOX.md").read_text(encoding="utf-8") if (run / "INBOX.md").exists() else ""
    print(text if text.strip() else "(empty inbox)")


def cmd_deferred(session: Session, args: list[str]) -> None:
    run = session.require_run()
    n = int(args[0]) if args else 20
    rows = list_deferred(run, limit=n)
    if not rows:
        print("(no deferred tasks)")
        return
    for row in rows:
        print(
            f"[{row.get('need')}] {row.get('task')} "
            f"— {row.get('reason')} ({row.get('source')})"
        )


def cmd_trail(session: Session, args: list[str]) -> None:
    run = session.require_run()
    cursor = read_cursor(run)
    if cursor:
        print(f"left off: {cursor.get('left_off')}")
        print(f"updated:  {cursor.get('updated_at')}")
    n = int(args[0]) if args else 15
    rows = list_trail(run, limit=n)
    if not rows:
        print("(no web trail yet)")
        return
    for row in rows:
        when = row.get("ts", "")
        action = row.get("action")
        target = row.get("url") or row.get("query") or ""
        title = row.get("title") or ""
        ok = "ok" if row.get("ok") else "err"
        print(f"{when}  {action}/{ok}  {target}  {title}")


def cmd_tree(session: Session, _args: list[str]) -> None:
    run = session.require_run()
    lines = inventory_tree(run)
    if not lines:
        print("(empty run)")
        return
    print(f"run: {run}")
    for ln in lines:
        print(ln)


def cmd_map(session: Session, _args: list[str]) -> None:
    run = session.require_run()
    text = build_map(run)
    print(text)
    print(f"(also wrote {run / 'OPERATOR_MAP.md'})")


def cmd_ask(session: Session, args: list[str]) -> None:
    if not args:
        raise ValueError("usage: /ask <question>")
    run = session.require_run()
    question = " ".join(args)
    result = ask_over_run(
        run,
        question,
        llm_mode=session.llm,
        model=session.model,
        ollama_host=session.ollama_host,
    )
    print(result["answer"])
    if result.get("sources"):
        print("\nSources:")
        for s in result["sources"]:
            print(f"- {s['path']} (score={s['score']})")


def cmd_inject(session: Session, args: list[str]) -> None:
    if not args:
        raise ValueError(
            "usage: /inject <text>  (queues for next /run; "
            "add --now to write into the active run only)"
        )
    now = False
    parts = list(args)
    if parts and parts[0] in {"--now", "-n"}:
        now = True
        parts = parts[1:]
    if not parts:
        raise ValueError("usage: /inject [--now] <text>")
    text = " ".join(parts).strip()
    if now:
        run = session.require_run()
        continuous_inject(run, text)
        print(f"injected → {run / 'INBOX.md'}")
        return
    session.next_inbox = text
    dest = save_session(session)
    print(f"queued for next /run ({len(text)} chars)  (saved {dest})")
    if session.run_dir:
        print("(tip: /inject --now … writes into the active run instead)")


def cmd_curriculum(session: Session, _args: list[str]) -> None:
    """Queue the standard crystal bakeoff inject for the next /run."""
    session.next_inbox = DEFAULT_CURRICULUM
    dest = save_session(session)
    print(f"queued curriculum for next /run  (saved {dest})")
    print(DEFAULT_CURRICULUM)


def cmd_tail(session: Session, args: list[str]) -> None:
    run = session.require_run()
    n = int(args[0]) if args else 15
    path = run / "actions.jsonl"
    if not path.exists():
        print("(no actions yet)")
        return
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    for ln in lines[-n:]:
        print(ln)


def cmd_graph(session: Session, args: list[str]) -> None:
    run = session.require_run()
    k = int(args[0]) if args else 8
    path = run / "memory" / "graph.json"
    if not path.exists():
        print("(no graph)")
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    edges = [
        {"edge": key, **val}
        for key, val in (data.get("edges") or {}).items()
    ]
    edges.sort(key=lambda e: float(e.get("weight", 0)), reverse=True)
    for e in edges[:k]:
        print(f"{e['weight']:.2f}\t{e['edge']}\tcount={e.get('count', 0)}")
    if not edges:
        print("(no edges yet)")


def cmd_score(session: Session, args: list[str]) -> None:
    run = session.require_run()
    compare = None
    if args and args[0] == "--compare":
        if len(args) < 2:
            raise ValueError("usage: /score --compare <earlier_run>")
        compare = Path(args[1])
    if compare is not None:
        print(json.dumps(compare_episodes(compare, run), indent=2))
    else:
        print(json.dumps(score_run(run).get("summary"), indent=2))


def cmd_report(session: Session, _args: list[str]) -> None:
    run = session.require_run()
    _print_file(run / "REPORT.md")


def cmd_open(session: Session, args: list[str]) -> None:
    if not args:
        raise ValueError("usage: /open <relpath>")
    run = session.require_run()
    rel = args[0].replace("\\", "/").lstrip("/")
    path = (run / rel).resolve()
    try:
        path.relative_to(run.resolve())
    except ValueError as e:
        raise ValueError("path escapes run dir") from e
    _print_file(path)


def _apply_run_flags(session: Session, args: list[str]) -> None:
    """Mutate session from --flag style tokens for /run and /daemon."""
    i = 0
    while i < len(args):
        tok = args[i]
        if tok in {"-v", "--verbose"}:
            session.verbose = True
            i += 1
            continue
        if tok == "--observer":
            session.observer = True
            i += 1
            continue
        if tok == "--curriculum":
            session.next_inbox = DEFAULT_CURRICULUM
            i += 1
            continue
        if tok == "--inject":
            if i + 1 >= len(args):
                raise ValueError("--inject needs text")
            session.next_inbox = args[i + 1]
            i += 2
            continue
        if not tok.startswith("--") or i + 1 >= len(args):
            raise ValueError(f"bad flag near {tok!r}")
        key = tok[2:].replace("-", "_")
        val = args[i + 1]
        if key == "out":
            session.out_dir = Path(val)
        elif key == "run_id":
            # stored temporarily via setattr for run
            setattr(session, "_run_id", val)
        elif key in {
            "world",
            "llm",
            "model",
            "ollama_host",
            "web_allowlist",
        }:
            setattr(session, key if key != "ollama_host" else "ollama_host", val)
        elif key in {"max_steps", "seed", "max_episodes", "num_ctx", "num_predict"}:
            if key in {"num_ctx", "num_predict"}:
                setattr(session, key, _parse_optional_int(val))
            else:
                setattr(session, key, int(val))
        elif key == "idle_seconds":
            session.idle_seconds = float(val)
        elif key == "keep_alive":
            session.keep_alive = _parse_keep_alive(val)
        else:
            raise ValueError(f"unknown flag {tok}")
        i += 2


def cmd_run(session: Session, args: list[str]) -> None:
    if args:
        _apply_run_flags(session, args)
    if session.observer:
        print("note: --observer is a stub; STATUS remains structured-only", file=sys.stderr)
    verbose = session.verbose or session.llm == "ollama"
    llm, model_id = build_llm(
        llm_mode=session.llm,
        model=session.model,
        ollama_host=session.ollama_host,
        verbose=verbose,
        num_ctx=session.num_ctx,
        num_predict=session.num_predict,
        keep_alive=session.keep_alive,
    )
    run_id = getattr(session, "_run_id", None)
    inbox = (session.next_inbox or "").strip()
    run_dir = run_episode(
        session.out_dir,
        world=session.world,
        llm=llm,
        max_steps=session.max_steps,
        seed=session.seed,
        model_id=model_id,
        run_id=run_id,
        verbose=verbose,
        web_allowlist=parse_allowlist(session.web_allowlist),
        initial_inbox=inbox or None,
    )
    session.run_dir = run_dir
    if hasattr(session, "_run_id"):
        delattr(session, "_run_id")
    if inbox:
        session.next_inbox = ""
    save_session(session)
    print(run_dir)


def cmd_daemon(session: Session, args: list[str]) -> None:
    if args:
        _apply_run_flags(session, args)
    if session.observer:
        print("note: --observer is a stub; STATUS remains structured-only", file=sys.stderr)
    verbose = session.verbose or session.llm == "ollama"
    llm, model_id = build_llm(
        llm_mode=session.llm,
        model=session.model,
        ollama_host=session.ollama_host,
        verbose=verbose,
        num_ctx=session.num_ctx,
        num_predict=session.num_predict,
        keep_alive=session.keep_alive,
    )
    runs = run_daemon(
        run_episode_fn=run_episode,
        out_dir=session.out_dir,
        world=session.world,
        llm=llm,
        max_steps=session.max_steps,
        seed=session.seed,
        model_id=model_id,
        idle_seconds=session.idle_seconds,
        max_episodes=session.max_episodes,
        web_allowlist=parse_allowlist(session.web_allowlist),
        verbose=verbose,
    )
    if runs:
        session.run_dir = runs[-1]
        save_session(session)
    for r in runs:
        print(r)


def _repo_root() -> Path:
    """Walk up from cwd for a checkout that has pyproject.toml."""
    cur = Path.cwd().resolve()
    for candidate in [cur, *cur.parents]:
        if (candidate / "pyproject.toml").is_file():
            return candidate
    return cur


def _run_shell(argv: list[str], *, cwd: Path) -> int:
    print(f"$ {' '.join(argv)}  (cwd={cwd})")
    proc = subprocess.run(argv, cwd=str(cwd), check=False)
    return int(proc.returncode)


def cmd_pull(_session: Session, _args: list[str]) -> None:
    root = _repo_root()
    code = _run_shell(["git", "pull"], cwd=root)
    if code != 0:
        raise RuntimeError(f"git pull failed with exit {code}")
    print("pulled ok — run /reinstall if Python/package files changed, then /quit and restart ambc")


def cmd_reinstall(_session: Session, _args: list[str]) -> None:
    root = _repo_root()
    code = _run_shell(
        [sys.executable, "-m", "pip", "install", "-e", ".[dev]"],
        cwd=root,
    )
    if code != 0:
        raise RuntimeError(f"pip install failed with exit {code}")
    print(
        "reinstall ok — this ambc process still has old code in memory; "
        "/quit and run ambc again to load the new package"
    )


def cmd_update(session: Session, args: list[str]) -> None:
    cmd_pull(session, args)
    cmd_reinstall(session, args)


class _ExitRepl(Exception):
    """Raised when the menu (or a nested dispatch) requests leaving the shell."""


def cmd_menu(session: Session, _args: list[str]) -> None:
    """Arrow-key picker; builds a slash line and dispatches it."""
    name = pick_command()
    if name is None:
        print("(menu cancelled — try /help)")
        return
    if name in {"run", "daemon"}:
        print(
            f"using /settings: llm={session.llm} model={session.model} "
            f"max_steps={session.max_steps} world={session.world}"
        )
    args_text = prompt_args(name)
    if args_text is None:
        print("(cancelled)")
        return
    if name in {"inject", "ask", "open", "use", "set"} and not args_text.strip():
        print(f"error: /{name} needs an argument", file=sys.stderr)
        return
    # curriculum has no args
    line = build_slash_line(name, args_text)
    if not dispatch_line(session, line):
        raise _ExitRepl()


def cmd_stop(session: Session, _args: list[str]) -> None:
    session.out_dir.mkdir(parents=True, exist_ok=True)
    path = session.out_dir / "STOP"
    path.write_text("1\n", encoding="utf-8")
    print(f"wrote {path}")
    if session.run_dir and not should_stop(session.run_dir):
        (session.run_dir / "STOP").write_text("1\n", encoding="utf-8")


COMMANDS: dict[str, Callable[[Session, list[str]], None]] = {
    "help": cmd_help,
    "h": cmd_help,
    "?": cmd_help,
    "menu": cmd_menu,
    "settings": cmd_settings,
    "set": cmd_set,
    "use": cmd_use,
    "ls": cmd_ls,
    "status": cmd_status,
    "inbox": cmd_inbox,
    "deferred": cmd_deferred,
    "trail": cmd_trail,
    "tree": cmd_tree,
    "map": cmd_map,
    "ask": cmd_ask,
    "inject": cmd_inject,
    "curriculum": cmd_curriculum,
    "tail": cmd_tail,
    "graph": cmd_graph,
    "score": cmd_score,
    "report": cmd_report,
    "open": cmd_open,
    "run": cmd_run,
    "daemon": cmd_daemon,
    "stop": cmd_stop,
    "pull": cmd_pull,
    "reinstall": cmd_reinstall,
    "update": cmd_update,
}


def dispatch_line(session: Session, line: str) -> bool:
    """Handle one interactive line. Return False to exit."""
    raw = line.strip()
    if not raw:
        return True
    if raw in {"/quit", "/exit", "quit", "exit"}:
        return False
    if not raw.startswith("/"):
        print("commands start with / — try /help or /menu")
        return True
    # Windows-friendly: allow /help and \help style already covered by /
    body = raw[1:].strip()
    if not body:
        return True
    try:
        parts = shlex.split(body, posix=os.name != "nt")
    except ValueError:
        # Fallback when quotes are messy on Windows
        parts = body.split()
    if not parts:
        return True
    # On Windows shlex posix=False still works; also accept help without slash already handled
    name = parts[0].lower()
    args = parts[1:]
    fn = COMMANDS.get(name)
    if fn is None:
        print(f"unknown command /{name} — try /help or /menu")
        return True
    try:
        fn(session, args)
    except (ValueError, OSError, FileExistsError, RuntimeError) as e:
        print(f"error: {e}", file=sys.stderr)
    return True


def run_repl(session: Session | None = None) -> int:
    session = load_session(session)
    print(
        f"ambc interactive shell — type /menu or press Enter for picker  "
        f"(out={session.out_dir})"
    )
    print(f"settings: llm={session.llm} model={session.model}  file={settings_path()}")
    while True:
        try:
            line = input("ambc> ")
        except EOFError:
            print()
            break
        except KeyboardInterrupt:
            print("\n(interrupted — /quit to exit)")
            continue
        try:
            if not line.strip():
                cmd_menu(session, [])
                continue
            if not dispatch_line(session, line):
                break
        except _ExitRepl:
            break
    return 0
