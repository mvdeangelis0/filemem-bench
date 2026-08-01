from __future__ import annotations

import json
from pathlib import Path

from amb.graders.engine import grade
from amb.suite.load import load_suite


def regrade_run(run_dir: Path | str, suite_root: Path | str | None = None) -> dict:
    run_dir = Path(run_dir)
    config = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
    if suite_root is None:
        suite_root = config.get("suite", {}).get("path")
        if not suite_root:
            # default relative to cwd
            suite_id = config.get("suite", {}).get("id", "smoke")
            suite_root = Path("suites") / suite_id
    suite = load_suite(suite_root)
    scorecard, diagnostics = grade(run_dir, suite)
    (run_dir / "scorecard.json").write_text(
        json.dumps(scorecard, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (run_dir / "diagnostics.json").write_text(
        json.dumps(diagnostics, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return scorecard
