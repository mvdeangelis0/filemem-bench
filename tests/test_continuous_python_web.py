from pathlib import Path

from amb.continuous.lab import load_world
from amb.continuous.layout import init_run_dir
from amb.continuous.policy import Policy
from amb.continuous.tools import ToolRuntime


def test_bounded_python_math(tmp_path: Path):
    run = init_run_dir(tmp_path, run_id="py1", world="crystal", seed=0)
    world = load_world("crystal", run / "lab", seed=0)
    rt = ToolRuntime(run, world=world, policy=Policy(web_allowlist=[]))
    r = rt.execute("run_bounded_python", {"code": "result = 2 + 2"})
    assert r["ok"]
    assert r["result"] == 4


def test_bounded_python_blocks_os(tmp_path: Path):
    run = init_run_dir(tmp_path, run_id="py2", world="crystal", seed=0)
    world = load_world("crystal", run / "lab", seed=0)
    rt = ToolRuntime(run, world=world, policy=Policy(web_allowlist=[]))
    r = rt.execute("run_bounded_python", {"code": "import os\nresult = os.getcwd()"})
    assert not r["ok"]
    assert r["error_code"] == "policy_denied"


def test_web_fetch_blocked_empty_allowlist(tmp_path: Path):
    run = init_run_dir(tmp_path, run_id="web1", world="crystal", seed=0)
    world = load_world("crystal", run / "lab", seed=0)
    rt = ToolRuntime(run, world=world, policy=Policy(web_allowlist=[]))
    r = rt.execute("fetch_allowlisted_page", {"url": "https://example.com"})
    assert not r["ok"]
    assert r["error_code"] == "policy_denied"


def test_web_search_lists_hosts(tmp_path: Path):
    run = init_run_dir(tmp_path, run_id="web2", world="crystal", seed=0)
    world = load_world("crystal", run / "lab", seed=0)
    rt = ToolRuntime(run, world=world, policy=Policy(web_allowlist=["example.com"]))
    r = rt.execute("search_allowlisted_web", {"query": "crystal"})
    assert r["ok"]
    assert "example.com" in r["result"]["hosts"]
