# Agent Memory Bench — Design Document 04  
## Run Ledger and Schema

| Field | Value |
|---|---|
| **Status** | Approved (amended) |
| **Doc ID** | AMB-DD-04 |
| **Version** | 0.1.1 |
| **Date** | 2026-08-01 |
| **Approved** | 2026-08-01 (v0.1.0); amended 2026-08-01 (v0.1.1) |
| **Changelog** | 0.1.1 — Regenerable `figures/` beside `REPORT.md`; slim packs include figures (DD-06). |
| **Project** | `agent_memory_bench` |
| **Audience** | Implementers, re-grade consumers, paper artifact curators |
| **Depends on** | AMB-DD-01 (v0.2.0); AMB-DD-02 (v0.2.0 draft); AMB-DD-03 (Approved) |
| **Supersedes** | — |
| **Next doc** | AMB-DD-05 — Scoring: Scorecard & Diagnostics |
| **Related** | AMB-DD-07 §10 (self-learning ledger extensions) |

---

## 0. Abstract

The **run ledger** is the source of truth for every experiment (DD-01 P1). This document defines the on-disk layout, mandatory JSON/JSONL schemas, content digests, sealing rules for held-out evaluation, and the contract that offline re-grade depends only on ledger bytes plus grader code—not on live model calls.

Self-learning fields are specified as **optional extensions** so v1 static `smoke`/`core` ledgers remain valid without teacher/training directories.

---

## 1. Design Goals

1. **Re-gradable:** `amb regrade <run_dir>` reproduces deterministic scorecard fields bit-for-bit.  
2. **Auditable:** A stranger can see model/prompt pins, suite version, harness, and seeds.  
3. **Portable:** Relative paths; UTF-8; no absolute machine-specific roots in committed artifacts.  
4. **Extensible:** Extra directories allowed if unknown keys are ignored by v1 graders.  
5. **Sealable:** Held-out eval scorecards can be frozen against later teach/train leakage (DD-07 P15).

---

## 2. Top-Level Layout

```text
runs/
  <run_id>/
    config.json                 # mandatory
    MANIFEST.json               # file list + digests
    suite_pin.json              # suite id/version/digest
    prompts/                    # copies or stubs with digests
      manage.<prompt_id>.md
      search.<prompt_id>.md
    stream/                     # materialized chunks as seen by manage
      chunks.jsonl
    stores/
      organized/                # final tree after all manage steps
      verbatim/                 # deterministic dump
      snapshots/                # optional per-chunk organized snapshots
        after_chunk_001/
        ...
    trajectories/
      manage/
        chunk_001.jsonl
        ...
      search/
        organized/
          q_drink_current.jsonl
        verbatim/
          q_drink_current.jsonl
    search_outputs/
      organized/
        q_drink_current.json
      verbatim/
        q_drink_current.json
    scorecard.json              # written by grader
    diagnostics.json
    REPORT.md                   # human summary
    figures/                    # derived matplotlib PNGs (amb report); regenerable
      contrast_bar.png
      scorecard_breakdown.png   # optional
    meta/
      timings.json
      environment.json          # ollama version, GPU, versions
    # --- optional self-learning ---
    episodes/                   # multi-block layouts
    teaching/
    training/
    scorecard_seal.json
```

**`run_id` format (recommended):**  
`{suite_id}__{arm_id}__{YYYYMMDD}_{HHMMSS}__{short_hash}`  
Example: `smoke__baseline__20260801_151200__a1b2c3d`

---

## 3. `config.json` (mandatory)

```json
{
  "schema_version": "amb_ledger_v1",
  "run_id": "smoke__baseline__20260801_151200__a1b2c3d",
  "created_at": "2026-08-01T15:12:00Z",
  "code_version": "git:abcdef0",
  "suite": {
    "id": "smoke",
    "version": "1.0.0",
    "digest": "sha256:..."
  },
  "arm_id": "baseline",
  "protocol": "static",
  "harness_id": "memory_tool_v1",
  "shapes": ["organized", "verbatim"],
  "seed": 42,
  "roles": {
    "manage": {
      "model_id": "ollama/deepseek-r1-distill-qwen-7b:q4_K_M",
      "prompt_id": "manage.memory_tool.v1",
      "prompt_digest": "sha256:...",
      "adapter_id": null,
      "temperature": 0.0,
      "max_steps": 30
    },
    "search": {
      "model_id": "ollama/deepseek-r1-distill-qwen-7b:q4_K_M",
      "prompt_id": "search.memory_tool.v1",
      "prompt_digest": "sha256:...",
      "adapter_id": null,
      "temperature": 0.0,
      "max_steps": 20
    }
  },
  "check_set_id": "smoke_scorecard_v1",
  "diagnostics_set_id": "smoke_diagnostics_v1",
  "agent_visible_chunk_fields": ["id", "t", "timestamp", "channel", "title", "text"],
  "eval_held_out": false,
  "notes": ""
}
```

**Validation:** Missing `roles.manage` or `roles.search` model/prompt pins → reject run as non-conformant.

For self-learning, add (when applicable):

```json
{
  "protocol": "transfer",
  "arm_id": "context",
  "teacher": {
    "model_id": "...",
    "prompt_id": "teacher.informed.self.v1",
    "prompt_digest": "sha256:...",
    "teacher_mode": "informed",
    "teacher_identity": "self_teacher"
  },
  "exposure_schedule": {
    "train_blocks": ["block_01"],
    "eval_blocks": ["block_02"],
    "baseline_matched": true
  },
  "eval_held_out": true,
  "eval_world_id": "morgan_transfer_b_v1"
}
```

---

## 4. Digests and `MANIFEST.json`

Every ledger file that affects grading or reproducibility is listed:

```json
{
  "schema_version": "amb_manifest_v1",
  "files": [
    {"path": "config.json", "sha256": "...", "bytes": 1234},
    {"path": "stores/organized/people/morgan.md", "sha256": "...", "bytes": 560},
    {"path": "search_outputs/organized/q_drink_current.json", "sha256": "...", "bytes": 180}
  ]
}
```

**Rules:**

- Digests use SHA-256 over raw file bytes.  
- Re-grade inputs: final stores, `search_outputs/**`, `stream/chunks.jsonl`, suite pin, check_set id (resolved from repo or vendored copy).  
- Trajectories are **not** required for deterministic v1 scorecard families except diagnostics that count steps (`search_step_count`). If missing, step diagnostics emit `null` with reason `trajectory_absent`.

---

## 5. Stream Materialization

`stream/chunks.jsonl` — one JSON object per line, **already whitelist-filtered** (exactly what manage saw):

```json
{"id":"chunk_003","t":3,"timestamp":"2025-03-12T15:00:00Z","channel":"meeting","title":"Sync with Priya on Atlas","text":"..."}
```

Author-only fields must not appear.

---

## 6. Store Snapshots

- `stores/organized/` — tree after the final management step of the run (or eval block).  
- `stores/verbatim/` — deterministic builder output.  
- `stores/snapshots/after_chunk_XXX/` — optional; recommended for debugging update failures; not required for v1 re-grade of final-store checks.

File contents: UTF-8 markdown. Paths use `/` separators in all JSON references.

---

## 7. Trajectories

### 7.1 Manage: `trajectories/manage/chunk_TTT.jsonl`

One step per line:

```json
{
  "step": 1,
  "ts": "2026-08-01T15:12:01.012Z",
  "event": "tool_call",
  "tool": "view",
  "arguments": {"path": "."},
  "observation": {"ok": true, "listing": ["people/", "projects/"]},
  "tokens_in": 1200,
  "tokens_out": 80
}
```

Terminal event:

```json
{"step": 12, "event": "done", "reason": "agent_done"}
```

or `"reason": "max_steps_exceeded" | "protocol_error" | ...` (DD-03 §10).

### 7.2 Search: `trajectories/search/{shape}/{query_id}.jsonl`

Same step schema. Must end with `event: "final"` or a done tool whose arguments include the final payload.

---

## 8. Search Outputs

`search_outputs/{shape}/{query_id}.json` is the **grading surface** for search (even if also embedded in trajectory):

```json
{
  "query_id": "q_drink_current",
  "shape": "organized",
  "answer": "coffee",
  "citations": ["people/morgan.md"],
  "confidence": "high",
  "status": "ok",
  "error_code": null
}
```

**Normative:** Graders read this file, not free-text trajectory scraping. Runner MUST write it on every search attempt.

On failure:

```json
{
  "query_id": "q_drink_current",
  "shape": "organized",
  "answer": null,
  "citations": [],
  "status": "error",
  "error_code": "max_steps_exceeded"
}
```

---

## 9. Scorecard and Diagnostics Files

Written by the grader (DD-05). Ledger runner may leave placeholders absent until grade.

### 9.1 `scorecard.json` (shape preview)

```json
{
  "schema_version": "amb_scorecard_v1",
  "check_set_id": "smoke_scorecard_v1",
  "suite": {"id": "smoke", "version": "1.0.0", "digest": "sha256:..."},
  "run_id": "...",
  "results": [
    {
      "check_id": "mgmt.fact_present.morgan_drink_current",
      "family": "fact_present",
      "gate": "scorecard",
      "passed": true,
      "detail": {"matched_form": "coffee", "path_hint": "people/morgan.md"}
    }
  ],
  "summary": {
    "n_scorecard": 20,
    "n_passed": 14,
    "pass_rate": 0.7,
    "by_family": {"fact_present": {"n": 5, "passed": 4}}
  }
}
```

### 9.2 `diagnostics.json`

Same result list pattern with `"gate": "diagnostic"`. Must not be folded into `summary.pass_rate`.

---

## 10. Sealing (held-out eval)

When `config.eval_held_out` is true, after grading the eval block:

`scorecard_seal.json`:

```json
{
  "sealed_at": "2026-08-01T16:00:00Z",
  "scorecard_sha256": "...",
  "eval_world_id": "morgan_transfer_b_v1",
  "eval_blocks": ["block_02"],
  "forbid_train_export": true,
  "forbid_teach_until_after": "2026-08-01T16:00:00Z"
}
```

Training dataset builders (DD-07b) MUST refuse to include trajectories from sealed eval worlds for the adapter version under claim. Violations are detectable by auditing `training/dataset_digest.json` world ids against the seal.

---

## 11. Environment and Timings

`meta/environment.json`:

```json
{
  "python": "3.12.x",
  "ollama_version": "...",
  "cuda_or_metal": "cuda-12.x",
  "gpu_name": "RTX 3070",
  "amb_package_version": "0.1.0"
}
```

`meta/timings.json`: wall times per chunk, per query, total; optional peak VRAM.

---

## 12. Multi-Episode Layout (optional)

```text
episodes/
  block_01/
    config_fragment.json
    stream/
    stores/
    trajectories/
    search_outputs/
    scorecard.json
  block_02/
    ...
teaching/
  teacher_mode.json
  skills_snapshot/
  policy_snapshot/
  teacher_trajectory.jsonl
training/
  stage.json
  dataset_digest.json
  adapter_id.txt
  train_metrics.json
```

Static v1 runs omit `episodes/` and keep the flat layout in §2.

---

## 13. Prompt Vendoring

`prompts/` inside the run MUST contain the exact prompt bodies used (or a pointer file):

```json
{
  "prompt_id": "manage.memory_tool.v1",
  "sha256": "...",
  "source_path": "prompts/manage/memory_tool.v1.md",
  "body_path": "manage.memory_tool.v1.md"
}
```

Prefer copying bodies into the run so rehydration does not depend on later prompt edits.

---

## 14. Schema Versioning

| Schema | Version string | Compatibility |
|---|---|---|
| Ledger | `amb_ledger_v1` | Additive optional keys OK |
| Manifest | `amb_manifest_v1` | — |
| Scorecard | `amb_scorecard_v1` | DD-05 owns semantics |
| Search output | implicit in §8 | Additive keys OK |

Breaking changes bump the version suffix (`v2`) and require a migration note in DD-04 changelog.

Machine-readable JSON Schema files will live at `schemas/ledger/*.json` at implementation time; this doc is normative until those files land.

---

## 15. Re-grade Contract

Inputs sufficient for deterministic scorecard:

1. `config.json` (check_set_id, shapes, suite pin)  
2. Suite fixtures from repo at pinned version **or** vendored `suite/` snapshot in the run (recommended for public releases)  
3. `stores/organized/**`, `stores/verbatim/**`  
4. `search_outputs/**`  
5. Grader code version  

Not required: live Ollama, trajectories (except step diagnostics), teaching/, training/.

**Bit-for-bit:** `summary` and each `results[i].passed` must match prior `scorecard.json` when grader code and fixtures are unchanged. `detail` strings MAY differ in path hints if multiple matches exist; prefer stable tie-break (lexicographic first path).

---

## 16. Public Release Subset

For GitHub/HF display packs, a run MAY ship a **slim** archive:

- `config.json`, `MANIFEST.json`, `scorecard.json`, `diagnostics.json`, `REPORT.md`  
- `figures/**` when present (derived; may be regenerated via `amb report`)  
- `stores/**`  
- `search_outputs/**`  
- `prompts/**`  
- omit full trajectories if size-bound (note omission in REPORT)

Slim packs remain re-gradable for v1 scorecard families.

---

## 17. Decision Record

| Decision | Choice | Rationale |
|---|---|---|
| Source of truth | On-disk ledger | P1 |
| Search grading surface | `search_outputs/*.json` | Stable vs trajectory scrape |
| Whitelist stream copy | `stream/chunks.jsonl` | Audit what agent saw |
| Digests | SHA-256 manifest | Tamper evidence |
| Seal file | `scorecard_seal.json` | P15 |
| Optional trajectories for scorecard | Not required | Smaller artifacts |
| Vendor prompts into run | Yes | Reproducibility |

---

## 18. Review Checklist

- [ ] Layout is complete enough to implement the runner.  
- [ ] `config.json` role pins match DD-03.  
- [ ] Re-grade contract matches how you want public artifacts to work.  
- [ ] Seal / multi-episode extensions are clear without blocking static v1.  
- [ ] Slim public pack policy is acceptable.  

**Review outcome:** Approve · Approve with edits · Request rewrite  

---

*End of AMB-DD-04*
