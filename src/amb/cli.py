from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from amb import __version__
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


if __name__ == "__main__":
    main()
