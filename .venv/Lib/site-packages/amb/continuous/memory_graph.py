from __future__ import annotations

import json
from pathlib import Path

ACCESS_BUMP = 1.0
SUCCESS_BOOST = 0.5


def _norm(label: str) -> str:
    return " ".join(label.strip().lower().split())


def _edge_key(a: str, b: str) -> str:
    x, y = sorted([_norm(a), _norm(b)])
    return f"{x}|{y}"


class MemoryGraph:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        if not self.path.exists():
            self._save({"nodes": {}, "edges": {}})

    def load(self) -> dict:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _save(self, data: dict) -> None:
        self.path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    def observe(self, labels: list[str], *, observation_id: str, success: bool) -> None:
        labels = [_norm(x) for x in labels if _norm(x)]
        data = self.load()
        nodes, edges = data["nodes"], data["edges"]
        for lab in labels:
            n = nodes.setdefault(lab, {"visits": 0, "observations": []})
            n["visits"] += 1
            if observation_id not in n["observations"]:
                n["observations"].append(observation_id)
        for i, a in enumerate(labels):
            for b in labels[i + 1 :]:
                k = _edge_key(a, b)
                e = edges.setdefault(k, {"weight": 0.0, "count": 0})
                e["weight"] += ACCESS_BUMP
                e["count"] += 1
                if success:
                    e["weight"] += SUCCESS_BOOST
        self._save(data)

    def retrieve(self, *, query_tokens: list[str], top_k: int = 5) -> list[dict]:
        q = {_norm(t) for t in query_tokens if _norm(t)}
        data = self.load()
        scored: list[dict] = []
        for k, e in data["edges"].items():
            a, b = k.split("|", 1)
            overlap = (1 if a in q else 0) + (1 if b in q else 0)
            if overlap == 0 and q:
                continue
            scored.append({"edge": k, "a": a, "b": b, "weight": e["weight"] * (1 + overlap)})
        scored.sort(key=lambda x: x["weight"], reverse=True)
        return scored[:top_k]
