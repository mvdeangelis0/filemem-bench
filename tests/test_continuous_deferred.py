from pathlib import Path

from amb.continuous.deferred import append_deferred, list_deferred
from amb.continuous.lab import load_world
from amb.continuous.layout import DEFAULT_OBJECTIVE, init_run_dir
from amb.continuous.policy import Policy
from amb.continuous.tools import ToolRuntime


def test_init_run_dir_creates_skeleton(tmp_path: Path):
    run = init_run_dir(tmp_path / "continuous_runs", run_id="t1", world="crystal", seed=0)
    assert (run / "STATUS.md").is_file()
    assert (run / "INBOX.md").is_file()
    assert (run / "core" / "objective.md").read_text(encoding="utf-8").startswith(
        "Your continuing purpose"
    )
    assert (run / "core" / "capabilities.md").is_file()
    assert "ALLOWED" in (run / "core" / "capabilities.md").read_text(encoding="utf-8").upper() or (
        "Allowed" in (run / "core" / "capabilities.md").read_text(encoding="utf-8")
    )
    assert (run / "memory" / "observations.jsonl").is_file()
    assert (run / "memory" / "deferred.jsonl").is_file()
    assert (run / "memory" / "current_plan.json").is_file()
    assert (run / "memory" / "graph.json").is_file()
    assert (run / "memory" / "lessons.md").is_file()
    assert (run / "lab").is_dir()
    assert (run / "inbox_archive").is_dir()
    cfg = (run / "config.json").read_text(encoding="utf-8")
    assert '"world": "crystal"' in cfg
    assert DEFAULT_OBJECTIVE


def test_defer_tool_and_policy_auto_defer(tmp_path: Path):
    run = init_run_dir(tmp_path, run_id="d1", world="crystal", seed=0)
    world = load_world("crystal", run / "lab", seed=0)
    rt = ToolRuntime(run, world=world, policy=Policy(web_allowlist=[]))

    r = rt.execute(
        "defer",
        {
            "task": "Scrape arxiv for crystal papers",
            "reason": "web disabled",
            "need": "web",
        },
    )
    assert r["ok"]
    assert list_deferred(run)

    denied = rt.execute("fetch_allowlisted_page", {"url": "https://example.com"})
    assert not denied["ok"]
    assert denied.get("deferred")
    assert count_at_least(run, 2)


def count_at_least(run: Path, n: int) -> bool:
    return len(list_deferred(run)) >= n


def test_append_deferred_roundtrip(tmp_path: Path):
    run = init_run_dir(tmp_path, run_id="d2", world="crystal", seed=0)
    append_deferred(
        run,
        task="Need shell to run make",
        reason="no shell tool",
        need="shell",
        source="agent",
    )
    rows = list_deferred(run)
    assert rows[-1]["need"] == "shell"
    assert "make" in rows[-1]["task"]
