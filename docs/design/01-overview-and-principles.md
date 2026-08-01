# Agent Memory Bench — Design Document 01

## Overview, Problem Statement, and Governing Principles


| Field          | Value                                                                                        |
| -------------- | -------------------------------------------------------------------------------------------- |
| **Status**     | Approved (amended)                                                                           |
| **Doc ID**     | AMB-DD-01                                                                                    |
| **Version**    | 0.2.0                                                                                        |
| **Date**       | 2026-08-01                                                                                   |
| **Approved**   | 2026-08-01 (v0.1.1); amended 2026-08-01 (v0.2.0)                                           |
| **Changelog**  | 0.2.0 — Role-specific model/prompt IDs; fact-match & citation rigor pointers; P9 exposure match; agent metadata whitelist pointer. 0.1.1 — Self-teaching reserve (P9, DD-07). |
| **Project**    | `agent_memory_bench`                                                                         |
| **Audience**   | Contributors, reviewers, and future paper readers                                            |
| **Depends on** | Decision record in this doc, §8                                                              |
| **Supersedes** | —                                                                                            |
| **Next doc**   | AMB-DD-02 — Suite Contents & Fixture Protocol                                                |


---

## 0. Abstract

`agent_memory_bench` is an open evaluation harness for **filesystem-based memory** in LLM agents. It treats memory not as an opaque retrieval index, but as an inspectable directory of markdown files that agents read, write, and reorganize through a fixed tool harness.

The bench separates two capabilities that are usually conflated:

1. **Management** — integrate a stream of incoming content into a store and keep that store usable as facts update, conflict, and accumulate.
2. **Search** — answer questions over a fixed store with answers grounded in cited file paths.

Every experiment compares at least two store constructions on the same stream: an **agent-organized** store and a **verbatim dump** baseline. Primary claims are supported by **deterministic graders** over recorded artifacts. Observability UIs are optional and never required to reproduce a result.

This document defines the problem, scope, non-goals, success criteria, and the principles that all later design docs must obey.

---

## 1. Motivation

### 1.1 The deployed default is under-measured

Production coding agents increasingly persist long-horizon context as files: notes, memories, skills, and indexes living on disk behind generic file tools. That default is attractive because it is inspectable, portable, and aligned with tools models already use. It is also largely assumed rather than stress-tested.

The research literature has studied many bespoke memory representations (graphs, fact stores, summary banks, embedding trees). The filesystem form itself—how a store is built, how it evolves, and whether organization repays its cost—has only recently received systematic treatment (Zhou et al., 2026, arXiv:2607.26637).

### 1.2 Why small open-weight agents matter

Most public agent demonstrations use frontier models. That leaves a gap: careful, apples-to-apples measurement of **7B–8B-class** open models on the same agent memory tasks, under the same tools, fixtures, and graders. Local inference (e.g. Ollama on consumer GPUs) makes high-volume trajectory collection economically feasible. The scientific product is not a chat demo, rather it is a **public evidence pack**—configs, trajectories, final stores, scores, and reports that a third party can re-grade offline.

### 1.3 What “rigorous” means here

Rigor in this project is operational:

- Fixed suites with versioned fixtures and gold labels.
- Role separation so management failures are not hidden inside search success (and vice versa).
- Artifact-first runs: grading is a pure function of recorded outputs.
- Deterministic checks carry the pass/fail burden; model judges are secondary and labeled as such.
- Threats to validity are stated up front; diagnostics are not allowed to inflate headline success rates.

### 1.4 Self-teaching as a reserved capability axis

A natural next question after measuring static management quality is whether agents can improve their own memory strategies over time — extracting reusable organization patterns, refining update rules, or turning successful trajectories into skills. This bench is designed so that self-teaching mechanisms can be added as a third role or multi-episode mode without invalidating the v1 protocol.

v1 deliberately does **not** measure self-improvement. It establishes the frozen management + search baseline against which any later self-teaching claim must be compared (see P9).

---

## 2. Problem Statement

We want a reusable answer to the following:

> Under a fixed tool harness and a fixed synthetic personal-knowledge stream, how do open-weight agents compare on (a) integrating and updating a filesystem memory and (b) answering grounded questions over that memory—relative to a zero-curation verbatim baseline—when every step is recorded and re-gradable without access to the original GPU?

Concretely, the bench must make it cheap to run, hard to game, and easy for outsiders to audit.

---

## 3. Design Object

### 3.1 Unit of evaluation

The unit of evaluation is a **configured experiment run**:

```text
(suite_id,
 harness_id,
 shape_set,
 seed,
 code_version,
 roles: {
   manage: { model_id, prompt_id, adapter_id? },
   search: { model_id, prompt_id, adapter_id? },
   teacher?: { model_id, prompt_id }   # self-learning arms only
 }
) → RunLedger → Scorecard + Diagnostics
```

**Role-specific identity (normative).** Management, search, and (when present) teacher each carry their own `model_id` and `prompt_id`. A run that records only a single global `model_id` is non-conformant. Adapters, when used, are also role-scoped (`adapter_id` per role). Prompt bodies are versioned artifacts; `prompt_id` is a content-addressed or semver pin resolved in the ledger (details in AMB-DD-03 / DD-04).

A run always includes:


| Role             | Input                                   | Output                                                    |
| ---------------- | --------------------------------------- | --------------------------------------------------------- |
| Management agent | Instruction (`prompt_id`) + chunk x_t + store M_{t-1} | Store M_t + trajectory                                    |
| Search agent     | Instruction (`prompt_id`) + query q + fixed store M   | Answer a, citation set \Gamma + trajectory                |
| Verbatim builder | Stream x_t                              | Deterministic flat store M^{\mathrm{verbatim}} (no model) |


Search is evaluated independently on both M^{\mathrm{organized}} (management output) and M^{\mathrm{verbatim}}.

**Forward compatibility.** The unit of evaluation may later expand to **multi-episode runs**, in which a teacher or self-refinement step sits between management episodes (for example: manage stream A → refine policy or distill skills → manage stream B → search). That expansion must preserve the v1 ledger fields and the organized-vs-verbatim contrast; it is specified in AMB-DD-07, not in v1 suites.

### 3.2 Memory store (working definition)

A memory store M is a rooted directory of UTF-8 markdown files. Each file has a path, an optional one-line description (frontmatter), and a body. Folders are path prefixes. Agents never touch the store except through the harness.

This matches the minimal contract in Zhou et al. (2026): hierarchy + descriptions + tool-mediated access.

---

## 4. Scope

### 4.1 In scope for v1


| Area               | Commitment                                                                                    |
| ------------------ | --------------------------------------------------------------------------------------------- |
| Roles              | Management and search as separate agents                                                      |
| Domain             | Synthetic personal knowledge base (people, preferences, meetings, projects)                   |
| Shapes             | Agent-organized vs verbatim dump                                                              |
| Harness (default)  | Six memory-tool operations: view, create, str_replace, insert, delete, rename                 |
| Harness (reserved) | Sandboxed shell, same fixtures, later switch                                                  |
| Scale tiers        | `smoke` and `core` (sizes fixed in AMB-DD-02)                                                 |
| Ingestion          | Incremental: M_t = \mathrm{manage}(x_t, M_{t-1}), including for `smoke`                       |
| Scoring            | Pass/fail **scorecard** + non-gating **store-health diagnostics**                             |
| Artifacts          | Self-contained run ledger on disk; offline re-grade                                           |
| Telemetry          | Optional OpenTelemetry export to OSS backends (Langfuse / Phoenix); never required for claims |
| Repo home          | `agent_memory_bench/`                                                                         |


### 4.2 Explicit non-goals for v1

The following are deferred. They are compatible with this design but must not block v1 acceptance:

- Public OpenAI-compatible API, tunnels, or remote serving.
- S3/R2 as primary storage (local ledger first; object storage is a sync target later).
- LangSmith or other proprietary eval hosts in the critical path.
- Paper-scale streams and growth checkpoints (`paper-lite`).
- Full reproduction of LoCoMo / PersonaMem / REALTALK / ALFWorld.
- Taxonomy principles P1–P5 as automated pass/fail gates.
- LLM-as-judge as a primary reported metric.
- Multi-agent social or tool-use domains beyond filesystem memory.
- Self-teaching / self-refinement loops (agents modifying their own management policy or extracting skills across episodes). Reserved for a later suite once the static management + search baseline is solid; see AMB-DD-07.

---

## 5. Governing Principles

These principles are normative. Later docs and code that conflict with them require an explicit decision-record update.

### P1 — Artifacts are the source of truth

A published claim cites a run ledger (or a content-addressed export of one), not a screenshot of a trace UI. If a result cannot be re-scored from files alone, it is not a result.

### P2 — Separate construction from consumption

Management builds stores. Search consumes frozen stores. Mixing them in one agent loop is allowed as a future mode, but v1 measures the split so failures are attributable.

### P3 — Always include a zero-curation baseline

Every search evaluation that reports organized-store quality must also report the same queries against the verbatim dump built from the same stream. Organization claims without this contrast are out of policy.

### P4 — Determinism first, judgment second

Pass/fail checks are programmatic. Required families include: deterministic **fact-matching** against the gold fact table (AMB-DD-02 §6.4; algorithms in DD-05), update precedence, protected-fact survival, answer normalization match, **citation path existence**, and **evidence-based citation support** (cited files must contain declared evidence spans). Subjective quality judges, if used, are reported in a separate channel and cannot change the headline success rate.

### P5 — Diagnostics must not gate vanity metrics

Store-health and organization proxies (file counts, depth, duplication heuristics, label entropy, etc.) are reported as **diagnostics**. They inform analysis; they do not define task success in v1.

### P6 — Open by default, portable by construction

Fixtures, schemas, graders, and ledgers are open. Tracing backends are adapters. Prefer OpenTelemetry GenAI semantic conventions for optional telemetry so contributors are not locked to one vendor.

### P7 — Scale the suite, not the protocol

`smoke` and `core` share the same roles, harness contract, incremental ingestion rule, and grading philosophy. Only fixture volume and query coverage change.

### P8 — Threats to validity are first-class

Known limitations (synthetic domain, grader brittleness, harness sensitivity, model stochasticity) are documented in the scoring and suite docs. Suites should include at least one planted failure that graders must catch.

### P9 — Improvement claims require a frozen, exposure-matched baseline

Any claim that an agent improved its own memory strategy must be measured against the **same agent without the self-teaching / tuning mechanism**, on the same evaluation streams and queries. The baseline arm must be **exposure-matched**: it runs the same number of blocks / the same chunk and query exposure as the learning arm, differing only by the disabled mechanism (no teacher writes, no adapter updates). Relative improvement (learning on − baseline) is the primary reported quantity. Absolute scores alone are insufficient. Evaluation worlds used for headline transfer claims are **no-feedback held-out** (AMB-DD-07 §8.4): no teacher signal and no training updates may be derived from the evaluation world before its scorecard is finalized.

---

## 6. Success Criteria (Acceptance for v1)

v1 is accepted when all of the following hold:

1. **End-to-end smoke:** One local open model completes `smoke` for both shapes and writes a complete run ledger conforming to the schema in AMB-DD-04.
2. **Offline re-grade:** `amb regrade <run_dir>` (or equivalent) reproduces `scorecard.json` bit-for-bit for deterministic fields without loading a model.
3. **Contrast table:** `core` emits a comparison across `{model} × {organized, verbatim}` with management and search metrics separated.
4. **External intelligibility:** A cold reader can explain, from this doc series plus one `REPORT.md`, what was measured and what was not.
5. **Grader bite:** At least one planted regression (e.g. stale preference after an update chunk) fails the scorecard when the store is wrong and passes when the store is right.
6. **No proprietary dependency:** Cloning and re-grading requires no commercial eval SaaS account.

---

## 7. Document Map


| Doc ID        | Title                                                 | Question it answers                                            |
| ------------- | ----------------------------------------------------- | -------------------------------------------------------------- |
| **AMB-DD-01** | Overview & Principles (this doc)                      | Why does this exist and what rules bind it?                    |
| **AMB-DD-02** | Suite Contents & Fixture Protocol                     | What is in `smoke`/`core`, and how are gold labels defined?    |
| **AMB-DD-03** | Agent Contracts & Tool Harness                        | Exact I/O contracts, tools, stop conditions, prompts boundary  |
| **AMB-DD-04** | Run Ledger & Schema                                   | On-disk layout, IDs, versioning, reproducibility fields        |
| **AMB-DD-05** | Scoring: Scorecard & Diagnostics                      | Exact metrics, normalization, pass/fail rules                  |
| **AMB-DD-06** | Collaboration, Display & Release                      | Contrib path, CI, public results layout, licensing             |
| **AMB-DD-07** | Multi-episode & Self-Learning Overview | Arms, protocols, claim language, P9–P15 |
| **AMB-DD-07a** | Context Self-Learning Arm *(forthcoming)* | Teacher, skills/policy FS contract, blind/informed |
| **AMB-DD-07b** | Tuning Self-Learning Arm *(forthcoming)* | SFT→DPO→RL, adapters, datasets from ledgers |


Implementation plans for v1 (DD-01–DD-06) are produced only after that design series is reviewed and accepted. DD-07 is authored after the static baseline exists.

---

## 8. Decision Record (frozen for v1 unless revised)


| Decision         | Choice                                                 | Rationale                                                            |
| ---------------- | ------------------------------------------------------ | -------------------------------------------------------------------- |
| Unit under test  | Split management vs search                             | Attribution; paper-aligned richness                                  |
| Domain           | Synthetic personal KB                                  | Controllable gold labels; contradictions/updates easy to plant       |
| Shapes           | Organized + verbatim                                   | Minimum contrast that supports organization claims                   |
| Default harness  | Memory-tool six ops                                    | Industry-default alignment; shell reserved                           |
| Scale            | `smoke` + `core`                                       | Ship pipeline fast without weakening protocol                        |
| Scoring shape    | Scorecard + diagnostics                                | Honest headline metrics                                              |
| Ingestion        | Incremental always                                     | Evolution and updates are in-scope behaviors                         |
| Repo layout      | Top-level `agent_memory_bench/`                        | Clean public surface                                                 |
| Experiment spine | Artifact ledger (Approach 2)                           | Reproducibility and display without SaaS                             |
| Observability    | Optional OTel → OSS (Langfuse/Phoenix)                 | Open stack; ledger remains source of truth                           |
| Values           | Open source + collaboration + display + academic rigor | Bind product and methodology choices                                 |
| Self-teaching    | Reserved (out of v1); extension via DD-07              | Keep smoke/core tight; require frozen baseline (P9) for later claims |
| Role identity    | Per-role `model_id` + `prompt_id` (+ optional adapter) | Attribution across manage / search / teacher                       |
| Fact grading     | Explicit match contract (DD-02 §6.4)                   | Deterministic, auditable management scores                         |
| Citations        | Exist + evidence-support on scorecard (core required)  | Grounding, not decorative path lists                               |
| Chunk metadata   | Agent-visible whitelist only (DD-02 §5.4)              | No gold side-channels                                              |


---

## 9. Risks and Mitigations


| Risk                                    | Impact                             | Mitigation                                                                 |
| --------------------------------------- | ---------------------------------- | -------------------------------------------------------------------------- |
| Graders overfit to wording              | False negatives on valid answers   | Answer normalization spec in DD-05; multiple acceptable forms where needed |
| Synthetic domain overstates generality  | Overclaiming                       | Scope statements in reports; no LoCoMo-equivalence claims in v1            |
| Harness dominates model effects         | Confounded comparisons             | Freeze default harness; treat harness swaps as a separate axis later       |
| Stochastic runs                         | Unstable tables                    | Record seeds; allow n repeats in runner; report mean ± spread when n>1     |
| Trace UI becomes “the result”           | Non-reproducible science           | P1: ledgers gate claims                                                    |
| Self-teaching conflated with v1 success | Inflated or uninterpretable claims | Keep out of smoke/core; enforce P9 when DD-07 lands                        |
| Baseline under-exposed vs learning arm  | Fake “improvement” from extra practice | Exposure-matched baseline (P9 / DD-07)                                   |
| Eval-world feedback leakage             | Transfer scores contaminated           | No-feedback held-out eval worlds (DD-07 §8.4)                            |
| Gold metadata visible to agents         | Side-channel solves                    | Agent-visible whitelist (DD-02 §5.4)                                     |


---

## 10. References

- Zhou et al. (2026). *Filesystem-Based Memory for LLM Agents: Organization, Evolution, and Sustainability.* arXiv:2607.26637.
- OpenTelemetry GenAI semantic conventions (development/RC status; used here as a **portability target**, not a hard runtime dependency for v1).
- Industry eval practice (trajectory scoring, deterministic checks before judges, artifact replay) as background; this project intentionally keeps graders and ledgers in-repo.

---

## 11. Review Checklist (for the reader)

Please mark each item when reviewing this draft:

- [ ] Problem statement matches what you want measured.
- [ ] Non-goals are acceptable (nothing critical for v1 is missing).
- [ ] Principles P1–P9 (incl. exposure-matched / held-out eval in P9) are constraints you are willing to enforce.
- [ ] Per-role model/prompt IDs are acceptable as mandatory run config.
- [ ] Self-teaching is correctly reserved (signaled, not in v1 suites).
- [ ] Success criteria are specific enough to accept/reject v1.
- [ ] Decision record matches prior conversation choices.
- [ ] Wording is clear enough for an external collaborator.

**Review outcome:** Approve · Approve with edits · Request rewrite  

Comment here or in chat with numbered edits referencing section IDs (e.g. “§4.2: keep S3 as stretch goal but mention sync hooks”).

---

*End of AMB-DD-01*