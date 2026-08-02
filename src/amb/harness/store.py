from __future__ import annotations

from pathlib import Path


AMB_DIR = "_amb"
RESERVED_WRITE_PREFIXES = ("skills/", "policy/", f"{AMB_DIR}/")


def ensure_store(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / AMB_DIR).mkdir(exist_ok=True)
    return root


def canonicalize_rel_path(rel: object) -> tuple[str | None, str | None]:
    """Return (normalized_relative_path, error_message).

    Rejects absolute Windows/Unix paths. Store paths must be relative with `/`.
    """
    if rel is None:
        return None, "missing path (use a relative path like people/morgan.md)"
    if not isinstance(rel, str):
        rel = str(rel)
    raw = rel.strip()
    if not raw:
        return None, "empty path (use a relative path like people/morgan.md)"
    norm = raw.replace("\\", "/")
    # Windows drive / UNC
    if len(norm) >= 2 and norm[1] == ":":
        return None, "absolute paths forbidden; use relative paths like people/morgan.md"
    if norm.startswith("//"):
        return None, "absolute paths forbidden; use relative paths like people/morgan.md"
    # Unix absolute
    if norm.startswith("/"):
        return None, "absolute paths forbidden; use relative paths like people/morgan.md"
    norm = norm.lstrip("./")
    if norm in ("", "."):
        return ".", None
    if ".." in Path(norm).parts:
        return None, "path escapes store"
    return norm, None


def resolve_in_store(root: Path, rel: str) -> Path | None:
    """Return resolved path if inside root; None if escape attempt."""
    canon, err = canonicalize_rel_path(rel)
    if canon is None or err:
        return None
    if canon == ".":
        return root.resolve()
    candidate = (root / canon).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None
    return candidate


def is_write_reserved(rel: str) -> bool:
    canon, err = canonicalize_rel_path(rel)
    if canon is None or err or canon == ".":
        return False
    return any(canon == p.rstrip("/") or canon.startswith(p) for p in RESERVED_WRITE_PREFIXES)
