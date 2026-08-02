from pathlib import Path

from amb.agents.llm import MockLLM, ScriptedTurn
from amb.agents.rag_search import run_rag_search
from amb.harness.memory_tool import MemoryToolHarness
from amb.rag import retrieve_topk


def _seed_chunks(tmp_path: Path) -> None:
    h = MemoryToolHarness(tmp_path, role="manage")
    h.execute(
        "create",
        {
            "path": "chunks/chunk_001.md",
            "file_text": (
                "---\nt: 1\ntitle: About me\n---\n"
                "Preferred drink: tea.\nRoommate Jordan Lee.\n"
            ),
        },
    )
    h.execute(
        "create",
        {
            "path": "chunks/chunk_008.md",
            "file_text": (
                "---\nt: 8\ntitle: Preference update\n---\n"
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
                "---\nt: 10\ntitle: Atlas status\n---\n"
                "Atlas API review still owned by Priya.\n"
            ),
        },
    )


def test_retrieve_topk_prefers_drink_update(tmp_path: Path):
    _seed_chunks(tmp_path)
    hits = retrieve_topk(tmp_path, "What does Morgan prefer to drink?", k=2)
    assert hits
    paths = [h["path"] for h in hits]
    assert "chunks/chunk_008.md" in paths


def test_rag_search_mock_answers_from_retrieval(tmp_path: Path):
    _seed_chunks(tmp_path)
    llm = MockLLM(
        [
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
            )
        ]
    )
    payload, steps = run_rag_search(
        llm, tmp_path, "What does Morgan prefer to drink?", top_k=3
    )
    assert payload["answer"] == "coffee"
    assert payload["citations"] == ["chunks/chunk_008.md"]
    assert steps[0]["event"] == "retrieve"
