# Agent Memory Bench — Design Document 06  
## Collaboration, Display, and Release

| Field | Value |
|---|---|
| **Status** | Approved |
| **Doc ID** | AMB-DD-06 |
| **Version** | 0.1.0 |
| **Date** | 2026-08-01 |
| **Approved** | 2026-08-01 |
| **Project** | `agent_memory_bench` |
| **Audience** | Maintainers, external contributors, readers of public results |
| **Depends on** | AMB-DD-01 … AMB-DD-05; AMB-DD-07 (claim language for self-learning releases) |
| **Supersedes** | — |
| **Next docs** | Implementation plan; AMB-DD-07a / 07b (self-learning deep dives) |

---

## 0. Abstract

This document specifies how `agent_memory_bench` is **collaborated on**, **displayed publicly**, and **released** as reproducible evidence. It covers repository layout for contributors, contribution workflows (tasks, checks, runs), CI gates, licensing, results catalog format, report templates, and what must accompany any public claim table.

Goals (from DD-01): maximum open source, collaboration, and display—without sacrificing academic and testing rigor.

---

## 1. Public Surfaces

| Surface | Purpose | Source of truth |
|---|---|---|
| GitHub (or equivalent) repo | Code, fixtures, design docs, CI | git |
| `results/` catalog | Indexed run pointers + summary tables | ledger digests |
| Per-run `REPORT.md` | Human-readable single-run story | generated from ledger |
| Optional HF Space / Pages site | Browse tables & stores | reads `results/` + slim packs |
| Optional OSS telemetry (Langfuse/Phoenix) | Dev debugging | never required for claims |

Proprietary eval SaaS is not a release dependency (DD-01).

---

## 2. Repository Layout (contributor view)

```text
agent_memory_bench/
  README.md
  LICENSE
  CITATION.cff
  pyproject.toml
  docs/
    design/                    # AMB-DD-01… (this series)
    guides/
      adding_a_task.md
      running_smoke.md
      interpreting_scorecards.md
  prompts/
  suites/
    smoke/
    core/
    exploratory/
  schemas/
  src/amb/                      # package (runner, harness, graders)
  tests/
    graders/                    # negative fixtures, norm_v1, etc.
    suites/                     # validate-suite
  results/
    INDEX.md
    catalogs/
      smoke_v1.md
      core_v1.md
    runs/                       # optional git-lfs / release assets
      <run_id>/                 # slim or full packs
  scripts/
    amb_cli.py                  # or `amb` entrypoint
```

Large full ledgers MAY live in Git LFS, release tarballs, or object storage with URLs recorded in `results/catalogs/*.md`. Slim packs (DD-04 §16) are preferred in-git.

---

## 3. Licensing and Citation

### 3.1 Default recommendation

| Asset | License |
|---|---|
| Code | Apache-2.0 (preferred) or MIT |
| Fixtures / synthetic text | CC-BY-4.0 |
| Design docs | CC-BY-4.0 |
| Model weights / adapters | Per upstream + separate adapter license note |

Final SPDX identifiers are pinned in `LICENSE` / `NOTICE` at implementation init. This doc mandates **OSI-approved code license** and **attribution-capable** fixture license.

### 3.2 Citation

`CITATION.cff` must exist before the first public results release. Paper-style claims cite: suite id@version, check_set_id, harness_id, role model/prompt digests, run_ids, grader_version.

---

## 4. Contribution Workflows

### 4.1 Add or edit a task (fixtures)

1. Branch from `main`.  
2. Edit `suites/<tier>/` per DD-02 (chunks, facts, queries, checks).  
3. Bump suite `version` semver appropriately.  
4. Run `amb validate-suite suites/<tier>`.  
5. Run negative-fixture tests.  
6. PR checklist (template in `.github/PULL_REQUEST_TEMPLATE.md`):  
   - [ ] No denylisted metadata marked agent-visible  
   - [ ] Fact `match` blocks present  
   - [ ] Citation evidence on required queries  
   - [ ] Stale-trap still covered if updates changed  

### 4.2 Add a check family

1. Implement under `src/amb/graders/families/`.  
2. Add unit tests + negative fixtures.  
3. Document in DD-05 amendment or grader README.  
4. New families enter `exploratory/` first; promotion to `smoke`/`core` requires check_set_id bump and maintainer approval.

### 4.3 Contribute a run (results)

1. Produce ledger via `amb run ...`.  
2. `amb regrade` locally; confirm stable scorecard.  
3. Export slim pack.  
4. PR adding `results/runs/<run_id>/` + catalog row.  
5. CI verifies manifest digests and re-grade bit-for-bit on scorecard booleans.

### 4.4 Exploratory vs named suites

`suites/exploratory/**` and `results/runs/*exploratory*` MUST NOT appear in headline `core_v1` / `smoke_v1` catalog tables. They may have their own catalog page labeled **non-comparable**.

---

## 5. CI Gates

Minimum CI on every PR:

| Job | Requirement |
|---|---|
| `lint` | Format/type as project standard |
| `unit` | Grader + harness unit tests (CPU) |
| `validate-suites` | All named suites pass DD-02 validation gates |
| `negative-fixtures` | Planted failures fail; golden stores pass |
| `regrade-fixture` | Checked-in mini ledger regrades stably |

GPU / Ollama jobs are **nightly or manual**, not merge-blocking, until infra is stable.

Self-learning training jobs are never merge-blocking for v1.

---

## 6. CLI Surface (user-facing)

Minimum commands:

```text
amb validate-suite <path>
amb run --suite smoke --arm baseline --manage-model ... --search-model ...
amb regrade <run_dir>
amb report <run_dir>              # regenerate REPORT.md
amb suite-digest <path>
amb results-index                 # rebuild results/INDEX.md
```

Role model/prompt flags must exist (DD-01 / DD-03). Convenience `--model` that sets both roles is allowed but must still write per-role pins into `config.json`.

---

## 7. Display: Reports and Catalogs

### 7.1 Per-run `REPORT.md` (mandatory sections)

1. Title: run_id, suite@version, arm, date  
2. Config summary: harness, seeds, per-role model_id / prompt_id / adapter_id  
3. Scorecard summary table (overall, manage proxy, search proxy × shape)  
4. Failed checks list with one-line reasons  
5. Diagnostics highlights (steps, file counts)  
6. Artifact pointers (manifest digest, seal if any)  
7. Claims disclaimer: what this run does *not* show  

### 7.2 Catalog tables

`results/catalogs/core_v1.md` example columns:

| run_id | model_manage | model_search | shape focus | manage% | search% org | search% verb | overall% | suite | check_set | seed |
|---|---|---|---|---|---|---|---|---|---|---|

Rules:

- Every row links to run dir or release URL.  
- Missing digests → row rejected by `amb results-index`.  
- Self-learning catalogs require Δ vs exposure-matched baseline run_id (DD-07).

### 7.3 Optional web display

If a Space/site is added:

- Read-only rendering of catalogs + store browser for slim packs.  
- No silent re-scoring with different grader versions; show `grader_version`.  
- Clear badge: **Static v1** vs **Self-learning (experimental)**.

---

## 8. Release Types

| Release | Contents | When |
|---|---|---|
| `v0.x` library | Code + suites + docs; few/no GPU results | After DD series accepted + smoke runnable |
| Results drop | Slim packs + catalogs + REPORT rollup | After `core` multi-model table exists |
| Adapter drop | LoRA weights + train digests + license | Self-learning tune arm |
| Paper pack | Frozen suite digests + all cited run_ids | Preprint/camera-ready |

**Semantic versioning for the Python package** is independent of suite semver. Suites version inside `suite.yaml`.

---

## 9. Claim Hygiene for Public Posts

Any blog, README badge, or paper table that cites AMB must include:

1. `suite_id@version` + `check_set_id`  
2. `harness_id`  
3. Per-role `model_id` + `prompt_id` (and adapter if any)  
4. `n` seeds and aggregation  
5. Organized **and** verbatim search numbers when organization is discussed (P3)  
6. For improvement claims: baseline run_id, exposure schedule, teacher privilege labels (P9/P11/P14/P15)

Violations are corrected by issue → amend catalog or retract row.

---

## 10. Security and Safety Notes

- Synthetic fixtures only in named suites; no real PII (DD-02).  
- Do not publish API keys; tunnel/auth designs are out of band (future serving doc).  
- Slim packs should not include secrets from `meta/environment.json` beyond hardware class.  
- Teacher `informed` mode scorecards in teaching artifacts may be public; gold files remain in suite (already public by design).

---

## 11. Governance (lightweight)

| Role | Responsibility |
|---|---|
| Maintainers | Approve suite MAJOR bumps; promote check families; cut releases |
| Contributors | PRs for fixtures, graders, docs, runs |
| Review bar | CI green + design-doc compatibility for protocol changes |

Protocol changes (DD-01…05 normative rules) require a design-doc PR **before** or **with** code PR.

---

## 12. Collaboration Affordance Checklist (acceptance for “open enough”)

v1 collaboration surface is accepted when:

1. Cold contributor can add a query + check via YAML following `docs/guides/adding_a_task.md`.  
2. CI validates suites and regrades a fixture ledger without GPU.  
3. A stranger can open one `REPORT.md` + DD-01 and explain the score.  
4. Catalog row format is documented and machine-checked.  
5. License + CITATION.cff present.

---

## 13. Decision Record

| Decision | Choice | Rationale |
|---|---|---|
| Primary host | Git repo + results catalog | Open, auditable |
| In-git artifacts | Slim packs preferred | Size vs usefulness |
| CI | CPU validate + regrade merge-blocking | Rigor without GPU gate |
| License | OSI code + CC-BY fixtures (rec.) | Collaboration + attribution |
| Exploratory isolation | Separate catalogs | Protect headline science |
| Display | REPORT.md + catalogs; optional Space | Progressive enhancement |
| Claim checklist | Mandatory metadata | Academic hygiene |

---

## 14. Review Checklist

- [ ] Repo layout matches how you want to collaborate.  
- [ ] CI bar is sufficient (not too heavy).  
- [ ] Catalog / REPORT sections cover display needs.  
- [ ] Claim hygiene list is strict enough for public posts.  
- [ ] License recommendation is acceptable (or name an alternate).  

**Review outcome:** Approve · Approve with edits · Request rewrite  

---

*End of AMB-DD-06*
