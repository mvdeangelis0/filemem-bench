import json
from pathlib import Path

from amb.graders.engine import grade
from amb.runner import run_suite
from amb.suite.load import load_suite
from amb.suite.validate import validate_suite

ROOT = Path(__file__).resolve().parents[1]


def test_core_validates():
    suite = load_suite(ROOT / "suites" / "core")
    errors = validate_suite(suite)
    assert errors == [], errors
    assert len(suite.chunks) >= 20
    assert len(suite.queries) >= 15


def test_core_smoke_chunks_prefix_match():
    smoke = load_suite(ROOT / "suites" / "smoke")
    core = load_suite(ROOT / "suites" / "core")
    for sc, cc in zip(smoke.chunks, core.chunks[: len(smoke.chunks)]):
        assert sc["id"] == cc["id"]
        assert sc["text"].strip() == cc["text"].strip()


def test_core_negative_deadline_fails(tmp_path):
    import shutil

    suite = load_suite(ROOT / "suites" / "core")
    run = tmp_path / "run"
    (run / "stores" / "organized").mkdir(parents=True)
    (run / "stores" / "verbatim").mkdir(parents=True)
    (run / "search_outputs" / "organized").mkdir(parents=True)
    (run / "search_outputs" / "verbatim").mkdir(parents=True)
    src = ROOT / "suites/core/fixtures_negative/stale_deadline"
    shutil.copytree(src, run / "stores" / "organized", dirs_exist_ok=True)
    # also need drink/editor facts absent -> update drink may fail; focus deadline check
    scorecard, _ = grade(run, suite)
    upd = next(
        r
        for r in scorecard["results"]
        if r.get("check_id") == "mgmt.update_precedence.atlas_deadline"
    )
    assert upd["passed"] is False


def test_core_mock_run(tmp_path):
    run_dir = run_suite(
        ROOT / "suites" / "core",
        out_dir=tmp_path / "runs",
        llm_mode="mock",
        seed=2,
    )
    score = json.loads((run_dir / "scorecard.json").read_text(encoding="utf-8"))
    assert score["summary"]["pass_rate"] >= 0.95
