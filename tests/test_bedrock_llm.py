import json

from amb.agents.llm import (
    BedrockLLM,
    MockLLM,
    ScriptedTurn,
    action_from_model_text,
    normalize_llm_action,
    _parse_json_content,
)
from amb.agents.search import run_search
from amb.harness.memory_tool import MemoryToolHarness


def test_parse_bedrock_fenced_json():
    text = '```json\n{"tool":"view","arguments":{"path":"."}}\n```'
    action = normalize_llm_action(_parse_json_content(text))
    assert action["type"] == "tool_call"
    assert action["tool"] == "view"


def test_extract_tool_from_prose_and_fake_xml():
    text = (
        "I'll search the chunks.\n"
        "<function_calls>\n"
        '[{"tool": "view", "arguments": {"path": "chunks/chunk_001.md"}}]\n'
        "</function_calls>"
    )
    action = action_from_model_text(text)
    assert action["type"] == "tool_call"
    assert action["tool"] == "view"
    assert action["arguments"]["path"] == "chunks/chunk_001.md"


def test_unparseable_is_protocol_error_not_unknown():
    action = action_from_model_text("Sure, let me think about that.")
    assert action["type"] == "protocol_error"
    assert action["error"] == "unparseable_json"


def test_bedrock_message_merge_and_system():
    system, msgs = BedrockLLM._to_bedrock_messages(
        [
            {"role": "system", "content": "sys-a"},
            {"role": "system", "content": "sys-b"},
            {"role": "user", "content": "u1"},
            {"role": "user", "content": "u2"},
            {"role": "assistant", "content": "a1"},
        ]
    )
    assert system == "sys-a\n\nsys-b"
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert "u1" in msgs[0]["content"][0]["text"]
    assert "u2" in msgs[0]["content"][0]["text"]


def test_bedrock_complete_mocked():
    class FakeClient:
        def converse(self, **kwargs):
            assert kwargs["modelId"].startswith("us.anthropic")
            assert kwargs["messages"]
            return {
                "output": {
                    "message": {
                        "content": [
                            {
                                "text": (
                                    '{"tool":"done","arguments":'
                                    '{"answer":"unknown","citations":[]}}'
                                )
                            }
                        ]
                    }
                }
            }

    llm = BedrockLLM(
        "us.anthropic.claude-haiku-4-5-20251001-v1:0",
        region="us-east-1",
        client=FakeClient(),
    )
    out = llm.complete(
        [{"role": "user", "content": "q"}],
        [{"name": "done"}],
    )
    assert out["type"] == "tool_call"
    assert out["tool"] == "done"


def test_search_retries_protocol_error_and_sets_verbatim_shape(tmp_path):
    h = MemoryToolHarness(tmp_path, role="manage")
    h.execute(
        "create",
        {"path": "chunks/chunk_001.md", "file_text": "Preferred drink: tea\n"},
    )
    h.execute(
        "create",
        {
            "path": "chunks/chunk_008.md",
            "file_text": "Update: Morgan now prefers coffee, not tea.\n",
        },
    )
    llm = MockLLM(
        [
            ScriptedTurn(
                {
                    "type": "protocol_error",
                    "error": "unparseable_json",
                    "raw": "I'll help <function_calls>",
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
    assert any(s.get("event") == "protocol_error" for s in steps)
    assert steps[0].get("shape") == "verbatim"
    # First user message after system should carry later-chunk instruction.
    # (exercised via run_search building messages; assert via store_map event)
    assert "chunks/" in json.dumps(steps[0].get("store_map"))
