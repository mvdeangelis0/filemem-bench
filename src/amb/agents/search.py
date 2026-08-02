from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from amb.agents.llm import LLM
from amb.harness.memory_tool import MemoryToolHarness


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)

TOOLS = [
    {"name": "view", "args": ["path"]},
    {"name": "done", "args": ["answer", "citations", "confidence"]},
]


def run_search(
    llm: LLM,
    store_root: Path,
    query: str,
    prompt: str,
    *,
    max_steps: int = 20,
    progress: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    harness = MemoryToolHarness(store_root, role="search")
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": json.dumps({"type": "query", "q": query})},
    ]
    steps: list[dict[str, Any]] = []
    for step in range(1, max_steps + 1):
        if progress:
            _log(f"[amb] search step {step}/{max_steps} → asking model")
        out = llm.complete(messages, TOOLS)
        if out.get("type") == "tool_call":
            tool = out["tool"]
            args = out.get("arguments") or {}
            if tool == "done":
                if progress:
                    _log(f"[amb] search step {step}/{max_steps} final answer")
                payload = {
                    "query_id": None,
                    "answer": args.get("answer"),
                    "citations": args.get("citations") or [],
                    "confidence": args.get("confidence", "medium"),
                    "status": "ok",
                    "error_code": None,
                }
                steps.append(
                    {
                        "step": step,
                        "event": "final",
                        "tool": "done",
                        "arguments": args,
                    }
                )
                return payload, steps
            if progress:
                _log(f"[amb] search step {step}/{max_steps} exec tool={tool!r}")
            obs = harness.execute(tool, args)
            steps.append(
                {
                    "step": step,
                    "event": "tool_call",
                    "tool": tool,
                    "arguments": args,
                    "observation": obs,
                }
            )
            messages.append({"role": "assistant", "content": json.dumps(out)})
            messages.append({"role": "user", "content": json.dumps({"observation": obs})})
        else:
            content = out.get("content")
            if progress:
                _log(f"[amb] search step {step}/{max_steps} final (no tool)")
            if isinstance(content, dict):
                payload = {
                    "answer": content.get("answer"),
                    "citations": content.get("citations") or [],
                    "confidence": content.get("confidence", "medium"),
                    "status": "ok",
                    "error_code": None,
                }
            else:
                payload = {
                    "answer": str(content),
                    "citations": [],
                    "confidence": "low",
                    "status": "ok",
                    "error_code": None,
                }
            steps.append({"step": step, "event": "final", "content": content})
            return payload, steps
    if progress:
        _log(f"[amb] search hit max_steps={max_steps}")
    return {
        "answer": None,
        "citations": [],
        "status": "error",
        "error_code": "max_steps_exceeded",
    }, steps
