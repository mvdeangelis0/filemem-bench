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
# Prefer an embedded tool object even when wrapped in prose / fake XML.
_TOOL_OBJ = re.compile(
    r"\{\s*\"(?:type\"\s*:\s*\"tool_call\"\s*,\s*\")?tool\"\s*:\s*\"[^\"]+\"[\s\S]*?\}",
    re.IGNORECASE,
)


def _loads_object(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _extract_tool_dict(text: str) -> dict[str, Any] | None:
    """Find the first JSON object that looks like a tool call."""
    for m in _TOOL_OBJ.finditer(text):
        candidate = m.group(0)
        # Expand to balanced braces from the match start (regex may truncate).
        start = m.start()
        depth = 0
        end = None
        for i, ch in enumerate(text[start:], start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end is None:
            obj = _loads_object(candidate)
        else:
            obj = _loads_object(text[start:end])
        if isinstance(obj, dict) and "tool" in obj:
            return obj
        if isinstance(obj, list):
            for item in obj:
                if isinstance(item, dict) and "tool" in item:
                    return item
    # Arrays of tool calls: [{"tool":...}]
    start = text.find("[")
    end = text.rfind("]")
    if start >= 0 and end > start:
        arr = _loads_object(text[start : end + 1])
        if isinstance(arr, list):
            for item in arr:
                if isinstance(item, dict) and "tool" in item:
                    return item
    return None


def _parse_json_content(content: str) -> Any:
    text = (content or "").strip()
    if not text:
        return None
    m = _FENCE.search(text)
    if m:
        fenced = m.group(1).strip()
        obj = _loads_object(fenced)
        if obj is not None:
            if isinstance(obj, list):
                for item in obj:
                    if isinstance(item, dict) and "tool" in item:
                        return item
            return obj
        tool = _extract_tool_dict(fenced)
        if tool is not None:
            return tool
    obj = _loads_object(text)
    if obj is not None:
        if isinstance(obj, list):
            for item in obj:
                if isinstance(item, dict) and "tool" in item:
                    return item
        return obj
    tool = _extract_tool_dict(text)
    if tool is not None:
        return tool
    # Last resort: outermost {...} blob
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return _loads_object(text[start : end + 1])
    return None


def _coerce_tool_arguments(raw: Any) -> tuple[dict[str, Any] | None, str | None]:
    """Normalize tool arguments to a dict. Accept a single-element list of dict."""
    if raw is None:
        return {}, None
    if isinstance(raw, dict):
        return dict(raw), None
    if isinstance(raw, list):
        if not raw:
            return {}, None
        if isinstance(raw[0], dict):
            return dict(raw[0]), None
        return None, "arguments_not_object"
    return None, "arguments_not_object"


def _tool_call_action(tool: Any, arguments: Any, *, raw: str | None) -> dict[str, Any]:
    name = str(tool or "").strip()
    if not name:
        return {
            "type": "protocol_error",
            "error": "missing_tool_or_answer",
            "raw": (raw or "")[:500],
        }
    args, err = _coerce_tool_arguments(arguments)
    if err or args is None:
        return {
            "type": "protocol_error",
            "error": err or "arguments_not_object",
            "raw": (raw or json.dumps({"tool": name, "arguments": arguments}, ensure_ascii=False))[
                :500
            ],
        }
    return {"type": "tool_call", "tool": name, "arguments": args}


def normalize_llm_action(obj: Any, *, raw: str | None = None) -> dict[str, Any]:
    """Map model JSON into tool_call, final, or protocol_error."""
    if obj is None:
        return {
            "type": "protocol_error",
            "error": "unparseable_json",
            "raw": (raw or "")[:500],
        }
    if isinstance(obj, str):
        return {
            "type": "protocol_error",
            "error": "non_json_prose",
            "raw": obj[:500],
        }
    if not isinstance(obj, dict):
        return {
            "type": "protocol_error",
            "error": "unexpected_json_type",
            "raw": str(obj)[:500],
        }

    # Nested wrapper seen from small models: {"tool_call": {...}} or {"tool_call": "name"}
    if "tool_call" in obj and "tool" not in obj:
        tc = obj["tool_call"]
        if isinstance(tc, str):
            return _tool_call_action(tc, {}, raw=raw)
        if isinstance(tc, dict):
            return _tool_call_action(
                tc.get("tool"),
                tc.get("arguments") if "arguments" in tc else tc.get("args"),
                raw=raw,
            )
        return {
            "type": "protocol_error",
            "error": "missing_tool_or_answer",
            "raw": json.dumps(obj, ensure_ascii=False)[:500],
        }

    if obj.get("type") == "tool_call" and "tool" in obj:
        return _tool_call_action(
            obj["tool"],
            obj.get("arguments") if "arguments" in obj else obj.get("args"),
            raw=raw,
        )
    if "tool" in obj:
        return _tool_call_action(
            obj["tool"],
            obj.get("arguments") if "arguments" in obj else obj.get("args"),
            raw=raw,
        )
    if "final" in obj:
        return {"type": "final", "content": obj["final"]}
    if "answer" in obj:
        return {"type": "final", "content": obj}
    return {
        "type": "protocol_error",
        "error": "missing_tool_or_answer",
        "raw": json.dumps(obj, ensure_ascii=False)[:500],
    }


def action_from_model_text(content: str) -> dict[str, Any]:
    """Parse model text into a harness action (shared by Ollama/Bedrock)."""
    return normalize_llm_action(_parse_json_content(content), raw=content)


def protocol_nudge(tools: list[dict[str, Any]], *, error: str | None = None) -> str:
    tool_names = ", ".join(t["name"] for t in tools)
    err = f" ({error})" if error else ""
    return (
        f"Protocol error{err}: reply with ONE JSON object only — no prose, "
        f"no XML, no markdown fences. Example: "
        f'{{"tool":"view","arguments":{{"path":"."}}}} '
        f"Allowed tools: {tool_names}."
    )


def should_reinforce_tool_json(messages: list[dict[str, Any]]) -> bool:
    """Always reinforce for now — skipping mid-turn increased step count/cost."""
    return True


def reinforce_tool_json(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    *,
    force: bool | None = None,
) -> list[dict[str, Any]]:
    if force is False:
        return list(messages)
    if force is None and not should_reinforce_tool_json(messages):
        return list(messages)
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
    kind = action.get("type")
    if kind == "tool_call":
        detail = f"tool={action.get('tool')!r}"
    elif kind == "protocol_error":
        detail = f"protocol_error={action.get('error')!r}"
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

    def usage_dict(self) -> dict[str, Any]:
        return {
            "n_calls": self.n_calls,
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
            "model_id": f"ollama/{self.model}",
            "note": "Ollama path does not expose token counts",
        }

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
        action = action_from_model_text(content)
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
        self.input_tokens = 0
        self.output_tokens = 0
        self.cache_read_tokens = 0
        self.cache_write_tokens = 0
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

    def usage_dict(self) -> dict[str, Any]:
        return {
            "n_calls": self.n_calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "cache_write_tokens": self.cache_write_tokens,
            "model_id": f"bedrock/{self.model}",
        }

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
        # Prompt-cache the stable prefix (everything except the latest turn).
        # Haiku 4.5 needs ≥4096 tokens before a checkpoint takes effect.
        if len(out) >= 2:
            prev = out[-2]
            content = list(prev.get("content") or [])
            if content and not any(
                isinstance(b, dict) and "cachePoint" in b for b in content
            ):
                content = content + [{"cachePoint": {"type": "default"}}]
                prev = {**prev, "content": content}
                out[-2] = prev
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
            # Cache stable system text across multi-turn manage/search calls.
            kwargs["system"] = [
                {"text": system},
                {"cachePoint": {"type": "default"}},
            ]
        try:
            resp = self._client.converse(**kwargs)
        except (BotoCoreError, ClientError) as e:
            raise RuntimeError(
                f"Bedrock converse failed (call #{n}, model={self.model!r}): {e}. "
                "Newer Claude models need an inference profile id "
                "(e.g. us.anthropic.claude-haiku-4-5-20251001-v1:0)."
            ) from e
        dt = time.perf_counter() - t0
        usage = resp.get("usage") or {}
        self.input_tokens += int(usage.get("inputTokens") or 0)
        self.output_tokens += int(usage.get("outputTokens") or 0)
        self.cache_read_tokens += int(
            usage.get("cacheReadInputTokens")
            or usage.get("cacheReadInputTokenCount")
            or 0
        )
        self.cache_write_tokens += int(
            usage.get("cacheWriteInputTokens")
            or usage.get("cacheWriteInputTokenCount")
            or 0
        )
        chunks = (((resp.get("output") or {}).get("message") or {}).get("content")) or []
        content = "".join(c.get("text", "") for c in chunks if isinstance(c, dict))
        action = action_from_model_text(content)
        _log_action("bedrock converse", n, dt, action, content, self.verbose)
        if self.verbose and usage:
            _log(
                f"[amb] bedrock converse #{n} tokens "
                f"in={usage.get('inputTokens')} out={usage.get('outputTokens')}"
            )
        return action
