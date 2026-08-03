from pathlib import Path

from amb.continuous.memory_graph import MemoryGraph, _edge_key


def test_coaccess_strengthens_and_retrieve(tmp_path: Path):
    g = MemoryGraph(tmp_path / "graph.json")
    g.observe(["temperature", "growth"], observation_id="o1", success=False)
    g.observe(["temperature", "growth"], observation_id="o2", success=True)
    pack = g.retrieve(query_tokens=["temperature"], top_k=3)
    assert pack
    assert pack[0]["weight"] > 0
    # success boost => edge weight higher than single access
    data = g.load()
    edge = data["edges"][_edge_key("temperature", "growth")]
    assert edge["weight"] >= 2.0  # 1 + 1 + success boost >= 2
