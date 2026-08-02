from __future__ import annotations

import json
import os
import re
import sys
import threading
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


def reinforce_tool_json(
    messages: list[dict[str, Any]], tools: list[dict[str, Any]]
) -> list[dict[str, Any]]:
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
    return reinforced


def _log_action(prefix: str, n: int, dt: float, action: dict[str, Any], content: str, verbose: bool) -> None:
    if action.get("type") == "tool_call":
        detail = f"tool={action.get('tool')!r}"
    else:
        detail = "final"
    _log(f"[amb] {prefix} #{n} done in {dt:.1f}s → {detail}")
    if verbose and content.strip():
        preview = content.strip().replace("\n", " ")
        if len(preview) > 160:
            preview = preview[:160] + "…"
        _log(f"[amb] {prefix} #{n} preview: {preview}")


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
        reinforced = reinforce_tool_json(messages, tools)
        payload = {
            "model": self.model,
            "messages": reinforced,
            "stream": False,
            "options": {"temperature": self.temperature},
            "format": "json",
        }
        self.n_calls += 1
        n = self.n_calls
        msg = f"[amb] ollama chat #{n} model={self.model!r} waiting (GPU util drops between calls) …"
        if self.on_call:
            self.on_call(msg)
        else:
            _log(msg)
        t0 = time.perf_counter()
        stop_hb = threading.Event()

        def _heartbeat() -> None:
            while not stop_hb.wait(5.0):
                _log(
                    f"[amb] … still waiting on ollama chat #{n} "
                    f"({time.perf_counter() - t0:.0f}s)"
                )

        hb = threading.Thread(target=_heartbeat, name=f"ollama-hb-{n}", daemon=True)
        hb.start()
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
        finally:
            stop_hb.set()
            hb.join(timeout=0.2)
        dt = time.perf_counter() - t0
        content = data.get("message", {}).get("content", "")
        if not isinstance(content, str):
            content = json.dumps(content)
        action = normalize_llm_action(_parse_json_content(content))
        _log_action("ollama chat", n, dt, action, content, self.verbose)
        return action


def probe_bedrock(model: str, *, region: str | None = None) -> None:
    """Fail fast if boto3/credentials/region cannot reach bedrock-runtime."""
    try:
        import boto3
        from botocore.exceptions import BotoCoreError, ClientError
    except ImportError as e:
        raise RuntimeError(
            "bedrock mode requires boto3. Install with: pip install -e '.[bedrock]'"
        ) from e
    region = region or os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"
    _log(f"[amb] probing Bedrock runtime region={region} model={model!r} …")
    client = boto3.client("bedrock-runtime", region_name=region)
    try:
        # Cheap no-op auth/region check; model access validated on first converse.
        client.meta.events
        sts = boto3.client("sts", region_name=region)
        ident = sts.get_caller_identity()
    except (BotoCoreError, ClientError) as e:
        raise RuntimeError(f"Cannot use AWS/Bedrock in {region}: {e}") from e
    _log(
        f"[amb] Bedrock OK; account={ident.get('Account')} "
        f"model_id={model!r} (use inference profile ids like "
        f"us.anthropic.claude-haiku-4-5-20251001-v1:0)"
    )


class BedrockLLM:
    """AWS Bedrock Converse API → same JSON tool protocol as OllamaLLM."""

    def __init__(
        self,
        model: str,
        *,
        region: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
        verbose: bool = False,
        client: Any | None = None,
    ) -> None:
        self.model = model
        self.region = (
            region
            or os.environ.get("AWS_REGION")
            or os.environ.get("AWS_DEFAULT_REGION")
            or "us-east-1"
        )
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.verbose = verbose
        self.n_calls = 0
        if client is not None:
            self._client = client
        else:
            try:
                import boto3
            except ImportError as e:
                raise RuntimeError(
                    "bedrock mode requires boto3. Install with: pip install -e '.[bedrock]'"
                ) from e
            self._client = boto3.client("bedrock-runtime", region_name=self.region)

    @staticmethod
    def _to_bedrock_messages(
        messages: list[dict[str, Any]],
    ) -> tuple[str | None, list[dict[str, Any]]]:
        system_parts: list[str] = []
        out: list[dict[str, Any]] = []
        for m in messages:
            role = m.get("role") or "user"
            content = m.get("content")
            if not isinstance(content, str):
                content = json.dumps(content, ensure_ascii=False)
            if role == "system":
                system_parts.append(content)
                continue
            if role not in {"user", "assistant"}:
                role = "user"
            # Bedrock requires alternating roles; merge consecutive same-role turns.
            if out and out[-1]["role"] == role:
                prev = out[-1]["content"][0]["text"]
                out[-1]["content"][0]["text"] = prev + "\n\n" + content
            else:
                out.append({"role": role, "content": [{"text": content}]})
        system = "\n\n".join(system_parts) if system_parts else None
        return system, out

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        from botocore.exceptions import BotoCoreError, ClientError

        reinforced = reinforce_tool_json(messages, tools)
        system, br_messages = self._to_bedrock_messages(reinforced)
        self.n_calls += 1
        n = self.n_calls
        _log(f"[amb] bedrock converse #{n} model={self.model!r} …")
        t0 = time.perf_counter()
        kwargs: dict[str, Any] = {
            "modelId": self.model,
            "messages": br_messages,
            "inferenceConfig": {
                "maxTokens": self.max_tokens,
                "temperature": self.temperature,
            },
        }
        if system:
            kwargs["system"] = [{"text": system}]
        try:
            resp = self._client.converse(**kwargs)
        except (BotoCoreError, ClientError) as e:
            raise RuntimeError(
                f"Bedrock converse failed (call #{n}, model={self.model!r}): {e}. "
                "Newer Claude models need an inference profile id "
                "(e.g. us.anthropic.claude-haiku-4-5-20251001-v1:0)."
            ) from e
        dt = time.perf_counter() - t0
        chunks = (((resp.get("output") or {}).get("message") or {}).get("content")) or []
        content = "".join(c.get("text", "") for c in chunks if isinstance(c, dict))
        action = normalize_llm_action(_parse_json_content(content))
        _log_action("bedrock converse", n, dt, action, content, self.verbose)
        return action
