from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from amb.harness.store import canonicalize_rel_path

ALLOWED_TOOLS = frozenset({
    "lab_sense", "lab_act",
    "view", "create", "str_replace",
    "run_bounded_python",
    "search_allowlisted_web", "fetch_allowlisted_page",
    "defer",
    "done",
})

_FORBIDDEN_PY = ("import os", "import subprocess", "from os", "__import__", "socket", "subprocess")


@dataclass
class PolicyDecision:
    allowed: bool
    reason: str = ""


class Policy:
    def __init__(self, *, web_allowlist: list[str]) -> None:
        self.web_allowlist = [h.lower() for h in web_allowlist]

    def check(self, tool: str, arguments: dict) -> PolicyDecision:
        if tool not in ALLOWED_TOOLS:
            return PolicyDecision(False, f"tool not allowed: {tool}")
        if tool in ("view", "create", "str_replace"):
            path = arguments.get("path") or arguments.get("file_path") or ""
            canon, err = canonicalize_rel_path(path)
            if err or canon is None:
                return PolicyDecision(False, err or "bad path")
            if canon.startswith("inbox_archive/") is False and ".." in str(path):
                return PolicyDecision(False, "path escape")
        if tool == "run_bounded_python":
            code = str(arguments.get("code") or "")
            low = code.lower()
            for bad in _FORBIDDEN_PY:
                if bad in low:
                    return PolicyDecision(False, f"python blocked pattern: {bad}")
        if tool in ("search_allowlisted_web", "fetch_allowlisted_page"):
            if not self.web_allowlist:
                return PolicyDecision(False, "web allowlist empty")
            if tool == "fetch_allowlisted_page":
                url = str(arguments.get("url") or "")
                host = (urlparse(url).hostname or "").lower()
                if host not in self.web_allowlist:
                    return PolicyDecision(False, f"host not allowlisted: {host}")
        return PolicyDecision(True, "")
