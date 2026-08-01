from __future__ import annotations

from pathlib import Path
from typing import Any

from amb.harness.store import ensure_store, is_write_reserved, resolve_in_store

MUTATING = {"create", "str_replace", "insert", "delete", "rename"}
DEFAULT_VIEW_LIMIT = 32 * 1024


class MemoryToolHarness:
    def __init__(
        self,
        root: Path,
        *,
        role: str = "manage",
        view_limit: int = DEFAULT_VIEW_LIMIT,
    ) -> None:
        self.root = ensure_store(Path(root))
        self.role = role
        self.view_limit = view_limit

    def execute(self, tool: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        arguments = arguments or {}
        if tool in MUTATING and self.role == "search":
            return {
                "ok": False,
                "error_code": "permission_error",
                "error": "search role cannot mutate store",
            }
        handlers = {
            "view": self._view,
            "create": self._create,
            "str_replace": self._str_replace,
            "insert": self._insert,
            "delete": self._delete,
            "rename": self._rename,
            "done": self._done,
        }
        if tool not in handlers:
            return {"ok": False, "error_code": "protocol_error", "error": f"unknown tool {tool}"}
        return handlers[tool](arguments)

    def _path(self, rel: str) -> Path | None:
        return resolve_in_store(self.root, rel)

    def _view(self, args: dict[str, Any]) -> dict[str, Any]:
        rel = args.get("path", ".")
        path = self._path(rel)
        if path is None:
            return {"ok": False, "error_code": "path_error", "error": "path escapes store"}
        if not path.exists():
            return {"ok": False, "error_code": "path_error", "error": "not found", "path": rel}
        if path.is_dir():
            listing = sorted(
                p.name + ("/" if p.is_dir() else "")
                for p in path.iterdir()
                if p.name != "_amb"
            )
            return {"ok": True, "tool": "view", "path": rel, "listing": listing}
        data = path.read_text(encoding="utf-8")
        truncated = False
        if len(data.encode("utf-8")) > self.view_limit:
            data = data.encode("utf-8")[: self.view_limit].decode("utf-8", errors="ignore")
            truncated = True
        return {
            "ok": True,
            "tool": "view",
            "path": rel,
            "content": data,
            "truncated": truncated,
        }

    def _create(self, args: dict[str, Any]) -> dict[str, Any]:
        rel = args.get("path", "")
        if is_write_reserved(rel):
            return {"ok": False, "error_code": "permission_error", "error": "reserved path"}
        path = self._path(rel)
        if path is None:
            return {"ok": False, "error_code": "path_error", "error": "path escapes store"}
        if path.exists():
            return {"ok": False, "error_code": "path_error", "error": "already exists"}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(args.get("file_text", args.get("content", "")), encoding="utf-8")
        return {"ok": True, "tool": "create", "path": rel}

    def _str_replace(self, args: dict[str, Any]) -> dict[str, Any]:
        rel = args.get("path", "")
        if is_write_reserved(rel):
            return {"ok": False, "error_code": "permission_error", "error": "reserved path"}
        path = self._path(rel)
        if path is None or not path.is_file():
            return {"ok": False, "error_code": "path_error", "error": "not a file"}
        old = args.get("old_str", "")
        new = args.get("new_str", "")
        text = path.read_text(encoding="utf-8")
        if old not in text:
            return {"ok": False, "error_code": "path_error", "error": "old_str not found"}
        path.write_text(text.replace(old, new, 1), encoding="utf-8")
        return {"ok": True, "tool": "str_replace", "path": rel}

    def _insert(self, args: dict[str, Any]) -> dict[str, Any]:
        rel = args.get("path", "")
        if is_write_reserved(rel):
            return {"ok": False, "error_code": "permission_error", "error": "reserved path"}
        path = self._path(rel)
        if path is None or not path.is_file():
            return {"ok": False, "error_code": "path_error", "error": "not a file"}
        insert_line = int(args.get("insert_line", 1))
        new_str = args.get("new_str", "")
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        idx = max(0, min(len(lines), insert_line - 1))
        lines.insert(idx, new_str if new_str.endswith("\n") else new_str + "\n")
        path.write_text("".join(lines), encoding="utf-8")
        return {"ok": True, "tool": "insert", "path": rel}

    def _delete(self, args: dict[str, Any]) -> dict[str, Any]:
        rel = args.get("path", "")
        if is_write_reserved(rel):
            return {"ok": False, "error_code": "permission_error", "error": "reserved path"}
        path = self._path(rel)
        if path is None or not path.exists():
            return {"ok": False, "error_code": "path_error", "error": "not found"}
        if path.is_dir():
            try:
                path.rmdir()
            except OSError as e:
                return {"ok": False, "error_code": "path_error", "error": str(e)}
        else:
            path.unlink()
        return {"ok": True, "tool": "delete", "path": rel}

    def _rename(self, args: dict[str, Any]) -> dict[str, Any]:
        old_rel = args.get("old_path") or args.get("path", "")
        new_rel = args.get("new_path") or args.get("new_name", "")
        if is_write_reserved(old_rel) or is_write_reserved(new_rel):
            return {"ok": False, "error_code": "permission_error", "error": "reserved path"}
        old = self._path(old_rel)
        new = self._path(new_rel)
        if old is None or new is None:
            return {"ok": False, "error_code": "path_error", "error": "path escapes store"}
        if not old.exists():
            return {"ok": False, "error_code": "path_error", "error": "not found"}
        new.parent.mkdir(parents=True, exist_ok=True)
        old.rename(new)
        return {"ok": True, "tool": "rename", "old_path": old_rel, "new_path": new_rel}

    def _done(self, args: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True, "tool": "done", "final": args}
