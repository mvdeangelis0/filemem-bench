from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from amb.continuous.deferred import count_deferred, list_deferred
from amb.continuous.web_trail import list_trail, read_cursor
from amb.rag import tokenize

_SKIP_DIRS = {".git", "__pycache__", "inbox_archive"}
_TEXT_SUFFIXES = {".md", ".json", ".jsonl", ".txt", ".py", ".csv", ".yaml", ".yml"}


def inventory_tree(run_dir: Path, *, max_files: int = 200) -> list[str]:
    """Return relative paths under the run for operator display."""
    root = Path(run_dir).resolve()
    lines: list[str] = []
    count = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        rel = str(path.relative_to(root)).replace("\\", "/")
        size = path.stat().st_size
        lines.append(f"{rel}\t{size}B")
        count += 1
        if count >= max_files:
            lines.append("… (truncated)")
            break
    return lines


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def build_map(run_dir: Path) -> str:
    """Human-readable map of how run artifacts relate."""
    run_dir = Path(run_dir)
    cfg = _load_json(run_dir / "config.json") or {}
    plan = _load_json(run_dir / "memory" / "current_plan.json") or {}
    graph = _load_json(run_dir / "memory" / "graph.json") or {}
    cursor = read_cursor(run_dir) or {}
    deferred = list_deferred(run_dir, limit=10)
    trail = list_trail(run_dir, limit=8)
    edges = [
        {"edge": k, **v} for k, v in (graph.get("edges") or {}).items()
    ]
    edges.sort(key=lambda e: float(e.get("weight", 0)), reverse=True)

    lines = [
        f"# Operator map — {run_dir.name}",
        "",
        "## Run",
        f"- world: {cfg.get('world')}",
        f"- model: {cfg.get('model')}",
        f"- seed: {cfg.get('seed')}",
        f"- web_allowlist: {cfg.get('web_allowlist')}",
        "",
        "## Live focus",
        f"- plan task: {plan.get('task')}",
        f"- plan step: {plan.get('step')}/{plan.get('steps_total')}",
        f"- deferred count: {count_deferred(run_dir)}",
        f"- web left off: {cursor.get('left_off') or '(none)'}",
        "",
        "## File roles",
        "- `STATUS.md` — what it is doing now",
        "- `INBOX.md` — your pending instructions",
        "- `core/objective.md` / `core/capabilities.md` — goal + limits",
        "- `memory/observations.jsonl` — everything remembered",
        "- `memory/deferred.jsonl` — parked out-of-scope work",
        "- `memory/web_trail.jsonl` + `web_cursor.json` — browse breadcrumbs",
        "- `memory/graph.json` — weighted pathways",
        "- `trajectory.jsonl` / `actions.jsonl` — step logs",
        "- `lab/` — simulated world state",
        "",
        "## Strongest pathways",
    ]
    if edges:
        for e in edges[:8]:
            lines.append(f"- {e['weight']:.2f}  {e['edge']}  (n={e.get('count', 0)})")
    else:
        lines.append("- (none yet)")

    lines.extend(["", "## Deferred (sample)"])
    if deferred:
        for row in deferred:
            lines.append(
                f"- [{row.get('need')}] {row.get('task')} — {row.get('reason')}"
            )
    else:
        lines.append("- (none)")

    lines.extend(["", "## Web trail (sample)"])
    if trail:
        for row in trail:
            target = row.get("url") or row.get("query") or ""
            lines.append(
                f"- {row.get('ts')} {row.get('action')} {target} {row.get('title') or ''}"
            )
    else:
        lines.append("- (none)")

    lines.extend(["", "## Inventory"])
    lines.extend(f"- {ln}" for ln in inventory_tree(run_dir)[:80])
    text = "\n".join(lines) + "\n"
    (run_dir / "OPERATOR_MAP.md").write_text(text, encoding="utf-8")
    return text


def load_run_docs(run_dir: Path, *, max_chars: int = 12000) -> list[dict[str, Any]]:
    """Load text-ish files from a run as retrieval documents."""
    root = Path(run_dir).resolve()
    docs: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in _TEXT_SUFFIXES and path.name not in {
            "STATUS.md",
            "INBOX.md",
            "REPORT.md",
            "OPERATOR_MAP.md",
        }:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if len(text) > max_chars:
            text = text[:max_chars] + "\n...[truncated]"
        rel = str(path.relative_to(root)).replace("\\", "/")
        docs.append({"path": rel, "text": text, "tokens": tokenize(text)})
    return docs


def _tfidf_retrieve(docs: list[dict[str, Any]], query: str, *, k: int) -> list[dict[str, Any]]:
    if not docs:
        return []
    df: Counter[str] = Counter()
    tfs: list[Counter[str]] = []
    for doc in docs:
        tf = Counter(doc["tokens"])
        tfs.append(tf)
        for term in tf:
            df[term] += 1
    n = max(len(docs), 1)
    idf = {t: math.log((n + 1) / (df[t] + 1)) + 1.0 for t in df}
    q_tf = Counter(tokenize(query))
    q_vec = {t: q_tf[t] * idf.get(t, 0.0) for t in q_tf if t in idf}

    def _dot(a: dict[str, float], b: dict[str, float]) -> float:
        if len(a) > len(b):
            a, b = b, a
        return sum(v * b.get(k, 0.0) for k, v in a.items())

    def _norm(a: dict[str, float]) -> float:
        return math.sqrt(sum(v * v for v in a.values())) or 1.0

    qn = _norm(q_vec)
    scored: list[tuple[float, dict[str, Any]]] = []
    for doc, tf in zip(docs, tfs, strict=True):
        d_vec = {t: tf[t] * idf[t] for t in tf}
        score = _dot(q_vec, d_vec) / (qn * _norm(d_vec))
        scored.append((score, {**doc, "score": score}))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [d for s, d in scored[:k] if s > 0] or [d for _, d in scored[:k]]


def ask_over_run(
    run_dir: Path,
    question: str,
    *,
    llm: Any | None = None,
    llm_mode: str = "mock",
    model: str = "mock",
    ollama_host: str | None = None,
    top_k: int = 6,
) -> dict[str, Any]:
    """Retrieve run docs and answer a question (read-only operator Q&A)."""
    docs = load_run_docs(run_dir)
    hits = _tfidf_retrieve(docs, question, k=top_k)
    context_blocks = []
    for h in hits:
        context_blocks.append(f"### {h['path']}\n{h['text'][:3000]}")
    context = "\n\n".join(context_blocks) if context_blocks else "(no matching files)"
    messages = [
        {
            "role": "system",
            "content": (
                "You answer questions about a continuous-agent run directory. "
                "Use only the provided files. Cite paths like `memory/notes.md`. "
                "If unknown, say so. Reply in plain prose (not tool JSON)."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Question: {question}\n\n"
                f"Retrieved run files:\n{context}\n\n"
                "Answer clearly for the human operator."
            ),
        },
    ]
    answer = _operator_chat(
        messages,
        llm=llm,
        llm_mode=llm_mode,
        model=model,
        ollama_host=ollama_host,
    )
    return {
        "question": question,
        "answer": answer,
        "sources": [{"path": h["path"], "score": round(float(h.get("score") or 0), 4)} for h in hits],
    }


def _operator_chat(
    messages: list[dict[str, Any]],
    *,
    llm: Any | None,
    llm_mode: str,
    model: str,
    ollama_host: str | None,
) -> str:
    """Plain-text chat for operator Q&A (avoids tool-JSON reinforcement)."""
    if llm is not None and hasattr(llm, "complete"):
        # Mock / custom: accept final content or stringified response.
        resp = llm.complete(messages, tools=[])
        if isinstance(resp, dict):
            if resp.get("type") == "final":
                content = resp.get("content")
                return content if isinstance(content, str) else json.dumps(content, indent=2)
            return json.dumps(resp, indent=2)
        return str(resp)

    if llm_mode == "mock":
        return (
            "(mock) No live model configured. Retrieved sources are listed below; "
            "set /set llm ollama and /set model <tag> then /ask again."
        )

    if llm_mode != "ollama":
        raise ValueError(f"unsupported llm_mode for /ask: {llm_mode}")

    import os

    import httpx

    host = (ollama_host or os.environ.get("OLLAMA_HOST") or "http://127.0.0.1:11434").rstrip("/")
    if model in {"mock", ""}:
        raise ValueError("--model required for ollama /ask")
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": 0.2},
    }
    with httpx.Client(timeout=180.0) as client:
        r = client.post(f"{host}/api/chat", json=payload)
        r.raise_for_status()
        data = r.json()
    return str((data.get("message") or {}).get("content") or "")
