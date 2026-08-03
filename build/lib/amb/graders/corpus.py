from __future__ import annotations

from pathlib import Path


def build_corpus(store_root: Path) -> tuple[str, dict[str, str]]:
    bodies: dict[str, str] = {}
    parts: list[str] = []
    if not store_root.exists():
        return "", bodies
    for path in sorted(store_root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(store_root).as_posix()
        if rel.startswith("_amb/") or "/_amb/" in rel:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        bodies[rel] = text
        parts.append(f"{rel}\n{text}\n\n")
    return "".join(parts), bodies


def first_matching_path(bodies: dict[str, str], predicate) -> str | None:
    for rel in sorted(bodies):
        if predicate(bodies[rel]):
            return rel
    return None
