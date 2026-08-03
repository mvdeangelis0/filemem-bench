"""RAG search arm: lexical top-k passages → one JSON answer (no FS tools)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from amb.agents.llm import LLM, protocol_nudge
from amb.bookkeeper import validate_citations
from amb.rag import retrieve_topk

RAG_PROMPT = """You answer questions using ONLY the retrieved passages below.

Reply with ONE JSON object only (no markdown fences, no prose):
{"tool":"done","arguments":{"answer":"...","citations":["chunks/chunk_NNN.md"],"confidence":"high|medium|low"}}

Rules:
- answer must be a SHORT canonical value (a few words), not a sentence.
- Prefer later / updated facts when passages disagree (higher t= or "Update:" wins).
- Citations MUST be paths from the retrieved passages list only.
- If the passages are insufficient, answer "unknown" with citations: [].
- Do not use outside knowledge.
"""


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


TOOLS = [{"name": "done", "args": ["answer", "citations", "confidence"]}]


def run_rag_search(
    llm: LLM,
    store_root: Path,
    query: str,
    *,
    top_k: int = 3,
    max_steps: int = 4,
    progress: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    store_root = Path(store_root)
    hits = retrieve_topk(store_root, query, k=top_k)
    allowed = {h["path"] for h in hits}
    passages = [
        {"path": h["path"], "score": h["score"], "text": h["text"]} for h in hits
    ]
    user = {
        "type": "rag_query",
        "q": query,
        "retrieved": passages,
        "instruction": (
            "Answer from retrieved passages only. Prefer later updates. "
            "Return tool done with short answer + citation paths from retrieved."
        ),
    }
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": RAG_PROMPT},
        {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
    ]
    steps: list[dict[str, Any]] = [
        {"step": 0, "event": "retrieve", "top_k": top_k, "hits": passages}
    ]

    for step in range(1, max_steps + 1):
        if progress:
            _log(f"[amb] rag step {step}/{max_steps} → asking model")
        out = llm.complete(messages, TOOLS)
        if out.get("type") == "protocol_error":
            nudge = protocol_nudge(TOOLS, error=str(out.get("error") or "bad_protocol"))
            steps.append(
                {
                    "step": step,
                    "event": "protocol_error",
                    "error": out.get("error"),
                    "raw": out.get("raw"),
                }
            )
            messages.append(
                {
                    "role": "assistant",
                    "content": json.dumps(
                        {
                            "type": "protocol_error",
                            "error": out.get("error"),
                            "raw": out.get("raw"),
                        },
                        ensure_ascii=False,
                    ),
                }
            )
            messages.append({"role": "user", "content": nudge})
            continue

        args: dict[str, Any]
        if out.get("type") == "tool_call" and out.get("tool") == "done":
            args = out.get("arguments") or {}
        elif out.get("type") == "final" and isinstance(out.get("content"), dict):
            args = out["content"]
        else:
            nudge = protocol_nudge(TOOLS, error="expected_done")
            steps.append(
                {
                    "step": step,
                    "event": "protocol_error",
                    "error": "expected_done",
                    "raw": out,
                }
            )
            messages.append({"role": "assistant", "content": json.dumps(out)})
            messages.append({"role": "user", "content": nudge})
            continue

        answer = args.get("answer")
        citations = list(args.get("citations") or [])
        # Drop citations not in the retrieved set.
        bad_extra = [c for c in citations if isinstance(c, str) and c not in allowed]
        citations = [c for c in citations if isinstance(c, str) and c in allowed]
        check = validate_citations(store_root, citations, answer=answer)
        if not check.get("ok") or bad_extra:
            obs = {
                "ok": False,
                "error_code": "citation_error",
                "error": check.get("error") or "citation not in retrieved set",
                "bad_extra": bad_extra,
                "allowed": sorted(allowed),
                "hint": "cite only paths from retrieved passages, or unknown with []",
            }
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
            messages.append({"role": "user", "content": json.dumps({"observation": obs})})
            continue

        if progress:
            _log(f"[amb] rag step {step}/{max_steps} final answer={answer!r}")
        payload = {
            "answer": answer,
            "citations": check.get("citations") or [],
            "confidence": args.get("confidence", "medium"),
            "status": "ok",
            "error_code": None,
            "retrieval": [{"path": h["path"], "score": h["score"]} for h in hits],
        }
        steps.append(
            {"step": step, "event": "final", "tool": "done", "arguments": args}
        )
        return payload, steps

    return {
        "answer": None,
        "citations": [],
        "status": "error",
        "error_code": "max_steps_exceeded",
        "retrieval": [{"path": h["path"], "score": h["score"]} for h in hits],
    }, steps
