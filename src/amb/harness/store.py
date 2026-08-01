from __future__ import annotations

from pathlib import Path


AMB_DIR = "_amb"
RESERVED_WRITE_PREFIXES = ("skills/", "policy/", f"{AMB_DIR}/")


def ensure_store(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / AMB_DIR).mkdir(exist_ok=True)
    return root


def resolve_in_store(root: Path, rel: str) -> Path | None:
    """Return resolved path if inside root; None if escape attempt."""
    if rel is None:
        return None
    rel = rel.replace("\\", "/").lstrip("/")
    if rel in ("", "."):
        return root.resolve()
    if ".." in Path(rel).parts:
        return None
    candidate = (root / rel).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None
    return candidate


def is_write_reserved(rel: str) -> bool:
    norm = rel.replace("\\", "/").lstrip("/")
    return any(norm == p.rstrip("/") or norm.startswith(p) for p in RESERVED_WRITE_PREFIXES)
