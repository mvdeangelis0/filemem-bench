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


def test_later_update_gate_forces_chunk_008(tmp_path: Path):
    from amb.bookkeeper import later_update_gate

    h = MemoryToolHarness(tmp_path, role="manage")
    h.execute(
        "create",
        {
            "path": "chunks/chunk_001.md",
            "file_text": (
                "---\nid: chunk_001\nt: 1\ntitle: About me\n---\n"
                "Preferred drink: tea.\n"
            ),
        },
    )
    h.execute(
        "create",
        {
            "path": "chunks/chunk_008.md",
            "file_text": (
                "---\nid: chunk_008\nt: 8\ntitle: Preference update\n---\n"
                "Update: Morgan now prefers coffee, not tea.\n"
                "Please treat coffee as the current preferred drink.\n"
            ),
        },
    )
    h.execute(
        "create",
        {
            "path": "chunks/chunk_010.md",
            "file_text": (
                "---\nid: chunk_010\nt: 10\ntitle: Atlas status\n---\n"
                "Atlas API review still owned by Priya.\n"
            ),
        },
    )
    bk = Bookkeeper(tmp_path)
    timeline = bk.chunk_timeline()
    assert any(r["path"] == "chunks/chunk_008.md" and r["update_flag"] for r in timeline)
    blocked = later_update_gate(
        tmp_path,
        "What does Morgan prefer to drink?",
        answer="tea",
        citations=["chunks/chunk_001.md"],
    )
    assert blocked["ok"] is False
    assert "chunks/chunk_008.md" in blocked["hint_paths"]
    # Citing the update clears the gate.
    ok = later_update_gate(
        tmp_path,
        "What does Morgan prefer to drink?",
        answer="coffee",
        citations=["chunks/chunk_008.md"],
    )
    assert ok["ok"] is True
    # Abstain never blocked.
    unk = later_update_gate(
        tmp_path,
        "What does Morgan prefer to drink?",
        answer="unknown",
        citations=[],
    )
    assert unk["ok"] is True


def test_search_retries_after_later_update_gate(tmp_path: Path):
    from amb.agents.llm import MockLLM, ScriptedTurn
    from amb.agents.search import run_search

    h = MemoryToolHarness(tmp_path, role="manage")
    h.execute(
        "create",
        {
            "path": "chunks/chunk_001.md",
            "file_text": "---\nt: 1\n---\nPreferred drink: tea.\n",
        },
    )
    h.execute(
        "create",
        {
            "path": "chunks/chunk_008.md",
            "file_text": (
                "---\nt: 8\n---\nUpdate: Morgan now prefers coffee, not tea.\n"
                "Please treat coffee as the current preferred drink.\n"
            ),
        },
    )
    llm = MockLLM(
        [
            ScriptedTurn(
                {
                    "type": "tool_call",
                    "tool": "view",
                    "arguments": {"path": "chunks/chunk_001.md"},
                }
            ),
            ScriptedTurn(
                {
                    "type": "tool_call",
                    "tool": "done",
                    "arguments": {
                        "answer": "tea",
                        "citations": ["chunks/chunk_001.md"],
                        "confidence": "high",
                    },
                }
            ),
            ScriptedTurn(
                {
                    "type": "tool_call",
                    "tool": "view",
                    "arguments": {"path": "chunks/chunk_008.md"},
                }
            ),
            ScriptedTurn(
                {
                    "type": "tool_call",
                    "tool": "done",
                    "arguments": {
                        "answer": "coffee",
                        "citations": ["chunks/chunk_008.md"],
                        "confidence": "high",
                    },
                }
            ),
        ]
    )
    payload, steps = run_search(
        llm,
        tmp_path,
        "What does Morgan prefer to drink?",
        "search",
        shape="verbatim",
    )
    assert payload["answer"] == "coffee"
    assert any(
        s.get("rejected") and (s.get("observation") or {}).get("error_code")
        == "later_update_unchecked"
        for s in steps
    )
