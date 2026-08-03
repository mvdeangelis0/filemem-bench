from pathlib import Path

from amb.agents.llm import MockLLM, ScriptedTurn
from amb.continuous.layout import init_run_dir
from amb.continuous.memory_browser import ask_over_run, build_map, inventory_tree, load_run_docs


def test_inventory_and_map(tmp_path: Path):
    run = init_run_dir(tmp_path, run_id="mb1", world="crystal", seed=0)
    (run / "memory" / "notes.md").write_text(
        "Crystal growth prefers temperature near 37C.\n", encoding="utf-8"
    )
    lines = inventory_tree(run)
    assert any("memory/notes.md" in ln for ln in lines)
    text = build_map(run)
    assert "Operator map" in text
    assert (run / "OPERATOR_MAP.md").is_file()
    assert "memory/notes.md" in text or "File roles" in text


def test_ask_retrieves_notes(tmp_path: Path):
    run = init_run_dir(tmp_path, run_id="mb2", world="crystal", seed=0)
    (run / "memory" / "notes.md").write_text(
        "Ideal humidity band is 40 to 60 percent.\n", encoding="utf-8"
    )
    docs = load_run_docs(run)
    assert any(d["path"] == "memory/notes.md" for d in docs)
    llm = MockLLM(
        [ScriptedTurn({"type": "final", "content": "Humidity should be 40-60% (memory/notes.md)."})]
    )
    out = ask_over_run(run, "What humidity is ideal?", llm=llm)
    assert "40" in out["answer"]
    assert out["sources"]
    assert any(s["path"] == "memory/notes.md" for s in out["sources"])
