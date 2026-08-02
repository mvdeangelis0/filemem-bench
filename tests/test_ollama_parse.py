from amb.agents.llm import action_from_model_text, normalize_llm_action, _parse_json_content


def test_parse_fenced_tool_json():
    raw = """```json
{"tool":"view","arguments":{"path":"."}}
```"""
    obj = _parse_json_content(raw)
    act = normalize_llm_action(obj)
    assert act["type"] == "tool_call"
    assert act["tool"] == "view"


def test_parse_final_answer():
    act = normalize_llm_action({"answer": "coffee", "citations": ["memory.md"]})
    assert act["type"] == "final"
    assert act["content"]["answer"] == "coffee"


def test_empty_parse_is_protocol_error():
    act = action_from_model_text("")
    assert act["type"] == "protocol_error"
