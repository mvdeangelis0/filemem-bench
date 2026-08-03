from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


def inject(run_dir: Path, text: str) -> None:
    path = Path(run_dir) / "INBOX.md"
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    chunk = text.strip()
    if not chunk:
        return
    sep = "\n" if existing and not existing.endswith("\n") else ""
    path.write_text(existing + sep + chunk + "\n", encoding="utf-8")


def consume_inbox(run_dir: Path) -> str:
    path = Path(run_dir) / "INBOX.md"
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    stripped = text.strip()
    if not stripped:
        return ""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    arch = Path(run_dir) / "inbox_archive" / f"{ts}.md"
    arch.write_text(stripped + "\n", encoding="utf-8")
    path.write_text("", encoding="utf-8")
    return stripped
