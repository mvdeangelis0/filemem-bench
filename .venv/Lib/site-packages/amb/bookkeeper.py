"""Deterministic fetch inside a store root (no LLM)."""

from __future__ import annotations

import re
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

_UPDATE_MARK = re.compile(
    r"(?i)\b(update:|now prefers|no longer|instead of|treat .+ as the current)\b"
)
_FRONT_T = re.compile(r"(?m)^t:\s*(\d+)\s*$")
_FRONT_TITLE = re.compile(r"(?m)^title:\s*(.+)\s*$")
_CHUNK_NUM = re.compile(r"chunk_(\d+)", re.IGNORECASE)

# Too common in this suite / English to use alone for update gating.
_QUERY_STOP = {
    "morgan",
    "jordan",
    "priya",
    "atlas",
    "what",
    "does",
    "this",
    "that",
    "from",
    "with",
    "have",
    "prefer",
    "prefers",
    "preferred",
    "preference",
    "update",
    "updated",
    "current",
    "please",
    "treat",
    "about",
    "where",
    "when",
    "which",
    "who",
    "whom",
    "whose",
    "month",
    "working",
    "works",
}


def _query_tokens(query: str) -> set[str]:
    raw = {t for t in re.findall(r"[a-z0-9]+", (query or "").casefold()) if len(t) >= 4}
    content = {t for t in raw if t not in _QUERY_STOP}
    return content or raw


def _looks_like_update(body: str) -> bool:
    return bool(_UPDATE_MARK.search(body or ""))


def _chunk_t(path: str, body: str) -> int:
    m = _FRONT_T.search(body or "")
    if m:
        return int(m.group(1))
    m = _CHUNK_NUM.search(path.replace("\\", "/"))
    if m:
        return int(m.group(1))
    return 0


def _chunk_title(body: str) -> str | None:
    m = _FRONT_TITLE.search(body or "")
    return m.group(1).strip() if m else None


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

    def chunk_timeline(self) -> list[dict[str, Any]]:
        """Ordered metadata for chunks/ (no full bodies in the returned brief)."""
        listed = self.list_dir("chunks")
        if not listed.get("ok"):
            return []
        rows: list[dict[str, Any]] = []
        for name in listed.get("listing") or []:
            if not isinstance(name, str) or name.endswith("/"):
                continue
            rel = f"chunks/{name}"
            got = self.read(rel)
            if not got.get("ok") or got.get("content") is None:
                continue
            body = str(got["content"])
            rows.append(
                {
                    "path": got["path"],
                    "t": _chunk_t(got["path"], body),
                    "title": _chunk_title(body),
                    "update_flag": _looks_like_update(body),
                }
            )
        rows.sort(key=lambda r: (r["t"], r["path"]))
        return rows

    def later_update_candidates(
        self,
        query: str,
        cited_paths: list[str] | None,
    ) -> list[dict[str, Any]]:
        """Later chunks that look like updates and overlap the query."""
        timeline = self.chunk_timeline()
        if not timeline:
            return []

        cited_t: list[int] = []
        cited_set: set[str] = set()
        for c in cited_paths or []:
            if not isinstance(c, str):
                continue
            canon, err = canonicalize_rel_path(c)
            if err or canon is None:
                continue
            cited_set.add(canon)
            match = next((r for r in timeline if r["path"] == canon), None)
            if match is not None:
                cited_t.append(int(match["t"]))
            else:
                cited_t.append(_chunk_t(canon, ""))

        cited_max_t = max(cited_t) if cited_t else 0
        tokens = _query_tokens(query)
        out: list[dict[str, Any]] = []
        for row in timeline:
            if int(row["t"]) <= cited_max_t:
                continue
            if row["path"] in cited_set:
                continue
            if not row.get("update_flag"):
                continue
            body = str(self.read(row["path"]).get("content") or "").casefold()
            if tokens and not any(tok in body for tok in tokens):
                continue
            out.append(
                {
                    "path": row["path"],
                    "t": row["t"],
                    "title": row.get("title"),
                }
            )
        return out


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


def later_update_gate(
    root: Path,
    query: str,
    *,
    answer: str | None,
    citations: list[Any] | None,
) -> dict[str, Any]:
    """Reject non-abstain answers that ignore later update-like chunks."""
    ans = (answer or "").strip().casefold()
    if ans in {"unknown", "n/a", "na", "none", "not found", ""}:
        return {"ok": True, "candidates": []}
    cites = [c for c in (citations or []) if isinstance(c, str)]
    bk = Bookkeeper(root)
    candidates = bk.later_update_candidates(query, cites)
    if not candidates:
        return {"ok": True, "candidates": []}
    hint_paths = [c["path"] for c in candidates]
    return {
        "ok": False,
        "error_code": "later_update_unchecked",
        "error": "later chunks may supersede your answer; view them before done",
        "hint_paths": hint_paths,
        "candidates": candidates,
    }
