from amb.agents.llm import BedrockLLM, reinforce_tool_json, should_reinforce_tool_json
from amb.usage import estimate_usd


def test_reinforce_still_default_on():
    mid = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "q"},
        {"role": "assistant", "content": '{"tool":"view"}'},
        {"role": "user", "content": '{"observation":{"ok":true}}'},
    ]
    assert should_reinforce_tool_json(mid) is True
    forced_off = reinforce_tool_json(mid, [{"name": "view"}], force=False)
    assert forced_off == mid
    on = reinforce_tool_json(mid, [{"name": "view"}])
    assert len(on) == len(mid) + 1


def test_bedrock_messages_add_cache_point_on_prefix():
    system, msgs = BedrockLLM._to_bedrock_messages(
        [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "u1"},
            {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "u2"},
        ]
    )
    assert system == "sys"
    assert len(msgs) == 3
    # Penultimate message should carry a cachePoint (prefix cache).
    assert any("cachePoint" in b for b in msgs[-2]["content"])
    assert not any("cachePoint" in b for b in msgs[-1]["content"])


def test_estimate_usd_includes_cache():
    est = estimate_usd(
        {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_tokens": 1_000_000,
            "cache_write_tokens": 0,
        },
        model_id="haiku",
    )
    assert est["ok"] is True
    assert est["usd"] == 0.1
