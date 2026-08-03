from __future__ import annotations

import json
import os
import shlex
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from amb.continuous.daemon import run_daemon, should_stop
from amb.continuous.inbox import inject as continuous_inject
from amb.continuous.loop import run_episode
from amb.continuous.score import compare_episodes, score_run


HELP_TEXT = """
ambc — continuous sandboxed lab agent

Slash commands (interactive):
  /help                         Show this help
  /status                       Print STATUS.md for the active run
  /inbox                        Show pending INBOX.md
  /inject <text>                Queue an operator instruction
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
  /quit  |  /exit               Leave the shell

One-shot (non-interactive):
  ambc                         Enter interactive shell
  ambc help
  ambc run --llm ollama --model deepseek-r1:7b --max-steps 50
  ambc inject --run <dir> "Focus on humidity"
  ambc score --run <dir>
  ambc status --run <dir>

/run flags: --world --llm --model --max-steps --seed --out --run-id
            --ollama-host --web-allowlist -v --observer
""".strip()


def build_llm(
    *,
    llm_mode: str,
    model: str,
    ollama_host: str | None,
    verbose: bool,
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
        return OllamaLLM(model_id, base_url=host, verbose=verbose), model_id
    raise ValueError(f"unsupported llm {llm_mode}")


def parse_allowlist(raw: str) -> list[str]:
    return [h.strip() for h in raw.split(",") if h.strip()]


@dataclass
class Session:
    out_dir: Path = field(default_factory=lambda: Path("continuous_runs"))
    run_dir: Path | None = None
    world: str = "crystal"
    llm: str = "mock"
    model: str = "mock"
    max_steps: int = 20
    seed: int = 0
    ollama_host: str | None = None
    web_allowlist: str = ""
    verbose: bool = True
    observer: bool = False
    idle_seconds: float = 1.0
    max_episodes: int = 1

    def require_run(self) -> Path:
        if self.run_dir is None or not self.run_dir.exists():
            raise ValueError("no active run — use /run or /use <run_dir>")
        return self.run_dir


def _print_file(path: Path) -> None:
    if not path.exists():
        print(f"(missing) {path}")
        return
    text = path.read_text(encoding="utf-8")
    print(text, end="" if text.endswith("\n") else "\n")


def cmd_help(_session: Session, _args: list[str]) -> None:
    print(HELP_TEXT)


def cmd_settings(session: Session, _args: list[str]) -> None:
    print(
        json.dumps(
            {
                "out": str(session.out_dir),
                "run": str(session.run_dir) if session.run_dir else None,
                "world": session.world,
                "llm": session.llm,
                "model": session.model,
                "max_steps": session.max_steps,
                "seed": session.seed,
                "ollama_host": session.ollama_host,
                "web_allowlist": session.web_allowlist,
                "verbose": session.verbose,
                "observer": session.observer,
                "idle_seconds": session.idle_seconds,
                "max_episodes": session.max_episodes,
            },
            indent=2,
        )
    )


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
    }
    if key not in mapping:
        raise ValueError(f"unknown key {key!r}; see /settings")
    mapping[key](value)
    print(f"set {key}={value}")


def cmd_use(session: Session, args: list[str]) -> None:
    if not args:
        raise ValueError("usage: /use <run_dir>")
    path = Path(args[0])
    if not path.exists():
        raise ValueError(f"not found: {path}")
    session.run_dir = path
    print(f"active run: {path}")


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


def cmd_inject(session: Session, args: list[str]) -> None:
    if not args:
        raise ValueError('usage: /inject <text>')
    run = session.require_run()
    continuous_inject(run, " ".join(args))
    print(f"injected → {run / 'INBOX.md'}")


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
        elif key in {"max_steps", "seed", "max_episodes"}:
            setattr(session, key, int(val))
        elif key == "idle_seconds":
            session.idle_seconds = float(val)
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
    )
    run_id = getattr(session, "_run_id", None)
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
    )
    session.run_dir = run_dir
    if hasattr(session, "_run_id"):
        delattr(session, "_run_id")
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
    for r in runs:
        print(r)


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
    "settings": cmd_settings,
    "set": cmd_set,
    "use": cmd_use,
    "ls": cmd_ls,
    "status": cmd_status,
    "inbox": cmd_inbox,
    "inject": cmd_inject,
    "tail": cmd_tail,
    "graph": cmd_graph,
    "score": cmd_score,
    "report": cmd_report,
    "open": cmd_open,
    "run": cmd_run,
    "daemon": cmd_daemon,
    "stop": cmd_stop,
}


def dispatch_line(session: Session, line: str) -> bool:
    """Handle one interactive line. Return False to exit."""
    raw = line.strip()
    if not raw:
        return True
    if raw in {"/quit", "/exit", "quit", "exit"}:
        return False
    if not raw.startswith("/"):
        print("commands start with / — try /help")
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
        print(f"unknown command /{name} — try /help")
        return True
    try:
        fn(session, args)
    except (ValueError, OSError, FileExistsError, RuntimeError) as e:
        print(f"error: {e}", file=sys.stderr)
    return True


def run_repl(session: Session | None = None) -> int:
    session = session or Session()
    print(f"ambc interactive shell — type /help  (out={session.out_dir})")
    while True:
        try:
            line = input("ambc> ")
        except EOFError:
            print()
            break
        except KeyboardInterrupt:
            print("\n(interrupted — /quit to exit)")
            continue
        if not dispatch_line(session, line):
            break
    return 0
