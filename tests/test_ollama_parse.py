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


def test_unwrap_nested_tool_call_object():
    # Seen in continuous desktop traces (extra wrapper).
    act = action_from_model_text(
        '{"tool_call": {"tool": "lab_sense", "arguments": {"temperature": 25.0}}}'
    )
    assert act["type"] == "tool_call"
    assert act["tool"] == "lab_sense"
    assert act["arguments"]["temperature"] == 25.0


def test_unwrap_string_tool_call():
    act = action_from_model_text('{"tool_call": "lab_sense"}')
    assert act["type"] == "tool_call"
    assert act["tool"] == "lab_sense"
    assert act["arguments"] == {}


def test_coerce_arguments_list_of_dict():
    act = normalize_llm_action(
        {
            "tool": "defer",
            "arguments": [{"task": "x", "reason": "y", "need": "web"}],
        }
    )
    assert act["type"] == "tool_call"
    assert act["tool"] == "defer"
    assert act["arguments"]["task"] == "x"


def test_bad_arguments_list_is_protocol_error():
    act = normalize_llm_action({"tool": "defer", "arguments": ["not", "a", "dict"]})
    assert act["type"] == "protocol_error"
    assert act["error"] == "arguments_not_object"
