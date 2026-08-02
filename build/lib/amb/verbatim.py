from __future__ import annotations

from pathlib import Path
from typing import Any


def build_verbatim(
    store_root: Path,
    chunks: list[dict[str, Any]],
    whitelist: list[str],
) -> None:
    root = store_root / "chunks"
    root.mkdir(parents=True, exist_ok=True)
    for chunk in chunks:
        cid = chunk["id"]
        header_lines = ["---"]
        for key in whitelist:
            if key == "text":
                continue
            if key in chunk:
                header_lines.append(f"{key}: {chunk[key]}")
        header_lines.append("---")
        header_lines.append("")
        body = chunk.get("text", "")
        (root / f"{cid}.md").write_text(
            "\n".join(header_lines) + body.rstrip() + "\n", encoding="utf-8"
        )
