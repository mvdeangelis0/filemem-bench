from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from amb import __version__
from amb.continuous.daemon import run_daemon
from amb.continuous.inbox import inject as continuous_inject
from amb.continuous.loop import run_episode
from amb.continuous.score import compare_episodes, score_run
from amb.ledger.regrade import regrade_run
from amb.report import write_report
from amb.runner import run_suite
from amb.suite.load import load_suite
from amb.suite.validate import validate_suite


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="amb", description="Agent Memory Bench CLI")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_val = sub.add_parser("validate-suite", help="Validate a suite directory")
    p_val.add_argument("suite")

    p_run = sub.add_parser("run", help="Run a suite")
    p_run.add_argument("--suite", required=True)
    p_run.add_argument("--out", default="runs")
    p_run.add_argument(
        "--llm", default="mock", choices=["mock", "ollama", "bedrock"]
    )
    p_run.add_argument("--seed", type=int, default=0)
    p_run.add_argument("--manage-model", default="mock")
    p_run.add_argument("--search-model", default="mock")
    p_run.add_argument(
        "--ollama-host",
        default=None,
        help="Ollama base URL (default: OLLAMA_HOST or http://127.0.0.1:11434)",
    )
    p_run.add_argument(
        "--aws-region",
        default=None,
        help="AWS region for --llm bedrock (default: AWS_REGION or us-east-1)",
    )
    p_run.add_argument("--arm", default="baseline")
    p_run.add_argument(
        "--search-mode",
        default="tools",
        choices=["tools", "rag"],
        help="tools=FS memory tool loop; rag=lexical top-k over chunks (verbatim only)",
    )
    p_run.add_argument(
        "--rag-top-k",
        type=int,
        default=3,
        help="Top-k chunks for --search-mode rag (default: 3)",
    )
    p_run.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Log each model call with timing (live progress always on for ollama/bedrock)",
    )

    p_re = sub.add_parser("regrade", help="Regrade a run ledger")
    p_re.add_argument("run_dir")
    p_re.add_argument("--suite", default=None)

    p_rep = sub.add_parser("report", help="Regenerate REPORT.md")
    p_rep.add_argument("run_dir")

    p_cont = sub.add_parser("continuous", help="Continuous sandboxed lab agent")
    cont_sub = p_cont.add_subparsers(dest="continuous_cmd", required=True)

    p_crun = cont_sub.add_parser("run", help="Run one continuous episode")
    p_crun.add_argument("--world", default="crystal")
    p_crun.add_argument("--llm", default="mock", choices=["mock", "ollama"])
    p_crun.add_argument("--model", default="mock")
    p_crun.add_argument("--max-steps", type=int, default=20)
    p_crun.add_argument("--seed", type=int, default=0)
    p_crun.add_argument("--out", default="continuous_runs")
    p_crun.add_argument("--run-id", default=None)
    p_crun.add_argument(
        "--ollama-host",
        default=None,
        help="Ollama base URL (default: OLLAMA_HOST or http://127.0.0.1:11434)",
    )
    p_crun.add_argument(
        "--web-allowlist",
        default="",
        help="Comma-separated hostnames allowed for web tools",
    )
    p_crun.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Log each continuous step (default on for ollama)",
    )
    p_crun.add_argument(
        "--observer",
        action="store_true",
        help="Reserved: observer summarizer (stub; not enabled yet)",
    )

    p_cinj = cont_sub.add_parser("inject", help="Append operator instruction to INBOX.md")
    p_cinj.add_argument("--run", required=True, help="Run directory")
    p_cinj.add_argument("text", help="Instruction text")

    p_cscore = cont_sub.add_parser("score", help="Score a continuous run")
    p_cscore.add_argument("--run", required=True)
    p_cscore.add_argument("--compare", default=None, help="Optional earlier run to compare")

    p_cdaemon = cont_sub.add_parser("daemon", help="Run episodes until STOP file")
    p_cdaemon.add_argument("--world", default="crystal")
    p_cdaemon.add_argument("--llm", default="mock", choices=["mock", "ollama"])
    p_cdaemon.add_argument("--model", default="mock")
    p_cdaemon.add_argument("--max-steps", type=int, default=20)
    p_cdaemon.add_argument("--seed", type=int, default=0)
    p_cdaemon.add_argument("--out", default="continuous_runs")
    p_cdaemon.add_argument("--idle-seconds", type=float, default=1.0)
    p_cdaemon.add_argument("--max-episodes", type=int, default=1)
    p_cdaemon.add_argument("--ollama-host", default=None)
    p_cdaemon.add_argument("--web-allowlist", default="")
    p_cdaemon.add_argument("-v", "--verbose", action="store_true")
    p_cdaemon.add_argument("--observer", action="store_true")

    args = parser.parse_args(argv)

    if args.cmd == "validate-suite":
        suite = load_suite(args.suite)
        errors = validate_suite(suite)
        if errors:
            print("INVALID")
            for e in errors:
                print(f"- {e}")
            sys.exit(1)
        print(f"OK {suite.meta.get('id')}@{suite.meta.get('version')}")
        return

    if args.cmd == "run":
        try:
            run_dir = run_suite(
                args.suite,
                out_dir=args.out,
                llm_mode=args.llm,
                seed=args.seed,
                manage_model=args.manage_model,
                search_model=args.search_model,
                arm_id=args.arm,
                ollama_host=args.ollama_host,
                aws_region=args.aws_region,
                verbose=args.verbose,
                search_mode=args.search_mode,
                rag_top_k=args.rag_top_k,
            )
        except (RuntimeError, ValueError) as e:
            print(f"error: {e}", file=sys.stderr)
            sys.exit(1)
        scorecard = json.loads((run_dir / "scorecard.json").read_text(encoding="utf-8"))
        summary = scorecard.get("summary", {})
        print(run_dir)
        print(
            f"pass_rate={summary.get('pass_rate')} "
            f"({summary.get('n_passed')}/{summary.get('n_scorecard')})"
        )
        usage_path = run_dir / "usage.json"
        if usage_path.exists():
            usage = json.loads(usage_path.read_text(encoding="utf-8"))
            total = usage.get("total") or {}
            est = usage.get("estimate") or {}
            usd = est.get("usd")
            usd_s = f"${usd:.4f}" if isinstance(usd, (int, float)) else "n/a"
            print(
                f"usage calls={total.get('n_calls')} "
                f"in={total.get('input_tokens')} out={total.get('output_tokens')} "
                f"est={usd_s}"
            )
        return

    if args.cmd == "regrade":
        scorecard = regrade_run(args.run_dir, suite_root=args.suite)
        print(json.dumps(scorecard.get("summary"), indent=2))
        return

    if args.cmd == "report":
        path = write_report(Path(args.run_dir))
        print(path)
        return

    if args.cmd == "continuous":
        if args.continuous_cmd == "inject":
            continuous_inject(Path(args.run), args.text)
            print(Path(args.run) / "INBOX.md")
            return
        if args.continuous_cmd == "score":
            if args.compare:
                cmp = compare_episodes(Path(args.compare), Path(args.run))
                print(json.dumps(cmp, indent=2))
            else:
                sc = score_run(Path(args.run))
                print(json.dumps(sc.get("summary"), indent=2))
            return
        if args.continuous_cmd in ("run", "daemon"):
            if args.observer:
                print(
                    "note: --observer is a stub; STATUS remains structured-only",
                    file=sys.stderr,
                )
            verbose = args.verbose or args.llm == "ollama"
            allowlist = [h.strip() for h in args.web_allowlist.split(",") if h.strip()]
            model_id = args.model
            if args.llm == "mock":
                from amb.agents.llm import MockLLM

                llm: object = MockLLM([])
                model_id = model_id if model_id != "mock" else "mock"
            elif args.llm == "ollama":
                from amb.agents.llm import OllamaLLM

                host = (
                    args.ollama_host
                    or os.environ.get("OLLAMA_HOST")
                    or "http://127.0.0.1:11434"
                )
                if model_id == "mock":
                    print(
                        "error: --model required for --llm ollama "
                        "(e.g. deepseek-r1:7b)",
                        file=sys.stderr,
                    )
                    sys.exit(1)
                llm = OllamaLLM(model_id, base_url=host, verbose=verbose)
            else:
                print(f"error: unsupported llm {args.llm}", file=sys.stderr)
                sys.exit(1)
            try:
                if args.continuous_cmd == "run":
                    run_dir = run_episode(
                        args.out,
                        world=args.world,
                        llm=llm,
                        max_steps=args.max_steps,
                        seed=args.seed,
                        model_id=model_id,
                        run_id=args.run_id,
                        verbose=verbose,
                        web_allowlist=allowlist,
                    )
                    print(run_dir)
                else:
                    runs = run_daemon(
                        run_episode_fn=run_episode,
                        out_dir=Path(args.out),
                        world=args.world,
                        llm=llm,
                        max_steps=args.max_steps,
                        seed=args.seed,
                        model_id=model_id,
                        idle_seconds=args.idle_seconds,
                        max_episodes=args.max_episodes,
                        web_allowlist=allowlist,
                        verbose=verbose,
                    )
                    for r in runs:
                        print(r)
            except (RuntimeError, ValueError, FileExistsError, OSError) as e:
                print(f"error: {e}", file=sys.stderr)
                sys.exit(1)
            return


if __name__ == "__main__":
    main()
