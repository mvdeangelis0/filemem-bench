from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from amb.agents.llm import LLM, protocol_nudge
from amb.bookkeeper import Bookkeeper, later_update_gate, validate_citations
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


def _is_chunk_store(store_map: dict[str, Any]) -> bool:
    children = store_map.get("children") or {}
    return "chunks/" in children or any(
        isinstance(name, str) and name.startswith("chunks")
        for name in ((store_map.get("root") or {}).get("listing") or [])
    )


def _append_protocol_retry(
    messages: list[dict[str, Any]],
    steps: list[dict[str, Any]],
    *,
    step: int,
    out: dict[str, Any],
    progress: bool,
) -> None:
    nudge = protocol_nudge(TOOLS, error=str(out.get("error") or "bad_protocol"))
    if progress:
        _log(f"[amb] search step {step} protocol retry: {out.get('error')}")
    steps.append(
        {
            "step": step,
            "event": "protocol_error",
            "error": out.get("error"),
            "raw": out.get("raw"),
            "nudge": nudge,
        }
    )
    messages.append(
        {
            "role": "assistant",
            "content": json.dumps(
                {"type": "protocol_error", "error": out.get("error"), "raw": out.get("raw")},
                ensure_ascii=False,
            ),
        }
    )
    messages.append({"role": "user", "content": nudge})


def run_search(
    llm: LLM,
    store_root: Path,
    query: str,
    prompt: str,
    *,
    shape: str | None = None,
    max_steps: int = 20,
    progress: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    store_root = Path(store_root)
    harness = MemoryToolHarness(store_root, role="search")
    store_map = _store_map(store_root)
    chunk_store = shape == "verbatim" or _is_chunk_store(store_map)
    bk = Bookkeeper(store_root)
    chunk_timeline = bk.chunk_timeline() if chunk_store else []
    instruction = (
        "Use store_map to pick paths, view files, then done with a "
        "SHORT canonical answer and real citations."
    )
    if chunk_store:
        instruction += (
            " This is a verbatim/chunk store: when facts conflict, prefer "
            "later chunks (higher chunk_NNN / later t= timestamp) over earlier ones. "
            "Do not stop after the first matching chunk if an update may exist later. "
            "chunk_timeline marks update_flag=true on superseding notes — view those."
        )
    user_payload: dict[str, Any] = {
        "type": "query",
        "q": query,
        "store_map": store_map,
        "shape": shape,
        "instruction": instruction,
    }
    if chunk_timeline:
        user_payload["chunk_timeline"] = chunk_timeline
    messages = [
        {"role": "system", "content": prompt},
        {
            "role": "user",
            "content": json.dumps(user_payload, ensure_ascii=False),
        },
    ]
    steps: list[dict[str, Any]] = [
        {
            "step": 0,
            "event": "store_map",
            "store_map": store_map,
            "shape": shape,
            "chunk_timeline": chunk_timeline,
        }
    ]
    for step in range(1, max_steps + 1):
        if progress:
            _log(f"[amb] search step {step}/{max_steps} → asking model")
        out = llm.complete(messages, TOOLS)
        if out.get("type") == "protocol_error":
            _append_protocol_retry(
                messages, steps, step=step, out=out, progress=progress
            )
            continue
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
                if chunk_store:
                    gate = later_update_gate(
                        store_root,
                        query,
                        answer=args.get("answer"),
                        citations=check.get("citations") or [],
                    )
                    if not gate.get("ok"):
                        obs = {
                            "ok": False,
                            "error_code": gate.get("error_code"),
                            "error": gate.get("error"),
                            "hint_paths": gate.get("hint_paths"),
                            "hint": (
                                "view hint_paths (later updates), then done "
                                "with a current answer and those citations"
                            ),
                        }
                        if progress:
                            _log(
                                f"[amb] search step {step}/{max_steps} "
                                f"later_update_gate → {gate.get('hint_paths')}"
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
                        messages.append(
                            {"role": "assistant", "content": json.dumps(out)}
                        )
                        messages.append(
                            {
                                "role": "user",
                                "content": json.dumps({"observation": obs}),
                            }
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
            continue

        # type == final (structured answer without tool wrapper)
        content = out.get("content")
        if not isinstance(content, dict) or "answer" not in content:
            _append_protocol_retry(
                messages,
                steps,
                step=step,
                out={
                    "error": "final_without_answer",
                    "raw": json.dumps(content, ensure_ascii=False)[:500]
                    if not isinstance(content, str)
                    else content[:500],
                },
                progress=progress,
            )
            continue
        if progress:
            _log(f"[amb] search step {step}/{max_steps} final (structured)")
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
        if chunk_store:
            gate = later_update_gate(
                store_root,
                query,
                answer=answer,
                citations=check.get("citations") or [],
            )
            if not gate.get("ok"):
                obs = {
                    "ok": False,
                    "error_code": gate.get("error_code"),
                    "error": gate.get("error"),
                    "hint_paths": gate.get("hint_paths"),
                    "hint": (
                        "view hint_paths (later updates), then done "
                        "with a current answer and those citations"
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
