from pathlib import Path

from amb.bookkeeper import Bookkeeper, validate_citations
from amb.harness.memory_tool import MemoryToolHarness


def test_bookkeeper_read_and_brief(tmp_path: Path):
    h = MemoryToolHarness(tmp_path, role="manage")
    assert h.execute("create", {"path": "people/morgan.md", "file_text": "drink: oat\n"})[
        "ok"
    ]
    bk = Bookkeeper(tmp_path)
    listed = bk.list_dir(".")
    assert listed["ok"]
    assert "people/" in listed["listing"]
    brief = bk.brief("people/morgan.md")
    assert brief["ok"]
    assert "oat" in brief["content"]
    assert brief["citations"] == ["people/morgan.md"]


def test_validate_citations_rejects_placeholder(tmp_path: Path):
    h = MemoryToolHarness(tmp_path, role="manage")
    h.execute("create", {"path": "people/morgan.md", "file_text": "x\n"})
    bad = validate_citations(tmp_path, ["path.md"], answer="oat latte")
    assert bad["ok"] is False
    good = validate_citations(tmp_path, ["people/morgan.md"], answer="oat latte")
    assert good["ok"] is True
    unk = validate_citations(tmp_path, [], answer="unknown")
    assert unk["ok"] is True


def test_search_store_map_lists_children(tmp_path: Path):
    from amb.agents.search import _store_map

    h = MemoryToolHarness(tmp_path, role="manage")
    h.execute("create", {"path": "people/morgan.md", "file_text": "drink: coffee\n"})
    h.execute("create", {"path": "notes/a.md", "file_text": "x\n"})
    sm = _store_map(tmp_path)
    assert sm["root"]["ok"]
    assert "people/" in sm["root"]["listing"]
    assert "morgan.md" in sm["children"]["people/"]
