from __future__ import annotations

import json
import os
import re
import sys
import time
from dataclasses import dataclass
from typing import Any, Callable, Protocol

import httpx


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


class LLM(Protocol):
    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        """Return either {type: tool_call, tool, arguments} or {type: final, content/dict}."""
        ...


@dataclass
class ScriptedTurn:
    response: dict[str, Any]


class MockLLM:
    """Deterministic scripted LLM for tests."""

    def __init__(self, turns: list[ScriptedTurn] | None = None) -> None:
        self.turns = list(turns or [])
        self.i = 0

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        if self.i >= len(self.turns):
            return {"type": "final", "content": {"answer": "unknown", "citations": []}}
        turn = self.turns[self.i]
        self.i += 1
        return turn.response


_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


def _parse_json_content(content: str) -> Any:
    text = (content or "").strip()
    if not text:
        return None
    m = _FENCE.search(text)
    if m:
        text = m.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # try first {...} blob
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return None
        return None


def normalize_llm_action(obj: Any) -> dict[str, Any]:
    """Map model JSON into tool_call or final."""
    if obj is None:
        return {"type": "final", "content": {"answer": "unknown", "citations": []}}
    if isinstance(obj, str):
        return {"type": "final", "content": obj}
    if not isinstance(obj, dict):
        return {"type": "final", "content": str(obj)}

    if obj.get("type") == "tool_call" and "tool" in obj:
        return {
            "type": "tool_call",
            "tool": obj["tool"],
            "arguments": obj.get("arguments") or {},
        }
    if "tool" in obj:
        return {
            "type": "tool_call",
            "tool": obj["tool"],
            "arguments": obj.get("arguments") or obj.get("args") or {},
        }
    if "final" in obj:
        return {"type": "final", "content": obj["final"]}
    if "answer" in obj:
        return {"type": "final", "content": obj}
    return {"type": "final", "content": obj}


def probe_ollama(base_url: str, model: str, *, timeout: float = 30.0) -> None:
    """Fail fast if Ollama is down or the model name is missing."""
    base = base_url.rstrip("/")
    _log(f"[amb] probing Ollama at {base} …")
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.get(f"{base}/api/tags")
            r.raise_for_status()
            names = [m.get("name", "") for m in r.json().get("models") or []]
    except httpx.HTTPError as e:
        raise RuntimeError(
            f"Cannot reach Ollama at {base}: {e}. "
            "Is `ollama serve` running? Try: ollama list"
        ) from e
    if model not in names and not any(
        n == model or n.startswith(model + ":") for n in names
    ):
        preview = ", ".join(names[:12]) or "(none)"
        raise RuntimeError(
            f"Model {model!r} not found in Ollama. Installed: {preview}. "
            "Use the exact name from `ollama list`."
        )
    _log(f"[amb] Ollama OK; model {model!r} present ({len(names)} models listed)")


class OllamaLLM:
    def __init__(
        self,
        model: str,
        base_url: str | None = None,
        temperature: float = 0.0,
        timeout: float = 300.0,
        verbose: bool = False,
        on_call: Callable[[str], None] | None = None,
    ) -> None:
        self.model = model
        self.base_url = (base_url or os.environ.get("OLLAMA_HOST") or "http://127.0.0.1:11434").rstrip(
            "/"
        )
        self.temperature = temperature
        self.timeout = timeout
        self.verbose = verbose
        self.on_call = on_call
        self.n_calls = 0

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        # Append a short tool reminder so format=json stays grounded.
        tool_names = ", ".join(t["name"] for t in tools)
        reinforced = list(messages)
        reinforced.append(
            {
                "role": "user",
                "content": (
                    "Reply with a single JSON object only. "
                    f"Either {{\"tool\":\"<one of: {tool_names}>\",\"arguments\":{{...}}}} "
                    "or {\"final\":{...}} / {\"answer\":\"...\",\"citations\":[...]}."
                ),
            }
        )
        payload = {
            "model": self.model,
            "messages": reinforced,
            "stream": False,
            "options": {"temperature": self.temperature},
            "format": "json",
        }
        self.n_calls += 1
        n = self.n_calls
        if self.verbose or self.on_call:
            msg = f"[amb] ollama chat #{n} model={self.model!r} …"
            if self.on_call:
                self.on_call(msg)
            else:
                _log(msg)
        t0 = time.perf_counter()
        try:
            with httpx.Client(timeout=self.timeout) as client:
                r = client.post(f"{self.base_url}/api/chat", json=payload)
                r.raise_for_status()
                data = r.json()
        except httpx.TimeoutException as e:
            raise RuntimeError(
                f"Ollama chat timed out after {self.timeout}s "
                f"(call #{n}, model={self.model!r}). "
                "First load can be slow; GPU idle often means CPU/offload or a hung server."
            ) from e
        except httpx.HTTPError as e:
            raise RuntimeError(
                f"Ollama chat failed (call #{n}, model={self.model!r}): {e}"
            ) from e
        dt = time.perf_counter() - t0
        if self.verbose:
            _log(f"[amb] ollama chat #{n} done in {dt:.1f}s")
        content = data.get("message", {}).get("content", "")
        return normalize_llm_action(
            _parse_json_content(content) if isinstance(content, str) else content
        )
