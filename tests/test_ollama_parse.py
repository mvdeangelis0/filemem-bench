from amb.agents.llm import normalize_llm_action, _parse_json_content


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
