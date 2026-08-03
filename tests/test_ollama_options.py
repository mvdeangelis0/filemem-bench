from amb.agents.llm import OllamaLLM


def test_ollama_payload_includes_speed_options(monkeypatch):
    captured: dict = {}

    class FakeResp:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"message": {"content": '{"tool":"lab_sense","arguments":{}}'}}

    class FakeClient:
        def __init__(self, *a, **k):  # noqa: ANN001
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):  # noqa: ANN001
            return False

        def post(self, url, json=None):  # noqa: ANN001
            captured["url"] = url
            captured["json"] = json
            return FakeResp()

    monkeypatch.setattr("amb.agents.llm.httpx.Client", FakeClient)
    llm = OllamaLLM(
        "qwen2.5:7b",
        base_url="http://127.0.0.1:11434",
        num_ctx=4096,
        num_predict=512,
        keep_alive="30m",
    )
    out = llm.complete([{"role": "user", "content": "x"}], [{"name": "lab_sense"}])
    assert out["type"] == "tool_call"
    opts = captured["json"]["options"]
    assert opts["num_ctx"] == 4096
    assert opts["num_predict"] == 512
    assert captured["json"]["keep_alive"] == "30m"


def test_session_set_num_ctx():
    from amb.continuous.console import Session, dispatch_line

    session = Session()
    assert session.num_ctx == 4096
    assert dispatch_line(session, "/set num_ctx 8192") is True
    assert session.num_ctx == 8192
    assert dispatch_line(session, "/set num_predict none") is True
    assert session.num_predict is None
    assert dispatch_line(session, "/set keep_alive -1") is True
    assert session.keep_alive == "-1"
