from pathlib import Path

from amb.continuous.layout import DEFAULT_OBJECTIVE, init_run_dir


def test_init_run_dir_creates_skeleton(tmp_path: Path):
    run = init_run_dir(tmp_path / "continuous_runs", run_id="t1", world="crystal", seed=0)
    assert (run / "STATUS.md").is_file()
    assert (run / "INBOX.md").is_file()
    assert (run / "core" / "objective.md").read_text(encoding="utf-8").startswith("Your continuing purpose")
    assert (run / "memory" / "observations.jsonl").is_file()
    assert (run / "memory" / "current_plan.json").is_file()
    assert (run / "memory" / "graph.json").is_file()
    assert (run / "memory" / "lessons.md").is_file()
    assert (run / "core" / "capabilities.md").is_file()
    assert (run / "memory" / "deferred.jsonl").is_file()
    assert (run / "lab").is_dir()
    assert (run / "inbox_archive").is_dir()
    cfg = (run / "config.json").read_text(encoding="utf-8")
    assert '"world": "crystal"' in cfg
    assert DEFAULT_OBJECTIVE
