from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Protocol

import httpx


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


class OllamaLLM:
    def __init__(
        self,
        model: str,
        base_url: str | None = None,
        temperature: float = 0.0,
        timeout: float = 300.0,
    ) -> None:
        self.model = model
        self.base_url = (base_url or os.environ.get("OLLAMA_HOST") or "http://127.0.0.1:11434").rstrip(
            "/"
        )
        self.temperature = temperature
        self.timeout = timeout

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
        with httpx.Client(timeout=self.timeout) as client:
            r = client.post(f"{self.base_url}/api/chat", json=payload)
            r.raise_for_status()
            data = r.json()
        content = data.get("message", {}).get("content", "")
        return normalize_llm_action(_parse_json_content(content) if isinstance(content, str) else content)
