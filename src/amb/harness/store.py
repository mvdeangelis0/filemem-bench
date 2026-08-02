from __future__ import annotations

import re
from pathlib import Path


AMB_DIR = "_amb"
RESERVED_WRITE_PREFIXES = ("skills/", "policy/", f"{AMB_DIR}/")

# Windows-illegal filename characters (also bad on purpose for portable stores).
_WIN_BAD_CHARS = re.compile(r'[<>:"|?*\x00-\x1f]')
_WIN_RESERVED = {
    "con",
    "prn",
    "aux",
    "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}


def ensure_store(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / AMB_DIR).mkdir(exist_ok=True)
    return root


def canonicalize_rel_path(rel: object) -> tuple[str | None, str | None]:
    """Return (normalized_relative_path, error_message).

    Rejects absolute Windows/Unix paths. Store paths must be relative with `/`.
    Also rejects characters that are illegal on Windows filesystems.
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
    # Lone "/" means store root (models often emit this); other absolutes forbidden.
    if norm == "/":
        return ".", None
    if norm.startswith("/"):
        return None, "absolute paths forbidden; use relative paths like people/morgan.md"
    norm = norm.lstrip("./")
    if norm in ("", "."):
        return ".", None
    parts = Path(norm).parts
    if ".." in parts:
        return None, "path escapes store"
    for part in parts:
        if part in ("", "."):
            continue
        if _WIN_BAD_CHARS.search(part):
            return (
                None,
                "illegal path characters (avoid <>:\"|?* and control chars); "
                "use names like people/morgan.md or notes/sync-2025-03-21.md",
            )
        if part.endswith(" ") or part.endswith("."):
            return None, "path segment cannot end with space or dot"
        stem = part.split(".")[0].casefold()
        if stem in _WIN_RESERVED:
            return None, f"illegal reserved path segment {part!r}"
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
