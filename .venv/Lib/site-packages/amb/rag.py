"""Lexical top-k retrieval over verbatim chunk files (no embedding deps)."""

from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

_TOKEN = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN.findall((text or "").casefold()) if len(t) >= 2]


def load_chunk_docs(store_root: Path) -> list[dict[str, Any]]:
    """Load chunks/*.md as retrieval documents."""
    root = Path(store_root) / "chunks"
    if not root.is_dir():
        return []
    docs: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        rel = f"chunks/{path.name}"
        docs.append(
            {
                "path": rel,
                "text": text,
                "tokens": tokenize(text),
            }
        )
    return docs


def _tfidf_vectors(
    docs: list[dict[str, Any]],
) -> tuple[list[Counter[str]], dict[str, float]]:
    df: Counter[str] = Counter()
    tfs: list[Counter[str]] = []
    for doc in docs:
        tf = Counter(doc["tokens"])
        tfs.append(tf)
        for term in tf:
            df[term] += 1
    n = max(len(docs), 1)
    idf = {t: math.log((n + 1) / (df[t] + 1)) + 1.0 for t in df}
    return tfs, idf


def _dot(a: dict[str, float], b: dict[str, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(v * b.get(k, 0.0) for k, v in a.items())


def _norm(a: dict[str, float]) -> float:
    return math.sqrt(sum(v * v for v in a.values())) or 1.0


def retrieve_topk(
    store_root: Path,
    query: str,
    *,
    k: int = 3,
) -> list[dict[str, Any]]:
    """Return top-k chunk docs by TF-IDF cosine similarity."""
    docs = load_chunk_docs(store_root)
    if not docs:
        return []
    tfs, idf = _tfidf_vectors(docs)
    q_tf = Counter(tokenize(query))
    q_vec = {t: q_tf[t] * idf.get(t, 0.0) for t in q_tf if t in idf}
    qn = _norm(q_vec)
    scored: list[tuple[float, dict[str, Any]]] = []
    for doc, tf in zip(docs, tfs, strict=True):
        d_vec = {t: tf[t] * idf[t] for t in tf}
        score = _dot(q_vec, d_vec) / (qn * _norm(d_vec))
        scored.append((score, doc))
    scored.sort(key=lambda x: (-x[0], x[1]["path"]))
    out: list[dict[str, Any]] = []
    for score, doc in scored[: max(k, 0)]:
        out.append(
            {
                "path": doc["path"],
                "score": round(float(score), 6),
                "text": doc["text"],
            }
        )
    return out
