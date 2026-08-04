from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from amb import __version__
from amb.continuous.console import (
    HELP_TEXT,
    Session,
    build_llm,
    cmd_run,
    load_session,
    parse_allowlist,
    run_repl,
)
from amb.continuous.daemon import run_daemon
from amb.continuous.inbox import inject as continuous_inject
from amb.continuous.loop import run_episode
from amb.continuous.score import compare_episodes, score_run


def _add_run_flags(p: argparse.ArgumentParser) -> None:
    p.add_argument("--world", default="crystal")
    p.add_argument("--llm", default="ollama", choices=["mock", "ollama"])
    p.add_argument("--model", default="qwen2.5:7b-instruct-q4_K_M")
    p.add_argument("--max-steps", type=int, default=30)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out", default="continuous_runs")
    p.add_argument("--run-id", default=None)
    p.add_argument("--ollama-host", default=None)
    p.add_argument("--web-allowlist", default="")
    p.add_argument("--num-ctx", type=int, default=4096)
    p.add_argument("--num-predict", type=int, default=512)
    p.add_argument("--keep-alive", default="30m")
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("--observer", action="store_true")


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)

    # Bare `ambc` or `ambc shell` → interactive
    if not argv or argv[0] in {"shell", "repl", "i"}:
        raise SystemExit(run_repl(load_session()))

    if argv[0] in {"help", "-h", "--help", "/help"}:
        print(HELP_TEXT)
        return

    parser = argparse.ArgumentParser(
        prog="ambc",
        description="Dedicated continuous-agent CLI (interactive slash commands + one-shot)",
    )
    parser.add_argument("--version", action="version", version=f"ambc {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_shell = sub.add_parser("shell", help="Interactive slash-command shell")
    p_shell.add_argument("--out", default="continuous_runs")

    p_run = sub.add_parser("run", help="Run one episode")
    _add_run_flags(p_run)

    p_inj = sub.add_parser("inject", help="Inject operator text into INBOX.md")
    p_inj.add_argument("--run", required=True)
    p_inj.add_argument("text")

    p_score = sub.add_parser("score", help="Score a run")
    p_score.add_argument("--run", required=True)
    p_score.add_argument("--compare", default=None)

    p_status = sub.add_parser("status", help="Print STATUS.md")
    p_status.add_argument("--run", required=True)

    p_daemon = sub.add_parser("daemon", help="Run episodes until STOP")
    _add_run_flags(p_daemon)
    p_daemon.add_argument("--idle-seconds", type=float, default=1.0)
    p_daemon.add_argument("--max-episodes", type=int, default=1)

    args = parser.parse_args(argv)

    if args.cmd == "shell":
        raise SystemExit(run_repl(Session(out_dir=Path(args.out))))

    if args.cmd == "inject":
        continuous_inject(Path(args.run), args.text)
        print(Path(args.run) / "INBOX.md")
        return

    if args.cmd == "score":
        if args.compare:
            print(json.dumps(compare_episodes(Path(args.compare), Path(args.run)), indent=2))
        else:
            print(json.dumps(score_run(Path(args.run)).get("summary"), indent=2))
        return

    if args.cmd == "status":
        path = Path(args.run) / "STATUS.md"
        print(path.read_text(encoding="utf-8") if path.exists() else "(missing STATUS.md)")
        return

    if args.cmd in {"run", "daemon"}:
        session = Session(
            out_dir=Path(args.out),
            world=args.world,
            llm=args.llm,
            model=args.model,
            max_steps=args.max_steps,
            seed=args.seed,
            ollama_host=args.ollama_host,
            web_allowlist=args.web_allowlist,
            verbose=args.verbose or args.llm == "ollama",
            observer=args.observer,
            num_ctx=args.num_ctx,
            num_predict=args.num_predict,
            keep_alive=args.keep_alive,
        )
        if args.cmd == "run":
            if args.run_id:
                setattr(session, "_run_id", args.run_id)
            cmd_run(session, [])
            return
        session.idle_seconds = args.idle_seconds
        session.max_episodes = args.max_episodes
        if args.observer:
            print("note: --observer is a stub; STATUS remains structured-only", file=sys.stderr)
        verbose = session.verbose
        try:
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
        except (RuntimeError, ValueError, FileExistsError, OSError) as e:
            print(f"error: {e}", file=sys.stderr)
            raise SystemExit(1) from e
        for r in runs:
            print(r)
        return


if __name__ == "__main__":
    main()
