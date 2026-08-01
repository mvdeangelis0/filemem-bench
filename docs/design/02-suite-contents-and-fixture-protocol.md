# Agent Memory Bench — Design Document 02  
## Suite Contents and Fixture Protocol

| Field | Value |
|---|---|
| **Status** | Approved |
| **Doc ID** | AMB-DD-02 |
| **Version** | 0.2.0 |
| **Date** | 2026-08-01 |
| **Approved** | 2026-08-01 |
| **Changelog** | 0.2.0 — Fact-matching contract (§6.4); evidence-based citations; agent-visible metadata whitelist (§5.4) |
| **Project** | `agent_memory_bench` |
| **Audience** | Contributors authoring tasks; reviewers of scientific claims |
| **Depends on** | AMB-DD-01 (Approved) |
| **Supersedes** | — |
| **Next doc** | AMB-DD-03 — Agent Contracts & Tool Harness |
| **Related** | AMB-DD-05 (scoring semantics); this doc defines *what* is checked, DD-05 defines *how* checks are computed |

---

## 0. Abstract

This document specifies the **contents** of the v1 evaluation suites (`smoke`, `core`) and the **fixture protocol** used to author them. A fixture is a versioned, human-editable package: an ordered stream of memory chunks, a set of search queries with gold answers, and a declarative list of deterministic checks. Suites differ only in volume and coverage; they share one schema and one ingestion rule (incremental management).

The protocol is designed so that contributors can add or tweak tasks and checks primarily by editing YAML (or JSON), without changing harness code. Exploratory experiments live outside named suites so they cannot silently alter published comparisons.

---

## 1. Purpose and Claims Boundary

### 1.1 What a suite is allowed to claim

A named suite (`smoke`, `core`) supports claims of the form:

> Under harness \(H\), model \(m\), and suite \(S\) version \(v\), management and search achieve scorecard rates \(R\) on organized vs verbatim stores constructed from stream \(X_S\).

Claims are invalid if the suite version, fixture digests, or check-set IDs are omitted from the run config.

### 1.2 What a suite is not

- Not a substitute for LoCoMo / PersonaMem / REALTALK / ALFWorld.
- Not a taxonomy-quality benchmark (organization metrics are diagnostics; see DD-01 P5).
- Not a self-teaching benchmark (DD-07).

---

## 2. Repository Layout (Fixtures)

```text
agent_memory_bench/
  suites/
    smoke/
      suite.yaml                 # suite metadata, check-set pin, sizes
      stream/
        chunks.yaml              # ordered chunks x_1 .. x_T
      gold/
        facts.yaml               # world state after full stream (for management checks)
        queries.yaml             # search queries + gold answers + citations hints
      checks/
        scorecard.yaml           # which check IDs run; parameters
        diagnostics.yaml         # non-gating metrics to emit
      README.md                  # human summary of the fictional world
    core/
      ...                        # same shape, larger coverage
    exploratory/                 # optional; never cited in v1 headline tables
      <experiment_name>/
        ...
  schemas/
    suite.schema.json
    chunk.schema.json
    query.schema.json
    checks.schema.json
```

**Normative rule:** Anything under `suites/smoke` or `suites/core` is versioned. Changing it bumps `suite.yaml` → `version` and changes the content digest recorded in every run ledger.

---

## 3. Suite Tiers

### 3.1 Size targets (v1)

| Tier | Chunks \(T\) | Search queries | Required phenomena | Wall-clock intent |
|---|---|---|---|---|
| **`smoke`** | 8–12 | 8–10 | ≥1 preference update; ≥1 multi-hop; ≥1 protected fact | Pipeline proof on one local model |
| **`core`** | 20–30 | 15–20 | ≥2 updates/contradictions; multi-hop; temporal; meeting→action; stale-trap | First publishable contrast tables |
| **`paper-lite`** | deferred | deferred | growth checkpoints | Out of v1 (DD-01 non-goal) |

Exact counts are pinned in each `suite.yaml`. Implementations must fail closed if a suite file violates its own declared `min_chunks` / `min_queries`.

### 3.2 Shared protocol (DD-01 P7)

Both tiers use:

- Incremental management: \(M_t = \mathrm{manage}(x_t, M_{t-1})\), \(M_0 = \varnothing\).
- Verbatim builder on the same ordered stream.
- Search over frozen stores for both shapes.
- The same check *families*; `core` enables more instances and stricter variants where noted.

### 3.3 `smoke` as a subset relationship (recommended)

`smoke` SHOULD be a **strict subset** of `core`’s world (same entities and early chunks), truncated and with a subset of queries. That lets a failing `smoke` check predict `core` failure modes without maintaining two unrelated fictional universes.

If `smoke` diverges into a separate world, `suite.yaml` must set `world_id` differently and reports must not imply subset transfer.

---

## 4. Fictional World (Domain Contract)

### 4.1 World genre

Synthetic **personal knowledge base** for a single user (call the user **Morgan** in v1 fixtures unless a suite overrides `persona_name`). Content covers:

| Category | Examples |
|---|---|
| People | Names, relationships, contact facts |
| Preferences | Food, tools, scheduling prefs (subject to updates) |
| Projects | Active workstreams, deadlines, owners |
| Meetings | Date/time, attendees, decisions, action items |
| Constraints | “Never delete …”, “Always keep …”, travel blackouts |

### 4.2 Design rules for the world

1. **Closed world for gold.** Every scored fact must be introduced in some chunk. Graders never require external knowledge.
2. **Plant updates explicitly.** At least one preference or plan changes later in the stream; gold marks *current* vs *historical*.
3. **Plant a stale trap.** At least one query that fails if the store keeps the pre-update value as current (DD-01 success criterion #5).
4. **Disambiguation pressure.** Two entities share a first name or project abbreviation so naive substring dumps can confuse search.
5. **No PII of real people.** All names, employers, and addresses are fictional.

### 4.3 World README

Each suite’s `README.md` describes the cast and timeline in prose for humans. It is **not** fed to agents unless a future mode explicitly adds it (v1 does not).

---

## 5. Stream Chunks

### 5.1 Chunk object

Each chunk \(x_t\) is a structured record:

```yaml
id: chunk_003
t: 3                              # 1-indexed order; must be contiguous
timestamp: "2025-03-12T15:00:00Z" # fictional event time
channel: meeting                  # note | meeting | message | email | system
title: "Sync with Priya on Atlas"
text: |
  Meeting notes. Attendees: Morgan, Priya Chen.
  Decision: ship Atlas v0.2 by March 28.
  Action: Priya owns API review.
tags: [project:atlas, person:priya]
introduces:                       # optional author hints for gold maintenance
  - fact_id: fact_atlas_deadline
supersedes:                       # optional
  - fact_id: fact_atlas_deadline_old
```

**Normative fields:** `id`, `t`, `text`. All others are optional authoring aids and are subject to the visibility rules in §5.4.

### 5.2 Ordering and idempotency

- Chunks are applied in ascending `t`.
- Re-running management on the same suite must use the same order.
- Graders key off store contents and declared facts, never off fields withheld from agents (§5.4).

### 5.3 Verbatim materialization

The verbatim builder writes one file per chunk (or per `channel` session group if `suite.yaml` sets `verbatim_grouping: session`). Default for v1:

```text
verbatim/chunks/chunk_001.md
verbatim/chunks/chunk_002.md
...
```

Each file body is the chunk `text` plus only **agent-visible** header fields from §5.4 (default: `id`, `timestamp` if whitelisted). No model calls. Author-only fields (`introduces`, `supersedes`, etc.) must never appear in verbatim files.

### 5.4 Agent-visible metadata whitelist

Chunk records may contain authoring metadata that must not leak into agent context. The harness exposes **only** fields listed in the suite’s whitelist.

**Default whitelist (v1):**

| Field | Management sees | Search sees | Notes |
|---|---|---|---|
| `id` | yes | only if present in store files | Stable chunk id |
| `t` | yes | no (unless written into store) | Order index |
| `timestamp` | yes | only if in store | Fictional event time |
| `channel` | yes | only if in store | note/meeting/… |
| `title` | yes | only if in store | Short heading |
| `text` | yes | only via store | Sole required body |

**Default denylist (never agent-visible):**

`introduces`, `supersedes`, `tags` *(unless suite explicitly whitelists `tags`)*, any `gold_*` keys, fact ids, check ids, and paths into `gold/` or `checks/`.

Suites MAY extend the whitelist in `suite.yaml`:

```yaml
agent_visible_chunk_fields: [id, t, timestamp, channel, title, text]
```

Validation fails if any denylisted field is listed as visible. DD-03 binds the harness observation envelope to this whitelist. Leaking denylisted fields into prompts, tool observations, or verbatim files is a protocol violation.

---

## 6. Gold World State (`facts.yaml`)

### 6.1 Why facts exist

Management grading should not scrape free-form prose hoping for luck. Authors declare an explicit **gold fact table** representing the correct world state **after the full stream**.

```yaml
facts:
  - id: fact_morgan_drink_current
    kind: preference
    subject: Morgan
    predicate: preferred_drink
    value: coffee
    match:
      mode: normalized_any          # see §6.4
      forms_any: ["coffee", "Coffee"]
      # optional regexes — evaluated after normalization unless mode says otherwise
      # regex_any: ["(?i)\\bcoffee\\b"]
    status: current
    introduced_in: chunk_012
    supersedes: fact_morgan_drink_tea
    protected: false
    evidence_spans:
      - chunk_id: chunk_012
        must_include: "prefers coffee"

  - id: fact_morgan_drink_tea
    kind: preference
    subject: Morgan
    predicate: preferred_drink
    value: tea
    match:
      mode: normalized_any
      forms_any: ["tea", "Tea"]
    status: historical
    introduced_in: chunk_005
    superseded_by: fact_morgan_drink_current
    protected: false
```

### 6.2 Fact statuses

| Status | Meaning for graders |
|---|---|
| `current` | Must be recoverable as live knowledge (present; not contradicted by another current fact) |
| `historical` | May remain in store if clearly non-current; must **not** be the sole answer to “what is current?” queries |
| `protected` | Must still exist in some file at end of management (`protected: true`) |

### 6.3 Consistency rules

- Every `introduced_in` / supersession edge must reference a real chunk id.
- No two `current` facts may share the same `(subject, predicate)` unless `cardinality: multi` is set.
- Every fact used by a scorecard check MUST declare a `match` block (§6.4).
- Suite validation (`amb validate-suite`) fails on violations before any model run.

### 6.4 Deterministic fact-matching contract

Management checks (`fact_present`, `update_precedence`, `protected_survives`) do **not** free-form semantic judge the store. They apply a declared match contract.

**Scan corpus.** Unless `args.paths` restricts scope, the grader concatenates all UTF-8 file bodies under the target store root (organized or as specified), using NFC normalization and `\n` line endings.

**Normalization (default `norm_v1`, detailed in DD-05):** lowercase; Unicode NFKC; strip combining marks optional flag default off; collapse whitespace; strip leading/trailing punctuation on token edges for `normalized_any`.

**Modes:**

| `match.mode` | Pass condition |
|---|---|
| `normalized_any` | At least one string in `forms_any`, after `norm_v1`, occurs as a substring of the scan corpus (also normalized). Default for v1. |
| `regex_any` | At least one pattern in `regex_any` matches the raw or normalized corpus per `regex_flags` (default: multiline, case-insensitive). |
| `normalized_all` | Every string in `forms_all` occurs (AND). |
| `absent_normalized_any` | Used for negative conditions: none of `forms_any` occur (historical-as-current traps). |

**Update precedence.** `update_precedence` passes iff the `current` fact matches under its contract AND the `historical` fact either (a) fails `normalized_any` over the corpus, OR (b) appears only in spans marked historical per suite rules (v1 default: **(a) only** — simplest, strongest). Soft historical retention with explicit markers is deferred to a later check_set version.

**Absence of fuzzy embedding match.** No embedding similarity, no LLM judge, no edit-distance soft match in v1 scorecard fact checks. Exploratory families may experiment under `gate: diagnostic` only.

**Author obligation.** `forms_any` must be short literal cues expected in a well-managed store (e.g. `coffee`), not entire sentences, unless using `regex_any` deliberately. Evidence spans on chunks (§6 + queries) remain separate from store match forms.

---

## 7. Queries (`queries.yaml`)

### 7.1 Query object

```yaml
queries:
  - id: q_drink_current
    tier: smoke                    # smoke | core
    category: update_awareness     # see §7.2
    q: "What does Morgan prefer to drink?"
    gold:
      answers_any:
        - "coffee"
        - "Coffee"
      answers_forbidden_any:       # if present as the answer, fail
        - "tea"
    citations:
      # Evidence-based grounding (normative for scorecard)
      evidence_any:
        - must_include_any: ["coffee", "prefers coffee"]
          # cited file body must contain ≥1 form (after norm_v1)
      min_supporting_citations: 1
    shapes: [organized, verbatim]  # which stores to grade
    checks:
      - answer_match
      - citations_exist
      - citations_support
```

### 7.2 Query categories (coverage taxonomy)

Every suite must declare counts per category in `suite.yaml`. v1 categories:

| Category | Intent |
|---|---|
| `single_hop` | Fact stated in one chunk |
| `multi_hop` | Combine ≥2 facts |
| `temporal` | Before/after, dates, ordering |
| `update_awareness` | Prefers post-update state |
| `meeting_action` | Decisions / action items / owners |
| `negative` | Correctly answer “not stated” / unknown when gold says unknown |
| `constraint` | Behavior about protected content (usually management-side; rare in search) |

`smoke` minimum: ≥1 `single_hop`, ≥1 `multi_hop`, ≥1 `update_awareness`.  
`core` minimum: all categories except `constraint` optional; ≥2 `update_awareness`.

### 7.3 Unknown / abstention

If `gold.abstain: true`, the only accepting answers are the suite’s normalized abstention set (e.g. `"unknown"`, `"not stated"`). This prevents reward hacking by guessing. Abstain queries still require `citations_exist` only if the suite asks for justifying “not in store” citations; default v1: abstain queries grade `answer_match` only.

### 7.4 Evidence-based citation contract

Decorative citations are insufficient for scorecard grounding.

| Check | Pass condition |
|---|---|
| `citations_exist` | Every cited path exists in the graded store; paths are normalized (no `..` escape). Empty \(\Gamma\) fails unless query sets `citations.allow_empty: true` (abstain-only). |
| `citations_support` | At least `min_supporting_citations` (default 1) cited files each contain ≥1 evidence form from `citations.evidence_any` under `norm_v1` (or `regex_any` if declared). |

**Tier policy:**

- `smoke`: `citations_exist` required; `citations_support` required on ≥50% of non-abstain queries (suite validator enforces count).  
- `core`: both required on **all** non-abstain queries.

Algorithms and path normalization: AMB-DD-05. Authors must keep `evidence_any` aligned with chunk text and expected store content.

---

## 8. Deterministic Checks (Attachment Protocol)

This section defines **how checks attach to suites**. Algorithms and normalization are specified in AMB-DD-05.

### 8.1 Check instance

A check instance is a declarative record:

```yaml
# suites/core/checks/scorecard.yaml
check_set_id: core_scorecard_v1
checks:
  - id: mgmt.fact_present.morgan_drink_current
    family: fact_present
    gate: scorecard              # scorecard | diagnostic
    args:
      fact_id: fact_morgan_drink_current
      store: organized

  - id: mgmt.update_precedence.morgan_drink
    family: update_precedence
    gate: scorecard
    args:
      current_fact_id: fact_morgan_drink_current
      historical_fact_id: fact_morgan_drink_tea
      store: organized

  - id: mgmt.protected_survives.emergency_contact
    family: protected_survives
    gate: scorecard
    args:
      fact_id: fact_emergency_contact
      store: organized

  - id: search.answer_match.q_drink_current
    family: answer_match
    gate: scorecard
    args:
      query_id: q_drink_current
      # shapes inherited from query unless overridden

  - id: search.citations_exist.q_drink_current
    family: citations_exist
    gate: scorecard
    args:
      query_id: q_drink_current

  - id: search.citations_support.q_drink_current
    family: citations_support
    gate: scorecard
    args:
      query_id: q_drink_current

  - id: diag.file_count
    family: store_file_count
    gate: diagnostic
    args:
      store: organized
```

### 8.2 Families available in v1 (minimum set)

| Family | Gate default | Touches |
|---|---|---|
| `fact_present` | scorecard | organized store vs gold fact **match contract** (§6.4) |
| `update_precedence` | scorecard | current vs historical per §6.4 |
| `protected_survives` | scorecard | protected facts/paths |
| `answer_match` | scorecard | search outputs vs gold |
| `citations_exist` | scorecard | citation paths ∈ store |
| `citations_support` | scorecard | cited file contains evidence (§7.4); required on core non-abstain |
| `store_file_count` | diagnostic | counts |
| `store_max_depth` | diagnostic | depth |
| `search_step_count` | diagnostic | trajectory length |

Contributors may add families under `exploratory/` freely. Promoting a family into `smoke`/`core` requires a DD-05 amendment and a `check_set_id` bump.

### 8.3 Tweaking without code changes

Supported edits (no Python required):

1. Toggle a check on/off by removing/adding its block (or `enabled: false`).
2. Change `args` (fact ids, query ids, thresholds).
3. Move `gate` from `scorecard` → `diagnostic` for soft experiments (must bump `check_set_id` if the suite is named).
4. Add queries/chunks/facts that existing families can reference.

Supported edits (small Python, encouraged in exploratory):

5. Implement a new family in `graders/families/`, register it, reference it from YAML.

### 8.4 Planted grader-bite requirement

Each of `smoke` and `core` MUST include at least one `update_precedence` check paired with an `update_awareness` query such that:

- A store that retains only the pre-update value fails both, and  
- A correctly updated store passes both.

Validation proves this on **fixture-level counterexamples** shipped under `suites/<tier>/fixtures_negative/` (hand-built bad stores). No model needed.

---

## 9. Suite Manifest (`suite.yaml`)

```yaml
id: smoke
version: "1.0.0"
world_id: morgan_personal_v1
protocol: amb_v1
shapes: [organized, verbatim]
harness_default: memory_tool_v1
ingestion: incremental
min_chunks: 8
max_chunks: 12
min_queries: 8
check_set_id: smoke_scorecard_v1
diagnostics_set_id: smoke_diagnostics_v1
categories_required:
  single_hop: 1
  multi_hop: 1
  update_awareness: 1
verbatim_grouping: per_chunk
notes: |
  Subset of core world; truncated after chunk_010.
```

Semver rules:

- **PATCH:** typo fixes that do not change gold or checks.  
- **MINOR:** add queries/checks that do not change existing IDs’ meanings.  
- **MAJOR:** change gold answers, fact values, chunk texts that affect gold, or remove/repurpose check IDs.

Published tables must show `suite_id@version` and `check_set_id`.

---

## 10. Authoring Workflow

### 10.1 Add a fact-bearing chunk

1. Append chunk to `stream/chunks.yaml`.  
2. Update `gold/facts.yaml` (introduce / supersede).  
3. Optionally add a query that reads the new fact.  
4. Attach `fact_present` / `update_precedence` checks.  
5. Run `amb validate-suite suites/core`.  
6. Run negative-store tests for update traps if applicable.

### 10.2 Ad hoc experimentation

1. Copy a suite skeleton to `suites/exploratory/<name>/`.  
2. Tweak checks aggressively.  
3. Record runs under `runs/exploratory/…`.  
4. Promote into `core` only via PR that bumps versions and updates this doc’s coverage tables if categories change.

### 10.3 What agents see vs what authors see

| Artifact | Management agent | Search agent | Grader |
|---|---|---|---|
| Chunk fields on whitelist (§5.4) | yes | only via store | n/a |
| Chunk denylisted metadata | **no** | **no** | n/a |
| `facts.yaml` | no | no | yes |
| `queries.yaml` gold / evidence | no | no (sees `q` only) | yes |
| `checks/*.yaml` | no | no | yes |

Leaking gold or denylisted metadata into agent context is a protocol violation.

---

## 11. Coverage Matrix (v1 Targets)

To be filled concretely when fixtures are authored; this table is the acceptance checklist for fixture complete-ness.

| Phenomenon | smoke | core |
|---|---|---|
| Preference update + stale trap | required | required (≥2) |
| Meeting → action item + owner | required | required |
| Multi-hop (person × project) | required | required |
| Temporal (before date D) | optional | required |
| Name disambiguation | optional | required |
| Protected fact survival | required | required |
| Abstain / unknown | optional | required |
| Verbatim vs organized contrast on same queries | required | required |

---

## 12. Validation Gates

Before a suite version can be marked `ready`:

1. Schema validation passes.  
2. Category minima met.  
3. Fact/chunk referential integrity holds.  
4. Negative fixtures demonstrate grader bite for at least one update trap.  
5. `README.md` exists and matches cast names used in facts.  
6. Content digest is reproducible (`amb suite-digest`).  
7. Every scorecard fact has a valid `match` block (§6.4).  
8. Citation policy met (§7.4): core non-abstain queries include `citations_support`.  
9. `agent_visible_chunk_fields` does not include denylisted keys (§5.4).

---

## 13. Threats to Validity (Suite-Level)

| Threat | Mitigation |
|---|---|
| Gold answers too brittle | `answers_any` allow-lists; normalization in DD-05 |
| Fact match too loose/tight | Explicit `match.mode` + forms; negative fixtures |
| Citations without evidence | `citations_support` on scorecard |
| Chunks leak answer format | Author review; prefer natural notes over QA pairs in stream |
| Metadata side-channels | Whitelist §5.4 |
| smoke/core world drift | Prefer subset relation; separate `world_id` if not |
| Check overfitting to one model’s phrasing | Prefer fact-table checks over raw transcript match for management |
| Exploratory contamination | Namespace + reporting policy (DD-06) |

---

## 14. Decision Record (this doc)

| Decision | Choice | Rationale |
|---|---|---|
| Fixture format | YAML-first, JSON-schema validated | Human tweakability |
| Gold representation | Explicit fact table + query gold | Deterministic management grading |
| Fact matching | Declared `match` contract; no embeddings in scorecard | Auditability |
| Citations | Exist + evidence-support | Real grounding |
| Agent chunk metadata | Whitelist / denylist | No gold leakage |
| smoke vs core | Shared protocol; smoke ideally subset of core world | Predictable scaling |
| Check attachment | Declarative `scorecard.yaml` / `diagnostics.yaml` | Tweak without code |
| Verbatim default | One file per chunk; whitelist headers only | Simplest zero-curation baseline |
| Negative fixtures | Required for update traps | Prove graders have teeth |
| Exploratory path | `suites/exploratory/` | Ad hoc without breaking science |

---

## 15. Review Checklist

- [ ] Size targets for smoke/core are acceptable.
- [ ] World rules (closed world, updates, stale trap, no real PII) are clear.
- [ ] Fact-matching contract (§6.4) is strict enough / not too brittle.
- [ ] Evidence-based citation policy (§7.4) is acceptable.
- [ ] Metadata whitelist (§5.4) matches what you want agents to see.
- [ ] Check attachment protocol matches how you want to experiment.
- [ ] Subset relationship smoke⊆core is desired (or call out preference for separate worlds).
- [ ] Coverage matrix matches what you want in the first publishable table.

**Review outcome:** Approve · Approve with edits · Request rewrite

---

*End of AMB-DD-02*
