from amb.agents.llm import BedrockLLM, normalize_llm_action, _parse_json_content


def test_parse_bedrock_fenced_json():
    text = '```json\n{"tool":"view","arguments":{"path":"."}}\n```'
    action = normalize_llm_action(_parse_json_content(text))
    assert action["type"] == "tool_call"
    assert action["tool"] == "view"


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
