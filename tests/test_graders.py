import json
import shutil
from pathlib import Path

from amb.graders.engine import grade
from amb.suite.load import load_suite

ROOT = Path(__file__).resolve().parents[1]


def _mini_run(tmp_path: Path, store_src: Path) -> Path:
    run = tmp_path / "run"
    (run / "stores" / "organized").mkdir(parents=True)
    (run / "stores" / "verbatim").mkdir(parents=True)
    (run / "search_outputs" / "organized").mkdir(parents=True)
    (run / "search_outputs" / "verbatim").mkdir(parents=True)
    shutil.copytree(store_src, run / "stores" / "organized", dirs_exist_ok=True)
    # minimal search outputs for drink query
    for shape in ("organized", "verbatim"):
        (run / "search_outputs" / shape / "q_drink_current.json").write_text(
            json.dumps(
                {
                    "query_id": "q_drink_current",
                    "shape": shape,
                    "answer": "coffee",
                    "citations": ["people/morgan.md"],
                    "status": "ok",
                }
            ),
            encoding="utf-8",
        )
    return run


def test_negative_stale_drink_fails_update(tmp_path):
    suite = load_suite(ROOT / "suites" / "smoke")
    run = _mini_run(tmp_path, ROOT / "suites/smoke/fixtures_negative/stale_drink")
    # fix citation path for negative store
    for shape in ("organized", "verbatim"):
        (run / "search_outputs" / shape / "q_drink_current.json").write_text(
            json.dumps(
                {
                    "query_id": "q_drink_current",
                    "shape": shape,
                    "answer": "tea",
                    "citations": ["people/morgan.md"],
                    "status": "ok",
                }
            ),
            encoding="utf-8",
        )
    scorecard, _ = grade(run, suite)
    upd = next(
        r
        for r in scorecard["results"]
        if r["family"] == "update_precedence"
    )
    assert upd["passed"] is False


def test_positive_store_passes_update(tmp_path):
    suite = load_suite(ROOT / "suites" / "smoke")
    run = _mini_run(tmp_path, ROOT / "suites/smoke/fixtures_positive/good_store")
    scorecard, _ = grade(run, suite)
    upd = next(r for r in scorecard["results"] if r["family"] == "update_precedence")
    assert upd["passed"] is True
    prot = next(r for r in scorecard["results"] if r["family"] == "protected_survives")
    assert prot["passed"] is True


def test_answer_match_accepts_gold_substring(tmp_path):
    suite = load_suite(ROOT / "suites" / "smoke")
    run = _mini_run(tmp_path, ROOT / "suites/smoke/fixtures_positive/good_store")
    for shape in ("organized", "verbatim"):
        (run / "search_outputs" / shape / "q_drink_current.json").write_text(
            json.dumps(
                {
                    "query_id": "q_drink_current",
                    "shape": shape,
                    "answer": "Morgan prefers to drink coffee.",
                    "citations": ["people/morgan.md"],
                    "status": "ok",
                }
            ),
            encoding="utf-8",
        )
        (run / "search_outputs" / shape / "q_roommate.json").write_text(
            json.dumps(
                {
                    "query_id": "q_roommate",
                    "shape": shape,
                    "answer": "Jordan Lee",
                    "citations": ["people/morgan.md"],
                    "status": "ok",
                }
            ),
            encoding="utf-8",
        )
    scorecard, _ = grade(run, suite)
    drink = [
        r
        for r in scorecard["results"]
        if r["family"] == "answer_match" and "drink" in r["check_id"]
    ]
    assert drink and all(r["passed"] for r in drink)
    # Forbidden stale form still fails even inside a sentence.
    for shape in ("organized", "verbatim"):
        (run / "search_outputs" / shape / "q_drink_current.json").write_text(
            json.dumps(
                {
                    "query_id": "q_drink_current",
                    "shape": shape,
                    "answer": "Morgan prefers to drink tea.",
                    "citations": ["people/morgan.md"],
                    "status": "ok",
                }
            ),
            encoding="utf-8",
        )
    scorecard, _ = grade(run, suite)
    drink_bad = [
        r
        for r in scorecard["results"]
        if r["family"] == "answer_match" and "drink" in r["check_id"]
    ]
    assert drink_bad and all(not r["passed"] for r in drink_bad)
