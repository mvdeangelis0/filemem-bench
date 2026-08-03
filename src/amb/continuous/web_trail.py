from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)


def trail_path(run_dir: Path) -> Path:
    return Path(run_dir) / "memory" / "web_trail.jsonl"


def cursor_path(run_dir: Path) -> Path:
    return Path(run_dir) / "memory" / "web_cursor.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def extract_title(html_or_text: str) -> str:
    m = _TITLE_RE.search(html_or_text or "")
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip()[:200]
    # plain text fallback
    line = (html_or_text or "").strip().splitlines()
    return (line[0][:200] if line else "")


def append_trail(
    run_dir: Path,
    *,
    action: str,
    url: str | None = None,
    query: str | None = None,
    ok: bool = True,
    status_code: int | None = None,
    title: str = "",
    snippet: str = "",
    step: int | None = None,
    note: str = "",
) -> dict[str, Any]:
    """Append a web breadcrumb and update where we left off."""
    row: dict[str, Any] = {
        "ts": _now(),
        "action": action,
        "url": url,
        "query": query,
        "ok": ok,
        "status_code": status_code,
        "title": title,
        "snippet": (snippet or "")[:400],
        "step": step,
        "note": note,
    }
    path = trail_path(run_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")

    cursor = {
        "updated_at": row["ts"],
        "last_action": action,
        "url": url,
        "query": query,
        "title": title,
        "ok": ok,
        "step": step,
        "left_off": (
            f"{action} {url or query or ''} — {title or snippet[:80]}".strip()
        ),
    }
    cursor_path(run_dir).write_text(json.dumps(cursor, indent=2) + "\n", encoding="utf-8")
    return row


def list_trail(run_dir: Path, *, limit: int | None = None) -> list[dict[str, Any]]:
    path = trail_path(run_dir)
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    if limit is not None:
        return rows[-limit:]
    return rows


def read_cursor(run_dir: Path) -> dict[str, Any] | None:
    path = cursor_path(run_dir)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
