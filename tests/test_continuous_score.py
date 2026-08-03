import json
from pathlib import Path

import pytest

from amb.continuous.layout import init_run_dir
from amb.continuous.score import compare_episodes, score_run


def _write_ok_lab_act(run: Path, *, temperature: float, humidity: float, step: int = 1) -> None:
    row = {
        "step": step,
        "tool": "lab_act",
        "arguments": {"temperature": temperature, "humidity": humidity},
        "result": {
            "ok": True,
            "result": {
                "temperature": temperature,
                "humidity": humidity,
                "growth": 0.9,
                "trials": step,
            },
            "informative": True,
        },
    }
    with (run / "actions.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def test_score_run_discovers_laws(tmp_path: Path):
    run = init_run_dir(tmp_path, run_id="sc1", world="crystal", seed=0)
    _write_ok_lab_act(run, temperature=37, humidity=50)
    (run / "memory" / "notes.md").write_text(
        "Growth peaks near temperature 37 with humidity 50.\n",
        encoding="utf-8",
    )
    sc = score_run(run)
    assert sc["summary"]["n_passed"] == 3
    assert sc["summary"]["pass_rate"] == 1.0
    assert (run / "scorecard.json").is_file()


def test_score_run_fails_without_hints(tmp_path: Path):
    run = init_run_dir(tmp_path, run_id="sc2", world="crystal", seed=0)
    sc = score_run(run)
    assert sc["summary"]["n_passed"] == 0


def test_score_run_notes_alone_insufficient(tmp_path: Path):
    """Regression: corpus regex used to false-green on notes without real lab_acts."""
    run = init_run_dir(tmp_path, run_id="sc3", world="crystal", seed=0)
    (run / "memory" / "notes.md").write_text(
        "Growth peaks near temperature 37 with humidity 50.\n",
        encoding="utf-8",
    )
    sc = score_run(run)
    assert sc["summary"]["n_passed"] == 1  # claim only
    assert sc["summary"]["pass_rate"] < 1.0


def test_compare_episodes(tmp_path: Path):
    early = init_run_dir(tmp_path, run_id="e1", world="crystal", seed=0)
    late = init_run_dir(tmp_path, run_id="e2", world="crystal", seed=0)
    _write_ok_lab_act(late, temperature=37, humidity=45)
    (late / "memory" / "notes.md").write_text(
        "Prefer temp 37 and humidity around 45.\n", encoding="utf-8"
    )
    cmp = compare_episodes(early, late)
    assert cmp["improved"] is True
    assert cmp["delta"] > 0


def test_historical_desktop_run_fails_strict_score():
    run = Path("continuous_runs/20260803_183032__crystal")
    if not run.is_dir():
        pytest.skip("historical continuous run not present")
    sc = score_run(run)
    assert sc["summary"]["n_passed"] < sc["summary"]["n_total"]
    assert sc["summary"]["pass_rate"] < 1.0
