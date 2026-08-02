from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class Suite:
    root: Path
    meta: dict[str, Any]
    chunks: list[dict[str, Any]]
    facts: list[dict[str, Any]]
    queries: list[dict[str, Any]]
    scorecard_checks: list[dict[str, Any]]
    diagnostic_checks: list[dict[str, Any]]
    check_set_id: str
    diagnostics_set_id: str
    facts_by_id: dict[str, dict[str, Any]] = field(default_factory=dict)
    queries_by_id: dict[str, dict[str, Any]] = field(default_factory=dict)


def _read_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_suite(root: Path | str) -> Suite:
    root = Path(root).resolve()
    meta = _read_yaml(root / "suite.yaml")
    chunks_doc = _read_yaml(root / "stream" / "chunks.yaml")
    facts_doc = _read_yaml(root / "gold" / "facts.yaml")
    queries_doc = _read_yaml(root / "gold" / "queries.yaml")
    score_doc = _read_yaml(root / "checks" / "scorecard.yaml")
    diag_doc = _read_yaml(root / "checks" / "diagnostics.yaml")

    chunks = list(chunks_doc.get("chunks") or [])
    facts = list(facts_doc.get("facts") or [])
    queries = list(queries_doc.get("queries") or [])
    scorecard_checks = list(score_doc.get("checks") or [])
    diagnostic_checks = list(diag_doc.get("checks") or [])

    return Suite(
        root=root,
        meta=meta,
        chunks=chunks,
        facts=facts,
        queries=queries,
        scorecard_checks=scorecard_checks,
        diagnostic_checks=diagnostic_checks,
        check_set_id=score_doc.get("check_set_id") or meta.get("check_set_id", ""),
        diagnostics_set_id=diag_doc.get("diagnostics_set_id")
        or meta.get("diagnostics_set_id", ""),
        facts_by_id={f["id"]: f for f in facts if "id" in f},
        queries_by_id={q["id"]: q for q in queries if "id" in q},
    )
