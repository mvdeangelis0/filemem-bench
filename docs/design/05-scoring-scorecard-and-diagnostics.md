# Agent Memory Bench — Design Document 05  
## Scoring: Scorecard and Diagnostics

| Field | Value |
|---|---|
| **Status** | Approved |
| **Doc ID** | AMB-DD-05 |
| **Version** | 0.1.0 |
| **Date** | 2026-08-01 |
| **Approved** | 2026-08-01 |
| **Project** | `agent_memory_bench` |
| **Audience** | Grader implementers; authors interpreting pass/fail; paper readers |
| **Depends on** | AMB-DD-01 (v0.2.0); AMB-DD-02 (v0.2.0); AMB-DD-03 (Approved); AMB-DD-04 (Approved) |
| **Supersedes** | — |
| **Next doc** | AMB-DD-06 — Collaboration, Display & Release |

---

## 0. Abstract

This document specifies how deterministic graders compute the **scorecard** (headline pass/fail) and **diagnostics** (non-gating analyses) from a run ledger. It freezes normalization (`norm_v1`), fact-matching algorithms (DD-02 §6.4), answer matching, citation existence and evidence support (DD-02 §7.4), aggregation rules, and the prohibition on using diagnostics or LLM judges for headline success rates (DD-01 P4–P5).

The grader is a pure function:

```text
grade(run_dir, suite_fixtures, check_set) → scorecard.json + diagnostics.json
```

No model calls are permitted inside v1 grading.

---

## 1. Gates and Aggregation

### 1.1 Gates

| Gate | Affects `summary.pass_rate`? | Use |
|---|---|---|
| `scorecard` | **Yes** | Primary science |
| `diagnostic` | **No** | Store health, cost, structure |

### 1.2 Pass rate

```text
pass_rate = n_passed_scorecard / n_scorecard
```

Checks with `status: skipped` (e.g. shape not in run) are excluded from both numerator and denominator.

### 1.3 By-family and by-role rollups

Mandatory rollups in `scorecard.summary`:

- `by_family`: counts per check family  
- `by_role_proxy`: `management` = families `{fact_present, update_precedence, protected_survives}`; `search` = `{answer_match, citations_exist, citations_support}`  
- `by_shape`: for search checks, split `organized` vs `verbatim`

---

## 2. Normalization: `norm_v1`

Used for fact forms, answer matching, and citation evidence forms unless a check overrides.

**Pipeline (in order):**

1. Decode as UTF-8 (replace invalid bytes with U+FFFD).  
2. Unicode NFKC.  
3. Lowercase (Unicode casefold).  
4. Replace `\r\n` / `\r` with `\n`.  
5. Collapse all Unicode whitespace (including newlines) to a single ASCII space.  
6. Strip leading/trailing whitespace.  
7. For **answer** matching only: strip leading/trailing punctuation characters from the set `.,;:!?\"'`.  

**Not in v1:** stemming, stopword removal, synonym tables, edit distance.

Version pin: `normalization_id: norm_v1` recorded in scorecard header.

---

## 3. Store Scan Corpus

For store-facing checks:

1. Walk all files under the target store root (default: `stores/organized`).  
2. Skip directories and skip `/_amb/**`.  
3. Read each file as UTF-8 text.  
4. Build `corpus = join(sorted_relpath + "\n" + body + "\n\n")` for stable scanning.  
5. Optionally retain a map `path → body` for path hints and citation support.

**Tie-break for path hints:** lexicographically smallest relative path that matches.

---

## 4. Scorecard Families (Algorithms)

Each check instance supplies `args` from the suite’s `scorecard.yaml` (DD-02 §8).

### 4.1 `fact_present`

**Args:** `fact_id`, `store` (default `organized`)

**Procedure:**

1. Load fact from `gold/facts.yaml`; require `match` block.  
2. Build corpus for `store`.  
3. Apply `match.mode` (DD-02 §6.4):  
   - `normalized_any`: ∃ form ∈ `forms_any` with `norm_v1(form)` as substring of `norm_v1(corpus)`.  
   - `regex_any`: ∃ regex match per flags.  
   - `normalized_all`: ∀ form ∈ `forms_all` substring match.  
   - `absent_normalized_any`: ¬∃ form match (used as helper; rare as standalone).  
4. **Pass** iff match predicate true.

**Detail:** `{matched_form|matched_regex, path_hint?}`.

### 4.2 `update_precedence`

**Args:** `current_fact_id`, `historical_fact_id`, `store`

**Procedure (v1 default = hard absence of historical forms):**

1. Run `fact_present` logic on current → `cur_ok`.  
2. Run `absent_normalized_any` using historical fact’s `forms_any` (or its `match` block) → `hist_absent`.  
3. **Pass** iff `cur_ok ∧ hist_absent`.

Soft “historical marked OK” modes are **not** enabled in v1 check sets.

### 4.3 `protected_survives`

**Args:** `fact_id`, `store`

**Procedure:** Identical to `fact_present`, but fact must have `protected: true` (validator enforces). Fail with `config_error` if not protected.

### 4.4 `answer_match`

**Args:** `query_id`, `shape` (or inherit from query `shapes` → emit one result per shape)

**Procedure:**

1. Load `search_outputs/{shape}/{query_id}.json`.  
2. If `status != ok` or `answer` is null → **Fail** (`error_code` in detail).  
3. Load query gold.  
4. If `gold.abstain: true`: **Pass** iff `norm_v1(answer)` ∈ normalized abstention set (suite default: `unknown`, `not stated`, `not found`, `insufficient information`).  
5. Else:  
   - Let `a = norm_v1(answer)`.  
   - **Fail** if ∃ f ∈ `answers_forbidden_any` with `norm_v1(f) == a` OR (optional suite flag) forbidden as substring. Default v1: **equality** on normalized strings for forbidden.  
   - **Pass** iff ∃ g ∈ `answers_any` with `norm_v1(g) == a`.  

Substring answer match is **not** default (too loose). Suites may set `gold.answer_match: substring` per query for explicitly marked cases.

### 4.5 `citations_exist`

**Args:** `query_id`, `shape`

**Procedure:**

1. Load search output; if error status → **Fail**.  
2. If `citations.allow_empty` on query and citations list empty → **Pass** (abstain path).  
3. If citations empty → **Fail**.  
4. For each path in `citations`:  
   - Normalize: strip leading `./`, reject `..`, reject absolute paths → else **Fail** `path_error`.  
   - Resolve under graded store root; file must exist and be a regular file → else **Fail**.  
5. **Pass** if all citations resolve.

### 4.6 `citations_support`

**Args:** `query_id`, `shape`

**Procedure:**

1. Require `citations_exist` would pass; else **Fail** (`deps_failed`).  
2. Load `citations.evidence_any` from query; if missing → `config_error` fail (core suites must declare evidence).  
3. `min_supporting = citations.min_supporting_citations` default 1.  
4. Count supporting citations: for each cited path, load body; **support** if ∃ evidence entry such that `normalized_any` or `regex_any` matches body under `norm_v1`.  
5. **Pass** iff `supporting_count >= min_supporting`.

---

## 5. Diagnostic Families (v1 minimum)

| Family | Metric | Notes |
|---|---|---|
| `store_file_count` | Number of files under store | Exclude `/_amb` |
| `store_max_depth` | Max directory depth | Root = 0 |
| `store_total_bytes` | Sum of file sizes | |
| `search_step_count` | Steps in search trajectory | `null` if trajectory absent |
| `manage_step_count` | Mean or total manage steps | Per-chunk list in detail |
| `citation_count` | Mean citations per query | Descriptive |

Diagnostics never flip scorecard pass/fail. Organization proxies (label entropy, duplicate headings) may be added later under diagnostic gate only (DD-01 P5).

---

## 6. Check Execution Order

1. Validate check_set against suite (unknown family → abort grade).  
2. Run store-level management checks.  
3. Run search checks per `(query_id, shape)`.  
4. Prefer running `citations_exist` before `citations_support` (support records dependency).  
5. Run diagnostics.  
6. Write `scorecard.json`, `diagnostics.json`, update `MANIFEST.json` digests.  
7. If `eval_held_out`, write/update `scorecard_seal.json` (DD-04 §10).

---

## 7. Result Object Schema

```json
{
  "check_id": "search.citations_support.q_drink_current.organized",
  "family": "citations_support",
  "gate": "scorecard",
  "passed": false,
  "status": "evaluated",
  "shape": "organized",
  "detail": {
    "supporting_count": 0,
    "min_supporting": 1,
    "citations": ["people/morgan.md"],
    "reason": "no_evidence_match"
  }
}
```

`status` ∈ `evaluated | skipped | config_error`.  
`config_error` counts as **failed** for scorecard gate (forces authors to fix suites).

---

## 8. Scorecard File Header

```json
{
  "schema_version": "amb_scorecard_v1",
  "normalization_id": "norm_v1",
  "grader_version": "git:...",
  "check_set_id": "smoke_scorecard_v1",
  "suite": {"id": "smoke", "version": "1.0.0", "digest": "sha256:..."},
  "run_id": "...",
  "graded_at": "2026-08-01T16:00:00Z",
  "results": [],
  "summary": {
    "n_scorecard": 0,
    "n_passed": 0,
    "pass_rate": 0.0,
    "by_family": {},
    "by_role_proxy": {},
    "by_shape": {}
  }
}
```

---

## 9. LLM-as-Judge (non-headline)

If used:

- Separate file: `judgments.json`  
- Must set `"gate": "judgment"`  
- Must not alter `scorecard.summary.pass_rate`  
- Must record `judge_model_id` and `judge_prompt_id`  
- Default: **off** for v1

---

## 10. Negative Fixture Testing

Per DD-02 §8.4, suites ship `fixtures_negative/` stores. Grader CI must:

1. Grade negative stores with the suite check_set.  
2. Assert planted `update_precedence` (and paired answer checks if included) **fail**.  
3. Grade a golden positive store fixture (hand-built) and assert **pass**.

These tests do not require GPU.

---

## 11. Stability and Bit-for-Bit Re-grade

Given identical:

- ledger grading surfaces (stores + search_outputs),  
- suite digest,  
- check_set_id,  
- grader_version,  
- normalization_id,

then each scorecard `passed` boolean and `summary.pass_rate` MUST be identical.

Allowed to change without breaking re-grade claim: `detail.path_hint` only if documented; prefer stable lex tie-break to avoid churn.

---

## 12. Reporting Tables (consumer contract)

Minimum columns for model comparison reports (DD-06 will style):

| Model | Shape | Manage pass | Search pass | Overall | Steps (diag) |
|---|---|---|---|---|---|

Manage pass = mean of management family checks; Search pass = mean of search family checks on that shape; Overall = `pass_rate`.

Self-learning Δ tables must cite baseline run_ids and exposure schedule (DD-07 P14).

---

## 13. Threats and Mitigations (scoring-specific)

| Threat | Mitigation |
|---|---|
| Over-strict exact answers | `answers_any` lists; abstain sets |
| Over-loose fact forms | Short forms; negative fixtures; no substring answers by default |
| Citation gaming (dummy paths with planted words) | Still requires correct answer_match; authors should use distinctive evidence strings |
| Truncated views hiding facts | Fact checks read full store files, not agent views |
| Mixing diagnostic into headline | Separate files + P5 |

---

## 14. Decision Record

| Decision | Choice | Rationale |
|---|---|---|
| Pure function grader | No LLM in v1 grade | P4, re-grade |
| Normalization | `norm_v1` as specified | Determinism |
| Update precedence | Current present ∧ historical forms absent | Strong stale-trap |
| Answer match | Normalized equality to allow-list | Avoid substring loopholes |
| Citations | Exist + evidence support | DD-02 §7.4 |
| Diagnostics | Separate file, non-gating | P5 |
| Judge | Optional side channel | Honesty |

---

## 15. Review Checklist

- [ ] `norm_v1` is acceptable (not too aggressive / too weak).  
- [ ] Hard historical absence for `update_precedence` is what you want in v1.  
- [ ] Answer equality (not substring) is OK given `answers_any`.  
- [ ] Citation support algorithm matches your grounding bar.  
- [ ] Rollups (`by_role_proxy`, `by_shape`) are useful enough for reports.  

**Review outcome:** Approve · Approve with edits · Request rewrite  

---

*End of AMB-DD-05*
