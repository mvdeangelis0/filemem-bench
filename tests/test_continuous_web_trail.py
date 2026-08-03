from pathlib import Path

from amb.continuous.lab import load_world
from amb.continuous.layout import init_run_dir
from amb.continuous.policy import Policy
from amb.continuous.tools import ToolRuntime
from amb.continuous.web_trail import list_trail, read_cursor


def test_web_trail_records_search_and_cursor(tmp_path: Path):
    run = init_run_dir(tmp_path, run_id="wt1", world="crystal", seed=0)
    assert (run / "memory" / "web_trail.jsonl").is_file()
    assert (run / "memory" / "web_cursor.json").is_file()
    world = load_world("crystal", run / "lab", seed=0)
    rt = ToolRuntime(
        run, world=world, policy=Policy(web_allowlist=["example.com"]), step=3
    )
    r = rt.execute("search_allowlisted_web", {"query": "crystal growth"})
    assert r["ok"]
    trail = list_trail(run)
    assert trail
    assert trail[-1]["action"] == "search"
    assert trail[-1]["query"] == "crystal growth"
    assert trail[-1]["step"] == 3
    cursor = read_cursor(run)
    assert cursor is not None
    assert "crystal growth" in (cursor.get("left_off") or "")
    assert cursor.get("updated_at")
