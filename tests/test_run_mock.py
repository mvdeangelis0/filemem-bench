import json
from pathlib import Path

from amb.ledger.regrade import regrade_run
from amb.runner import run_suite

ROOT = Path(__file__).resolve().parents[1]


def test_mock_smoke_run_and_regrade(tmp_path):
    run_dir = run_suite(
        ROOT / "suites" / "smoke",
        out_dir=tmp_path / "runs",
        llm_mode="mock",
        seed=1,
    )
    score1 = json.loads((run_dir / "scorecard.json").read_text(encoding="utf-8"))
    assert score1["summary"]["n_scorecard"] > 0
    # scripted manage+search should pass most checks
    assert score1["summary"]["pass_rate"] >= 0.8

    score2 = regrade_run(run_dir, suite_root=ROOT / "suites" / "smoke")
    assert score2["summary"]["pass_rate"] == score1["summary"]["pass_rate"]
    assert score2["summary"]["n_passed"] == score1["summary"]["n_passed"]
