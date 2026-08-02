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


def test_create_requires_path(tmp_path):
    h = MemoryToolHarness(tmp_path, role="manage")
    r = h.execute("create", {"file_text": "hello"})
    assert r["ok"] is False
    assert "relative path" in r["error"]


def test_rejects_windows_absolute_path(tmp_path):
    h = MemoryToolHarness(tmp_path, role="manage")
    r = h.execute(
        "create",
        {"path": r"C:\Users\user\store\people\morgan.md", "file_text": "x"},
    )
    assert r["ok"] is False
    assert "absolute" in r["error"]


def test_unknown_tool_lists_allowed(tmp_path):
    h = MemoryToolHarness(tmp_path, role="manage")
    r = h.execute("rm", {"path": "a.md"})
    assert r["ok"] is False
    assert r["error_code"] == "protocol_error"
    assert "view" in r["error"]
