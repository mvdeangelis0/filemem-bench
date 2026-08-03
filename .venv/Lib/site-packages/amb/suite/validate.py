from __future__ import annotations

from collections import Counter
from typing import Any

from amb.suite.load import Suite

DENYLIST = {
    "introduces",
    "supersedes",
    "tags",
    "gold_facts",
    "check_ids",
}


def validate_suite(suite: Suite) -> list[str]:
    errors: list[str] = []
    meta = suite.meta

    for key in ("id", "version", "world_id", "min_chunks", "min_queries"):
        if key not in meta:
            errors.append(f"suite.yaml missing {key}")

    n_chunks = len(suite.chunks)
    if n_chunks < int(meta.get("min_chunks", 0)):
        errors.append(f"chunks {n_chunks} < min_chunks {meta.get('min_chunks')}")
    if n_chunks > int(meta.get("max_chunks", 10**9)):
        errors.append(f"chunks {n_chunks} > max_chunks {meta.get('max_chunks')}")

    ts = sorted(c.get("t", -1) for c in suite.chunks)
    if ts != list(range(1, n_chunks + 1)):
        errors.append(f"chunk t values must be contiguous 1..N, got {ts}")

    chunk_ids = {c.get("id") for c in suite.chunks}
    for fact in suite.facts:
        fid = fact.get("id")
        if not fid:
            errors.append("fact missing id")
            continue
        if "match" not in fact:
            errors.append(f"fact {fid} missing match block")
        else:
            mode = fact["match"].get("mode")
            if mode not in {
                "normalized_any",
                "regex_any",
                "normalized_all",
                "absent_normalized_any",
            }:
                errors.append(f"fact {fid} bad match.mode {mode}")
        intro = fact.get("introduced_in")
        if intro and intro not in chunk_ids:
            errors.append(f"fact {fid} introduced_in unknown chunk {intro}")

    if len(suite.queries) < int(meta.get("min_queries", 0)):
        errors.append(
            f"queries {len(suite.queries)} < min_queries {meta.get('min_queries')}"
        )

    cats = Counter(q.get("category") for q in suite.queries)
    for cat, need in (meta.get("categories_required") or {}).items():
        if cats.get(cat, 0) < int(need):
            errors.append(f"category {cat}: have {cats.get(cat, 0)} need {need}")

    whitelist = set(meta.get("agent_visible_chunk_fields") or [])
    bad = whitelist & DENYLIST
    if bad:
        errors.append(f"agent_visible_chunk_fields includes denylist: {sorted(bad)}")

    non_abstain = [q for q in suite.queries if not (q.get("gold") or {}).get("abstain")]
    support_ok = 0
    for q in non_abstain:
        cites = q.get("citations") or {}
        if cites.get("evidence_any"):
            support_ok += 1
        elif "citations_support" in set(q.get("checks") or []):
            errors.append(f"query {q.get('id')} missing citations.evidence_any")

    # DD-02 §7.4: smoke ≥50%; core = all non-abstain
    policy = meta.get("citation_support_policy")
    if policy is None:
        policy = "all_non_abstain" if meta.get("id") == "core" else "half_non_abstain"
    if non_abstain:
        if policy == "all_non_abstain" and support_ok < len(non_abstain):
            errors.append(
                f"citation support coverage {support_ok}/{len(non_abstain)} < 100% (core)"
            )
        elif policy == "half_non_abstain" and support_ok < (len(non_abstain) + 1) // 2:
            errors.append(
                f"citation support coverage {support_ok}/{len(non_abstain)} < 50%"
            )

    for check in suite.scorecard_checks:
        family = check.get("family")
        args = check.get("args") or {}
        if family in {"fact_present", "protected_survives"}:
            fid = args.get("fact_id")
            if fid not in suite.facts_by_id:
                errors.append(f"check {check.get('id')} unknown fact {fid}")
            elif family == "protected_survives" and not suite.facts_by_id[fid].get(
                "protected"
            ):
                errors.append(f"check {check.get('id')} fact not protected")
        if family == "update_precedence":
            for k in ("current_fact_id", "historical_fact_id"):
                if args.get(k) not in suite.facts_by_id:
                    errors.append(f"check {check.get('id')} unknown {k}")
        if family in {"answer_match", "citations_exist", "citations_support"}:
            qid = args.get("query_id")
            if qid not in suite.queries_by_id:
                errors.append(f"check {check.get('id')} unknown query {qid}")

    return errors
