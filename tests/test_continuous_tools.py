from pathlib import Path

from amb.agents.llm import MockLLM, ScriptedTurn
from amb.continuous.lab import load_world
from amb.continuous.layout import init_run_dir
from amb.continuous.policy import Policy
from amb.continuous.tools import ToolRuntime


def test_workspace_create_view(tmp_path: Path):
    run = init_run_dir(tmp_path, run_id="w1", world="crystal", seed=0)
    world = load_world("crystal", run / "lab", seed=0)
    rt = ToolRuntime(run, world=world, policy=Policy(web_allowlist=[]))
    r = rt.execute("create", {"path": "memory/notes.md", "file_text": "hello"})
    assert r["ok"]
    r2 = rt.execute("view", {"path": "memory/notes.md"})
    assert r2["ok"] and "hello" in r2["content"]


def test_create_survives_relative_run_dir(tmp_path: Path, monkeypatch):
    """Regression: create used to ValueError after write when run_dir was relative."""
    monkeypatch.chdir(tmp_path)
    run = Path("rel_run")
    run.mkdir()
    (run / "lab").mkdir()
    world = load_world("crystal", run / "lab", seed=0)
    rt = ToolRuntime(run, world=world, policy=Policy(web_allowlist=[]))
    r = rt.execute("create", {"path": "note.json", "content": [{"k": 1}]})
    assert r["ok"], r
    assert r["path"] == "note.json"
    text = (run / "note.json").read_text(encoding="utf-8")
    assert '"k"' in text and "1" in text


def test_lab_roundtrip(tmp_path: Path):
    run = init_run_dir(tmp_path, run_id="w2", world="crystal", seed=0)
    world = load_world("crystal", run / "lab", seed=0)
    rt = ToolRuntime(run, world=world, policy=Policy(web_allowlist=[]))
    assert rt.execute("lab_act", {"temperature": 37, "humidity": 50})["ok"]
    sense = rt.execute("lab_sense", {})
    assert sense["ok"] and "growth" in sense["result"]


def test_lab_act_rejects_fake_action_keys(tmp_path: Path):
    run = init_run_dir(tmp_path, run_id="w4", world="crystal", seed=0)
    world = load_world("crystal", run / "lab", seed=0)
    rt = ToolRuntime(run, world=world, policy=Policy(web_allowlist=[]))
    r = rt.execute("lab_act", {"action": "test_action_optimized_growth"})
    assert not r["ok"]
    assert r["error_code"] == "bad_args"
    assert "temperature" in r["error"]


def test_lab_act_sets_temp_humidity_ignores_extra(tmp_path: Path):
    run = init_run_dir(tmp_path, run_id="w5", world="crystal", seed=0)
    world = load_world("crystal", run / "lab", seed=0)
    rt = ToolRuntime(run, world=world, policy=Policy(web_allowlist=[]))
    r = rt.execute(
        "lab_act",
        {"temperature": 37, "humidity": 50, "action": "ignored"},
    )
    assert r["ok"]
    assert r["result"]["temperature"] == 37.0
    assert r["result"]["humidity"] == 50.0
    assert "action" in r.get("ignored_keys", [])


def test_python_accepts_script_alias(tmp_path: Path):
    run = init_run_dir(tmp_path, run_id="w6", world="crystal", seed=0)
    world = load_world("crystal", run / "lab", seed=0)
    rt = ToolRuntime(run, world=world, policy=Policy(web_allowlist=[]))
    r = rt.execute("run_bounded_python", {"script": "result = 2 + 2"})
    assert r["ok"] and r["result"] == 4


def test_python_math_via_tools(tmp_path: Path):
    run = init_run_dir(tmp_path, run_id="w3", world="crystal", seed=0)
    world = load_world("crystal", run / "lab", seed=0)
    rt = ToolRuntime(run, world=world, policy=Policy(web_allowlist=[]))
    r = rt.execute("run_bounded_python", {"code": "result = 1 + 1"})
    assert r["ok"] and r["result"] == 2


def test_absolute_path_error_uses_continuous_example(tmp_path: Path):
    run = init_run_dir(tmp_path, run_id="w7", world="crystal", seed=0)
    world = load_world("crystal", run / "lab", seed=0)
    rt = ToolRuntime(run, world=world, policy=Policy(web_allowlist=[]))
    r = rt.execute("view", {"path": "/path/to/data.json"})
    assert not r["ok"]
    assert "people/morgan.md" not in r["error"]
    assert "memory/notes.md" in r["error"]


def test_mock_llm_unused_import_ok():
    # Keep MockLLM import wired for loop tests package discovery.
    assert MockLLM is not None and ScriptedTurn is not None
