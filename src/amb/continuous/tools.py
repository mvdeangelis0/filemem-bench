from __future__ import annotations

import io
import math
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from amb.continuous.deferred import append_deferred, infer_need_from_policy
from amb.continuous.policy import Policy
from amb.harness.store import canonicalize_rel_path, resolve_in_store

_PY_TIMEOUT_S = 2.0
_PY_OUTPUT_CAP = 8 * 1024
_WEB_TIMEOUT_S = 5.0
_WEB_OUTPUT_CAP = 32 * 1024
_SAFE_BUILTINS = {
    "abs": abs,
    "min": min,
    "max": max,
    "range": range,
    "len": len,
    "float": float,
    "int": int,
    "print": print,
    "str": str,
    "bool": bool,
    "list": list,
    "dict": dict,
    "round": round,
}


def _run_python_code(code: str) -> dict[str, Any]:
    stdout = io.StringIO()

    def _target() -> dict[str, Any]:
        import builtins as _bi

        def _print(*args: Any, **kwargs: Any) -> None:
            kwargs = dict(kwargs)
            kwargs["file"] = stdout
            _bi.print(*args, **kwargs)

        env: dict[str, Any] = {
            "__builtins__": {**_SAFE_BUILTINS, "print": _print},
            "math": math,
            "result": None,
        }
        exec(code, env, env)  # noqa: S102 — intentionally bounded sandbox
        out = stdout.getvalue()
        if len(out) > _PY_OUTPUT_CAP:
            out = out[:_PY_OUTPUT_CAP] + "\n...[truncated]"
        return {"ok": True, "result": env.get("result"), "stdout": out}

    with ThreadPoolExecutor(max_workers=1) as pool:
        fut = pool.submit(_target)
        try:
            return fut.result(timeout=_PY_TIMEOUT_S)
        except FuturesTimeout:
            return {
                "ok": False,
                "error_code": "timeout",
                "error": f"python exceeded {_PY_TIMEOUT_S}s",
            }
        except Exception as e:  # noqa: BLE001 — surface to agent
            return {"ok": False, "error_code": "python_error", "error": str(e)}


class ToolRuntime:
    """Policy-gated tools bound to a continuous run directory."""

    def __init__(self, run_dir: Path, *, world: Any, policy: Policy) -> None:
        self.run_dir = Path(run_dir)
        self.world = world
        self.policy = policy

    def execute(self, tool: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        arguments = dict(arguments or {})
        decision = self.policy.check(tool, arguments)
        if not decision.allowed:
            need = infer_need_from_policy(tool, decision.reason)
            row = append_deferred(
                self.run_dir,
                task=f"Attempted {tool}: {arguments!r}"[:400],
                reason=decision.reason,
                need=need,
                source="policy",
                tool=tool,
            )
            return {
                "ok": False,
                "error_code": "policy_denied",
                "error": decision.reason,
                "deferred": row,
            }
        handlers = {
            "view": self._view,
            "create": self._create,
            "str_replace": self._str_replace,
            "lab_sense": self._lab_sense,
            "lab_act": self._lab_act,
            "run_bounded_python": self._run_bounded_python,
            "search_allowlisted_web": self._search_web,
            "fetch_allowlisted_page": self._fetch_page,
            "defer": self._defer,
            "done": self._done,
        }
        handler = handlers.get(tool)
        if handler is None:
            return {
                "ok": False,
                "error_code": "protocol_error",
                "error": f"unknown tool {tool!r}",
            }
        try:
            return handler(arguments)
        except OSError as e:
            return {"ok": False, "error_code": "os_error", "error": str(e)}

    def _resolve(self, rel: object) -> tuple[Path | None, str | None]:
        canon, err = canonicalize_rel_path(rel)
        if err or canon is None:
            return None, err or "bad path"
        path = resolve_in_store(self.run_dir, canon)
        if path is None:
            return None, "path escape"
        return path, None

    def _view(self, args: dict[str, Any]) -> dict[str, Any]:
        path, err = self._resolve(args.get("path") or args.get("file_path"))
        if path is None:
            return {"ok": False, "error_code": "path_error", "error": err}
        if path.is_dir():
            names = sorted(p.name for p in path.iterdir())
            return {"ok": True, "content": "\n".join(names)}
        if not path.exists():
            return {"ok": False, "error_code": "not_found", "error": "file not found"}
        text = path.read_text(encoding="utf-8")
        return {"ok": True, "content": text}

    def _create(self, args: dict[str, Any]) -> dict[str, Any]:
        path, err = self._resolve(args.get("path") or args.get("file_path"))
        if path is None:
            return {"ok": False, "error_code": "path_error", "error": err}
        if path.exists():
            return {"ok": False, "error_code": "exists", "error": "file already exists"}
        path.parent.mkdir(parents=True, exist_ok=True)
        text = str(
            args.get("file_text")
            if args.get("file_text") is not None
            else args.get("content") or ""
        )
        path.write_text(text, encoding="utf-8")
        return {"ok": True, "path": str(path.relative_to(self.run_dir)).replace("\\", "/")}

    def _str_replace(self, args: dict[str, Any]) -> dict[str, Any]:
        path, err = self._resolve(args.get("path") or args.get("file_path"))
        if path is None:
            return {"ok": False, "error_code": "path_error", "error": err}
        if not path.is_file():
            return {"ok": False, "error_code": "not_found", "error": "file not found"}
        old = str(args.get("old_str") or args.get("old_string") or "")
        new = str(args.get("new_str") or args.get("new_string") or "")
        text = path.read_text(encoding="utf-8")
        if old not in text:
            return {"ok": False, "error_code": "no_match", "error": "old_str not found"}
        path.write_text(text.replace(old, new, 1), encoding="utf-8")
        return {"ok": True}

    def _lab_sense(self, _args: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True, "result": self.world.sense(), "informative": True}

    def _lab_act(self, args: dict[str, Any]) -> dict[str, Any]:
        out = self.world.act(args)
        return {
            "ok": bool(out.get("ok", True)),
            "result": out.get("state") or out,
            "informative": bool(out.get("informative", True)),
        }

    def _run_bounded_python(self, args: dict[str, Any]) -> dict[str, Any]:
        code = str(args.get("code") or "")
        if not code.strip():
            return {"ok": False, "error_code": "empty_code", "error": "missing code"}
        return _run_python_code(code)

    def _search_web(self, args: dict[str, Any]) -> dict[str, Any]:
        q = str(args.get("query") or "")
        hosts = list(self.policy.web_allowlist)
        return {
            "ok": True,
            "result": {
                "query": q,
                "hosts": hosts,
                "note": "v1 search returns allowlisted hosts only; use fetch_allowlisted_page",
            },
        }

    def _fetch_page(self, args: dict[str, Any]) -> dict[str, Any]:
        url = str(args.get("url") or "")
        host = (urlparse(url).hostname or "").lower()
        if host not in self.policy.web_allowlist:
            return {
                "ok": False,
                "error_code": "policy_denied",
                "error": f"host not allowlisted: {host}",
            }
        try:
            with httpx.Client(timeout=_WEB_TIMEOUT_S, follow_redirects=True) as client:
                resp = client.get(url)
            text = resp.text
            if len(text) > _WEB_OUTPUT_CAP:
                text = text[:_WEB_OUTPUT_CAP] + "\n...[truncated]"
            return {
                "ok": resp.is_success,
                "status_code": resp.status_code,
                "content": text,
            }
        except httpx.HTTPError as e:
            return {"ok": False, "error_code": "http_error", "error": str(e)}

    def _done(self, args: dict[str, Any]) -> dict[str, Any]:
        return {
            "ok": True,
            "done": True,
            "summary": str(args.get("summary") or ""),
        }

    def _defer(self, args: dict[str, Any]) -> dict[str, Any]:
        task = str(args.get("task") or args.get("description") or "").strip()
        if not task:
            return {
                "ok": False,
                "error_code": "missing_task",
                "error": "defer requires task text",
            }
        reason = str(args.get("reason") or "out of current capabilities")
        need = str(args.get("need") or "capability")
        row = append_deferred(
            self.run_dir,
            task=task,
            reason=reason,
            need=need,
            source="agent",
            tool="defer",
        )
        return {"ok": True, "deferred": row, "informative": True}
