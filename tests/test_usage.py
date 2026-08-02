from amb.agents.llm import BedrockLLM
from amb.usage import build_run_usage, estimate_usd, prices_for_model


def test_bedrock_complete_records_usage():
    class FakeClient:
        def converse(self, **kwargs):
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
                },
                "usage": {"inputTokens": 123, "outputTokens": 45},
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
    assert llm.n_calls == 1
    assert llm.input_tokens == 123
    assert llm.output_tokens == 45
    snap = llm.usage_dict()
    assert snap["input_tokens"] == 123
    assert "haiku" in snap["model_id"]


def test_estimate_usd_haiku():
    prices = prices_for_model("bedrock/us.anthropic.claude-haiku-4-5")
    assert prices == (1.0, 5.0)
    est = estimate_usd(
        {"input_tokens": 1_000_000, "output_tokens": 1_000_000},
        model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0",
    )
    assert est["ok"] is True
    assert est["usd"] == 6.0


def test_build_run_usage_merges_roles():
    usage = build_run_usage(
        manage={
            "n_calls": 2,
            "input_tokens": 100,
            "output_tokens": 10,
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
            "model_id": "bedrock/haiku",
        },
        search={
            "n_calls": 3,
            "input_tokens": 200,
            "output_tokens": 20,
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
            "model_id": "bedrock/haiku",
        },
        llm_mode="bedrock",
    )
    assert usage["total"]["n_calls"] == 5
    assert usage["total"]["input_tokens"] == 300
    assert usage["estimate"]["ok"] is True
