from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from amb.agents.llm import LLM
from amb.bookkeeper import Bookkeeper, validate_citations
from amb.harness.memory_tool import MemoryToolHarness


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


TOOLS = [
    {"name": "view", "args": ["path"]},
    {"name": "done", "args": ["answer", "citations", "confidence"]},
]


def _store_map(store_root: Path) -> dict[str, Any]:
    """Deterministic listing so search starts with a map of the universe."""
    bk = Bookkeeper(store_root)
    top = bk.list_dir(".")
    children: dict[str, Any] = {}
    if top.get("ok"):
        for name in top.get("listing") or []:
            if isinstance(name, str) and name.endswith("/"):
                sub = bk.list_dir(name.rstrip("/"))
                if sub.get("ok"):
                    children[name] = sub.get("listing") or []
    return {"root": top, "children": children}


def run_search(
    llm: LLM,
    store_root: Path,
    query: str,
    prompt: str,
    *,
    max_steps: int = 20,
    progress: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    store_root = Path(store_root)
    harness = MemoryToolHarness(store_root, role="search")
    store_map = _store_map(store_root)
    messages = [
        {"role": "system", "content": prompt},
        {
            "role": "user",
            "content": json.dumps(
                {
                    "type": "query",
                    "q": query,
                    "store_map": store_map,
                    "instruction": (
                        "Use store_map to pick paths, view files, then done with a "
                        "SHORT canonical answer and real citations."
                    ),
                },
                ensure_ascii=False,
            ),
        },
    ]
    steps: list[dict[str, Any]] = [
        {"step": 0, "event": "store_map", "store_map": store_map}
    ]
    for step in range(1, max_steps + 1):
        if progress:
            _log(f"[amb] search step {step}/{max_steps} → asking model")
        out = llm.complete(messages, TOOLS)
        if out.get("type") == "tool_call":
            tool = out["tool"]
            args = out.get("arguments") or {}
            if tool == "done":
                check = validate_citations(
                    store_root,
                    args.get("citations") or [],
                    answer=args.get("answer"),
                )
                if not check.get("ok"):
                    obs = {
                        "ok": False,
                        "error_code": "citation_error",
                        "error": check.get("error"),
                        "bad": check.get("bad"),
                        "hint": (
                            "view real files first, then done with citations "
                            "that exist (or answer unknown with citations:[])"
                        ),
                    }
                    if progress:
                        _log(
                            f"[amb] search step {step}/{max_steps} "
                            f"rejected done: {check.get('error')}"
                        )
                    steps.append(
                        {
                            "step": step,
                            "event": "tool_call",
                            "tool": "done",
                            "arguments": args,
                            "observation": obs,
                            "rejected": True,
                        }
                    )
                    messages.append({"role": "assistant", "content": json.dumps(out)})
                    messages.append(
                        {"role": "user", "content": json.dumps({"observation": obs})}
                    )
                    continue
                if progress:
                    _log(f"[amb] search step {step}/{max_steps} final answer")
                payload = {
                    "query_id": None,
                    "answer": args.get("answer"),
                    "citations": check.get("citations") or [],
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
                answer = content.get("answer")
                citations = content.get("citations") or []
                check = validate_citations(store_root, citations, answer=answer)
                if not check.get("ok"):
                    obs = {
                        "ok": False,
                        "error_code": "citation_error",
                        "error": check.get("error"),
                        "bad": check.get("bad"),
                        "hint": (
                            "use tool done with real citation paths, "
                            "or answer unknown with citations:[]"
                        ),
                    }
                    steps.append(
                        {
                            "step": step,
                            "event": "tool_call",
                            "tool": "final_rejected",
                            "arguments": content,
                            "observation": obs,
                            "rejected": True,
                        }
                    )
                    messages.append({"role": "assistant", "content": json.dumps(out)})
                    messages.append(
                        {"role": "user", "content": json.dumps({"observation": obs})}
                    )
                    continue
                payload = {
                    "answer": answer,
                    "citations": check.get("citations") or [],
                    "confidence": content.get("confidence", "medium"),
                    "status": "ok",
                    "error_code": None,
                }
            else:
                # Bare string final — only accept abstain-like unknowns.
                check = validate_citations(store_root, [], answer=str(content))
                if not check.get("ok"):
                    obs = {
                        "ok": False,
                        "error_code": "citation_error",
                        "error": check.get("error"),
                        "hint": "call done with answer + real citations",
                    }
                    steps.append(
                        {
                            "step": step,
                            "event": "tool_call",
                            "tool": "final_rejected",
                            "arguments": {"content": content},
                            "observation": obs,
                            "rejected": True,
                        }
                    )
                    messages.append({"role": "assistant", "content": json.dumps(out)})
                    messages.append(
                        {"role": "user", "content": json.dumps({"observation": obs})}
                    )
                    continue
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
