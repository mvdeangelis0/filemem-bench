from amb.harness.memory_tool import MemoryToolHarness


def test_sandbox_rejects_dotdot(tmp_path):
    h = MemoryToolHarness(tmp_path, role="manage")
    r = h.execute("view", {"path": "../outside"})
    assert r["ok"] is False
    assert r["error_code"] == "path_error"


def test_search_cannot_mutate(tmp_path):
    h = MemoryToolHarness(tmp_path, role="search")
    r = h.execute("create", {"path": "x.md", "file_text": "hi"})
    assert r["ok"] is False
    assert r["error_code"] == "permission_error"


def test_manage_create_view(tmp_path):
    h = MemoryToolHarness(tmp_path, role="manage")
    assert h.execute("create", {"path": "a.md", "file_text": "hello"})["ok"]
    r = h.execute("view", {"path": "a.md"})
    assert r["ok"]
    assert "hello" in r["content"]
