from pathlib import Path

from amb.continuous.daemon import should_stop
from amb.continuous.layout import init_run_dir


def test_stop_file(tmp_path: Path):
    run = init_run_dir(tmp_path, run_id="d1", world="crystal", seed=0)
    assert not should_stop(run)
    (run / "STOP").write_text("1\n", encoding="utf-8")
    assert should_stop(run)
