from pathlib import Path

from amb.continuous.inbox import consume_inbox, inject
from amb.continuous.layout import init_run_dir
from amb.continuous.status import write_status


def test_inject_and_consume(tmp_path: Path):
    run = init_run_dir(tmp_path, run_id="i1", world="crystal", seed=0)
    inject(run, "Focus on humidity.")
    assert "humidity" in (run / "INBOX.md").read_text(encoding="utf-8")
    text = consume_inbox(run)
    assert "humidity" in text
    assert (run / "INBOX.md").read_text(encoding="utf-8").strip() == ""
    archived = list((run / "inbox_archive").glob("*.md"))
    assert len(archived) == 1


def test_write_status(tmp_path: Path):
    run = init_run_dir(tmp_path, run_id="s1", world="crystal", seed=0)
    write_status(
        run,
        step=3,
        max_steps=10,
        last_tool="lab_act",
        last_ok=True,
        last_summary="set temp=40",
    )
    body = (run / "STATUS.md").read_text(encoding="utf-8")
    assert "Explore instruments" in body  # from default plan
    assert "lab_act" in body
    assert "3/10" in body
