"""Deterministic fetch inside a store root (no LLM)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from amb.harness.store import canonicalize_rel_path, resolve_in_store

DEFAULT_BYTE_CAP = 16 * 1024
PLACEHOLDER_CITATIONS = {
    "path.md",
    "path/to document",
    "path/to/document",
    "path_to_roommates.txt",
    "path/to/roommates.txt",
}


class Bookkeeper:
    """Librarian for one store root: list / read / existence checks only."""

    def __init__(self, root: Path, *, byte_cap: int = DEFAULT_BYTE_CAP) -> None:
        self.root = Path(root)
        self.byte_cap = byte_cap

    def exists(self, rel: str) -> bool:
        canon, err = canonicalize_rel_path(rel)
        if err or canon is None:
            return False
        path = resolve_in_store(self.root, canon)
        return path is not None and path.exists()

    def list_dir(self, rel: str = ".") -> dict[str, Any]:
        canon, err = canonicalize_rel_path(rel if rel is not None else ".")
        if err or canon is None:
            return {"ok": False, "error": err}
        path = resolve_in_store(self.root, canon)
        if path is None or not path.exists():
            return {"ok": False, "error": "not found", "path": canon}
        if not path.is_dir():
            return {"ok": False, "error": "not a directory", "path": canon}
        listing = sorted(
            p.name + ("/" if p.is_dir() else "")
            for p in path.iterdir()
            if p.name != "_amb"
        )
        return {"ok": True, "path": canon, "listing": listing}

    def read(self, rel: str) -> dict[str, Any]:
        canon, err = canonicalize_rel_path(rel)
        if err or canon is None:
            return {"ok": False, "error": err}
        path = resolve_in_store(self.root, canon)
        if path is None or not path.exists():
            return {"ok": False, "error": "not found", "path": canon}
        if path.is_dir():
            return self.list_dir(canon)
        data = path.read_text(encoding="utf-8")
        truncated = False
        raw = data.encode("utf-8")
        if len(raw) > self.byte_cap:
            data = raw[: self.byte_cap].decode("utf-8", errors="ignore")
            truncated = True
        return {
            "ok": True,
            "path": canon,
            "content": data,
            "truncated": truncated,
            "bytes": len(raw),
        }

    def brief(self, rel: str) -> dict[str, Any]:
        """Fetch one path into a ledger-friendly brief packet."""
        result = self.read(rel)
        if not result.get("ok"):
            return {
                "ok": False,
                "universe_path": rel,
                "error": result.get("error"),
            }
        return {
            "ok": True,
            "universe_path": result["path"],
            "content": result.get("content"),
            "listing": result.get("listing"),
            "truncated": result.get("truncated", False),
            "citations": [result["path"]] if result.get("content") is not None else [],
        }


def validate_citations(
    root: Path,
    citations: list[Any] | None,
    *,
    answer: str | None = None,
) -> dict[str, Any]:
    """Return ok=False if citations are placeholders or missing on disk.

    Empty citations allowed only when answer looks like an abstain.
    """
    cites = list(citations or [])
    ans = (answer or "").strip().casefold()
    abstain = ans in {"unknown", "n/a", "na", "none", "not found", ""}

    if not cites:
        if abstain:
            return {"ok": True, "citations": []}
        return {
            "ok": False,
            "error": "non-abstain answer requires at least one real citation path",
            "citations": [],
        }

    bk = Bookkeeper(root)
    bad: list[dict[str, str]] = []
    good: list[str] = []
    for c in cites:
        if not isinstance(c, str):
            bad.append({"citation": str(c), "reason": "not a string path"})
            continue
        key = c.replace("\\", "/").strip().casefold()
        if key in PLACEHOLDER_CITATIONS or key.startswith("path/to"):
            bad.append({"citation": c, "reason": "placeholder_citation"})
            continue
        canon, err = canonicalize_rel_path(c)
        if err or canon is None:
            bad.append({"citation": c, "reason": err or "invalid path"})
            continue
        if not bk.exists(canon):
            bad.append({"citation": c, "reason": "not_found"})
            continue
        good.append(canon)

    if bad or not good:
        return {
            "ok": False,
            "error": "citations must be existing relative store paths you viewed",
            "bad": bad,
            "good": good,
        }
    return {"ok": True, "citations": good}
