from pathlib import Path

from amb.agents.llm import MockLLM, ScriptedTurn
from amb.continuous.loop import run_episode


def test_mock_episode_writes_artifacts(tmp_path: Path):
    turns = [
        ScriptedTurn(
            {
                "type": "tool_call",
                "tool": "lab_act",
                "arguments": {"temperature": 37, "humidity": 50},
            }
        ),
        ScriptedTurn(
            {
                "type": "tool_call",
                "tool": "create",
                "arguments": {
                    "path": "memory/notes.md",
                    "file_text": "# Notes\nPrefer temp near 37 and humidity 40-60.\n",
                },
            }
        ),
        ScriptedTurn(
            {
                "type": "tool_call",
                "tool": "done",
                "arguments": {"summary": "trial done"},
            }
        ),
    ]
    run_dir = run_episode(
        out_dir=tmp_path,
        world="crystal",
        llm=MockLLM(turns),
        max_steps=10,
        seed=0,
        model_id="mock",
        run_id="mock_ep1",
        verbose=False,
    )
    assert (run_dir / "STATUS.md").stat().st_size > 20
    assert (run_dir / "trajectory.jsonl").read_text(encoding="utf-8").strip()
    assert (run_dir / "actions.jsonl").read_text(encoding="utf-8").strip()
    graph = (run_dir / "memory" / "graph.json").read_text(encoding="utf-8")
    assert "nodes" in graph
    report = (run_dir / "REPORT.md").read_text(encoding="utf-8").lower()
    assert "done" in report or "stop" in report
