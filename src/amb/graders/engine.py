from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from amb.graders.corpus import build_corpus, first_matching_path
from amb.graders.match import match_text
from amb.norm import norm_v1
from amb.suite.load import Suite

ABSTAIN_DEFAULT = {
    "unknown",
    "not stated",
    "not found",
    "insufficient information",
}

MANAGE_FAMILIES = {"fact_present", "update_precedence", "protected_survives"}
SEARCH_FAMILIES = {"answer_match", "citations_exist", "citations_support"}


def _store_path(run_dir: Path, store: str) -> Path:
    return run_dir / "stores" / store


def _eval_fact(store_root: Path, fact: dict[str, Any]) -> dict[str, Any]:
    corpus, bodies = build_corpus(store_root)
    ok, matched = match_text(corpus, fact.get("match") or {})
    hint = None
    if ok and matched:

        def pred(body: str) -> bool:
            m = dict(fact.get("match") or {})
            if m.get("mode") == "normalized_any":
                m = {"mode": "normalized_any", "forms_any": [matched]}
            return match_text(body, m)[0]

        hint = first_matching_path(bodies, pred)
    return {
        "passed": ok,
        "status": "evaluated",
        "detail": {"matched_form": matched, "path_hint": hint},
    }


def _normalize_cite_path(p: str) -> str | None:
    if not p or p.startswith("/") or ".." in Path_parts(p):
        return None
    return p.replace("\\", "/").lstrip("./")


def Path_parts(p: str) -> tuple[str, ...]:
    return Path(p.replace("\\", "/")).parts


def _load_search_output(run_dir: Path, shape: str, query_id: str) -> dict[str, Any]:
    path = run_dir / "search_outputs" / shape / f"{query_id}.json"
    if not path.exists():
        return {
            "query_id": query_id,
            "shape": shape,
            "answer": None,
            "citations": [],
            "status": "error",
            "error_code": "missing_output",
        }
    return json.loads(path.read_text(encoding="utf-8"))


def _shapes_for(query: dict[str, Any], args: dict[str, Any]) -> list[str]:
    if "shape" in args:
        return [args["shape"]]
    return list(query.get("shapes") or ["organized"])


def grade(run_dir: Path | str, suite: Suite) -> tuple[dict[str, Any], dict[str, Any]]:
    run_dir = Path(run_dir)
    score_results: list[dict[str, Any]] = []
    diag_results: list[dict[str, Any]] = []

    for check in suite.scorecard_checks:
        score_results.extend(_run_check(run_dir, suite, check))
    for check in suite.diagnostic_checks:
        diag_results.extend(_run_check(run_dir, suite, check))

    scorecard = _wrap(suite, run_dir, "scorecard", score_results)
    diagnostics = _wrap(suite, run_dir, "diagnostics", diag_results)
    return scorecard, diagnostics


def _run_check(
    run_dir: Path, suite: Suite, check: dict[str, Any]
) -> list[dict[str, Any]]:
    family = check["family"]
    gate = check.get("gate", "scorecard")
    args = dict(check.get("args") or {})
    base_id = check["id"]

    if family in MANAGE_FAMILIES:
        store = args.get("store", "organized")
        root = _store_path(run_dir, store)
        if family == "fact_present":
            fact = suite.facts_by_id.get(args.get("fact_id"))
            if not fact:
                return [_err(base_id, family, gate, "unknown fact")]
            out = _eval_fact(root, fact)
            return [{**out, "check_id": base_id, "family": family, "gate": gate}]
        if family == "protected_survives":
            fact = suite.facts_by_id.get(args.get("fact_id"))
            if not fact:
                return [_err(base_id, family, gate, "unknown fact")]
            if not fact.get("protected"):
                return [_err(base_id, family, gate, "fact not protected")]
            out = _eval_fact(root, fact)
            return [{**out, "check_id": base_id, "family": family, "gate": gate}]
        if family == "update_precedence":
            cur = suite.facts_by_id.get(args.get("current_fact_id"))
            hist = suite.facts_by_id.get(args.get("historical_fact_id"))
            if not cur or not hist:
                return [_err(base_id, family, gate, "unknown fact ids")]
            cur_out = _eval_fact(root, cur)
            hist_match = {
                "mode": "absent_normalized_any",
                "forms_any": (hist.get("match") or {}).get("forms_any") or [hist.get("value")],
            }
            corpus, _ = build_corpus(root)
            hist_absent, hit = match_text(corpus, hist_match)
            passed = bool(cur_out["passed"] and hist_absent)
            return [
                {
                    "check_id": base_id,
                    "family": family,
                    "gate": gate,
                    "passed": passed,
                    "status": "evaluated",
                    "detail": {
                        "current_ok": cur_out["passed"],
                        "historical_absent": hist_absent,
                        "historical_hit": hit,
                    },
                }
            ]

    if family in SEARCH_FAMILIES:
        qid = args.get("query_id")
        query = suite.queries_by_id.get(qid)
        if not query:
            return [_err(base_id, family, gate, "unknown query")]
        results = []
        for shape in _shapes_for(query, args):
            cid = f"{base_id}.{shape}" if "shape" not in args else base_id
            results.append(
                _search_family(run_dir, suite, family, gate, cid, query, shape)
            )
        return results

    if family == "store_file_count":
        store = args.get("store", "organized")
        root = _store_path(run_dir, store)
        _, bodies = build_corpus(root)
        return [
            {
                "check_id": base_id,
                "family": family,
                "gate": gate,
                "passed": True,
                "status": "evaluated",
                "detail": {"file_count": len(bodies)},
            }
        ]
    if family == "store_max_depth":
        store = args.get("store", "organized")
        root = _store_path(run_dir, store)
        depth = 0
        if root.exists():
            for p in root.rglob("*"):
                if p.is_file() and "_amb" not in p.parts:
                    depth = max(depth, len(p.relative_to(root).parts) - 1)
        return [
            {
                "check_id": base_id,
                "family": family,
                "gate": gate,
                "passed": True,
                "status": "evaluated",
                "detail": {"max_depth": depth},
            }
        ]

    return [_err(base_id, family, gate, f"unknown family {family}")]


def _search_family(
    run_dir: Path,
    suite: Suite,
    family: str,
    gate: str,
    check_id: str,
    query: dict[str, Any],
    shape: str,
) -> dict[str, Any]:
    out = _load_search_output(run_dir, shape, query["id"])
    store_root = _store_path(run_dir, shape)
    gold = query.get("gold") or {}
    citations_meta = query.get("citations") or {}

    if family == "answer_match":
        if out.get("status") != "ok" or out.get("answer") is None:
            return {
                "check_id": check_id,
                "family": family,
                "gate": gate,
                "shape": shape,
                "passed": False,
                "status": "evaluated",
                "detail": {"reason": "no_answer", "error_code": out.get("error_code")},
            }
        ans = norm_v1(str(out["answer"]), for_answer=True)
        if gold.get("abstain"):
            passed = ans in {norm_v1(x, for_answer=True) for x in ABSTAIN_DEFAULT}
            return {
                "check_id": check_id,
                "family": family,
                "gate": gate,
                "shape": shape,
                "passed": passed,
                "status": "evaluated",
                "detail": {"answer_norm": ans},
            }
        for bad in gold.get("answers_forbidden_any") or []:
            if ans == norm_v1(bad, for_answer=True):
                return {
                    "check_id": check_id,
                    "family": family,
                    "gate": gate,
                    "shape": shape,
                    "passed": False,
                    "status": "evaluated",
                    "detail": {"reason": "forbidden", "answer_norm": ans},
                }
        passed = any(ans == norm_v1(g, for_answer=True) for g in gold.get("answers_any") or [])
        return {
            "check_id": check_id,
            "family": family,
            "gate": gate,
            "shape": shape,
            "passed": passed,
            "status": "evaluated",
            "detail": {"answer_norm": ans},
        }

    if family == "citations_exist":
        if out.get("status") != "ok":
            return {
                "check_id": check_id,
                "family": family,
                "gate": gate,
                "shape": shape,
                "passed": False,
                "status": "evaluated",
                "detail": {"reason": "search_error"},
            }
        cites = out.get("citations") or []
        if not cites:
            if citations_meta.get("allow_empty"):
                return {
                    "check_id": check_id,
                    "family": family,
                    "gate": gate,
                    "shape": shape,
                    "passed": True,
                    "status": "evaluated",
                    "detail": {"empty_allowed": True},
                }
            return {
                "check_id": check_id,
                "family": family,
                "gate": gate,
                "shape": shape,
                "passed": False,
                "status": "evaluated",
                "detail": {"reason": "empty_citations"},
            }
        for c in cites:
            norm = _normalize_cite_path(str(c))
            if norm is None:
                return {
                    "check_id": check_id,
                    "family": family,
                    "gate": gate,
                    "shape": shape,
                    "passed": False,
                    "status": "evaluated",
                    "detail": {"reason": "path_error", "path": c},
                }
            target = store_root / norm
            if not target.is_file():
                return {
                    "check_id": check_id,
                    "family": family,
                    "gate": gate,
                    "shape": shape,
                    "passed": False,
                    "status": "evaluated",
                    "detail": {"reason": "missing_file", "path": norm},
                }
        return {
            "check_id": check_id,
            "family": family,
            "gate": gate,
            "shape": shape,
            "passed": True,
            "status": "evaluated",
            "detail": {"citations": cites},
        }

    if family == "citations_support":
        exist = _search_family(
            run_dir, suite, "citations_exist", gate, check_id, query, shape
        )
        if not exist["passed"]:
            return {
                "check_id": check_id,
                "family": family,
                "gate": gate,
                "shape": shape,
                "passed": False,
                "status": "evaluated",
                "detail": {"reason": "deps_failed", "exist": exist["detail"]},
            }
        evidence_any = citations_meta.get("evidence_any")
        if not evidence_any:
            return _err(check_id, family, gate, "missing evidence_any", shape=shape)
        min_sup = int(citations_meta.get("min_supporting_citations") or 1)
        supporting = 0
        for c in out.get("citations") or []:
            norm = _normalize_cite_path(str(c))
            if not norm:
                continue
            body = (store_root / norm).read_text(encoding="utf-8", errors="replace")
            for ev in evidence_any:
                m = {
                    "mode": "normalized_any",
                    "forms_any": ev.get("must_include_any") or [],
                }
                if ev.get("regex_any"):
                    m = {"mode": "regex_any", "regex_any": ev["regex_any"]}
                if match_text(body, m)[0]:
                    supporting += 1
                    break
        passed = supporting >= min_sup
        return {
            "check_id": check_id,
            "family": family,
            "gate": gate,
            "shape": shape,
            "passed": passed,
            "status": "evaluated",
            "detail": {
                "supporting_count": supporting,
                "min_supporting": min_sup,
                "citations": out.get("citations") or [],
            },
        }

    return _err(check_id, family, gate, "unhandled", shape=shape)


def _err(
    check_id: str, family: str, gate: str, reason: str, shape: str | None = None
) -> dict[str, Any]:
    d: dict[str, Any] = {
        "check_id": check_id,
        "family": family,
        "gate": gate,
        "passed": False,
        "status": "config_error",
        "detail": {"reason": reason},
    }
    if shape:
        d["shape"] = shape
    return d


def _wrap(
    suite: Suite, run_dir: Path, kind: str, results: list[dict[str, Any]]
) -> dict[str, Any]:
    scored = [r for r in results if r.get("gate") == "scorecard" or kind == "diagnostics"]
    if kind == "scorecard":
        scored = [r for r in results if r.get("gate") == "scorecard"]
        n = len(scored)
        n_pass = sum(1 for r in scored if r.get("passed"))
        by_family: dict[str, dict[str, int]] = defaultdict(lambda: {"n": 0, "passed": 0})
        by_role = {
            "management": {"n": 0, "passed": 0},
            "search": {"n": 0, "passed": 0},
        }
        by_shape: dict[str, dict[str, int]] = defaultdict(lambda: {"n": 0, "passed": 0})
        for r in scored:
            fam = r["family"]
            by_family[fam]["n"] += 1
            by_family[fam]["passed"] += int(bool(r.get("passed")))
            if fam in MANAGE_FAMILIES:
                by_role["management"]["n"] += 1
                by_role["management"]["passed"] += int(bool(r.get("passed")))
            if fam in SEARCH_FAMILIES:
                by_role["search"]["n"] += 1
                by_role["search"]["passed"] += int(bool(r.get("passed")))
            if "shape" in r:
                by_shape[r["shape"]]["n"] += 1
                by_shape[r["shape"]]["passed"] += int(bool(r.get("passed")))
        summary = {
            "n_scorecard": n,
            "n_passed": n_pass,
            "pass_rate": (n_pass / n) if n else 0.0,
            "by_family": dict(by_family),
            "by_role_proxy": by_role,
            "by_shape": dict(by_shape),
        }
    else:
        summary = {"n_diagnostic": len(results)}

    return {
        "schema_version": "amb_scorecard_v1",
        "normalization_id": "norm_v1",
        "check_set_id": suite.check_set_id
        if kind == "scorecard"
        else suite.diagnostics_set_id,
        "suite": {
            "id": suite.meta.get("id"),
            "version": suite.meta.get("version"),
        },
        "run_id": run_dir.name,
        "graded_at": datetime.now(timezone.utc).isoformat(),
        "results": results,
        "summary": summary,
    }
