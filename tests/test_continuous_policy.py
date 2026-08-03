from amb.continuous.policy import Policy, PolicyDecision


def test_allows_known_tools():
    p = Policy(web_allowlist=[])
    d = p.check("lab_sense", {})
    assert d.allowed
    d2 = p.check("view", {"path": "memory/lessons.md"})
    assert d2.allowed


def test_denies_unknown_and_shellish():
    p = Policy(web_allowlist=[])
    assert not p.check("bash", {"cmd": "ls"}).allowed
    assert not p.check("run_bounded_python", {"code": "import os; os.system('x')"}).allowed


def test_web_denied_when_allowlist_empty():
    p = Policy(web_allowlist=[])
    d = p.check("fetch_allowlisted_page", {"url": "https://example.com"})
    assert not d.allowed


def test_web_allowed_when_host_listed():
    p = Policy(web_allowlist=["example.com"])
    d = p.check("fetch_allowlisted_page", {"url": "https://example.com/a"})
    assert d.allowed


def test_path_escape_denied():
    p = Policy(web_allowlist=[])
    assert not p.check("view", {"path": "../secrets"}).allowed
