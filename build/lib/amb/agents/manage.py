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
    {"name": "create", "args": ["path", "file_text"]},
    {"name": "str_replace", "args": ["path", "old_str", "new_str"]},
    {"name": "insert", "args": ["path", "insert_line", "new_str"]},
    {"name": "delete", "args": ["path"]},
    {"name": "rename", "args": ["old_path", "new_path"]},
    {"name": "done", "args": []},
]


def run_manage(
    llm: LLM,
    store_root: Path,
    chunk: dict[str, Any],
    prompt: str,
    *,
    max_steps: int = 30,
    progress: bool = False,
) -> list[dict[str, Any]]:
    harness = MemoryToolHarness(store_root, role="manage")
    messages = [
        {"role": "system", "content": prompt},
        {
            "role": "user",
            "content": json.dumps({"type": "chunk", "chunk": chunk}, ensure_ascii=False),
        },
    ]
    steps: list[dict[str, Any]] = []
    for step in range(1, max_steps + 1):
        if progress:
            _log(f"[amb] manage step {step}/{max_steps} → asking model")
        out = llm.complete(messages, TOOLS)
        if out.get("type") == "tool_call":
            tool = out["tool"]
            args = out.get("arguments") or {}
            if progress:
                _log(f"[amb] manage step {step}/{max_steps} exec tool={tool!r}")
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
            if tool == "done" and obs.get("ok"):
                if progress:
                    _log(f"[amb] manage step {step}/{max_steps} agent done")
                steps.append({"step": step, "event": "done", "reason": "agent_done"})
                return steps
        else:
            if progress:
                _log(f"[amb] manage step {step}/{max_steps} final (no tool)")
            # treat final as done
            steps.append(
                {
                    "step": step,
                    "event": "done",
                    "reason": "final_message",
                    "content": out.get("content"),
                }
            )
            return steps
    if progress:
        _log(f"[amb] manage hit max_steps={max_steps}")
    steps.append({"step": max_steps, "event": "done", "reason": "max_steps_exceeded"})
    return steps
