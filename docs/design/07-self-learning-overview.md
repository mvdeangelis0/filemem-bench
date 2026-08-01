# Agent Memory Bench — Design Document 07  
## Multi-Episode and Self-Learning Extensions (Overview)

| Field | Value |
|---|---|
| **Status** | Draft for review |
| **Doc ID** | AMB-DD-07 |
| **Version** | 0.2.0 |
| **Date** | 2026-08-01 |
| **Changelog** | 0.2.0 — Exposure-matched baseline (P14); no-feedback held-out eval (§8.4); per-role model/prompt IDs |
| **Project** | `agent_memory_bench` |
| **Audience** | Contributors designing self-improvement experiments; paper readers evaluating claims |
| **Depends on** | AMB-DD-01 (Approved); AMB-DD-02 (fixtures; draft); AMB-DD-04/05 (ledger & scoring; forthcoming) |
| **Companion docs** | AMB-DD-07a (Context arm); AMB-DD-07b (Tuning arm) |
| **Does not replace** | v1 static protocol (`smoke` / `core`) |

---

## 0. Abstract

v1 of `agent_memory_bench` measures **static** filesystem memory competence: incremental management and grounded search under a frozen policy, with deterministic scorecards and an organized-vs-verbatim contrast (AMB-DD-01).

This document defines the **self-learning extension layer**: how agents may improve across episodes via (1) **context** mechanisms (teacher-written skills and policy notes in the filesystem) and/or (2) **model tuning** (a staged ladder SFT → DPO → RL on role-specific adapters), without invalidating the v1 protocol.

Self-learning is a **separate experimental axis**. Headline v1 tables remain exclusive of self-learning. Every improvement claim obeys **P9** (AMB-DD-01): relative gain against a **frozen, exposure-matched** baseline on the same evaluation streams and queries, with **no-feedback held-out** evaluation worlds for transfer headlines. Context and tuning are first reported as **mutually exclusive arms**; stacked cells (`context + adapter`) are reserved for a later factorial grid.

Detailed contracts for the context arm and the tuning arm live in AMB-DD-07a and AMB-DD-07b respectively. This overview is normative for claim language, arm definitions, episode protocols, and sequencing relative to v1.

---

## 1. Motivation

### 1.1 From static competence to improvement

A strong static score answers: *Can this model manage and search a filesystem memory under fixed instructions?*  
It does not answer: *Can the system get better from its own experience?*

That second question is central to long-horizon agents. Deployed systems already accumulate notes and skills; research systems increasingly propose trajectory distillation, preference optimization, and reinforcement learning on tool traces. Without a shared protocol, “self-improving agent” claims are incomparable and often unreproducible.

### 1.2 Two families of improvement (both in scope)

| Family | What changes | Weights | Inspectability |
|---|---|---|---|
| **Context / memory** | Skills, policy notes, optionally retrieved lessons in the store | Frozen | High (markdown diffs) |
| **Model tuning** | LoRA/QLoRA (or equivalent) adapters | Updated | Medium (adapter IDs + training digests) |

Attacking only one family would leave an obvious confound: gains might be “just better prompts in files” or “just fine-tuning,” with no contrast. This bench treats both as first-class, under identical evaluation episodes where possible.

### 1.3 Relationship to Zhou et al. (2026)

The filesystem memory paper separates management, search, and (in the skill setting) execution, and studies whether organization pays. Self-learning here **extends** that setting: skills and policy notes become *outputs of a teacher role across episodes*, and optionally *training targets* for adapters—while preserving inspectable stores, tool-mediated access, and deterministic grading.

---

## 2. Non-Goals (for this extension layer)

The following remain out of scope unless a future doc explicitly adds them:

- Claiming self-learning results from `smoke`/`core` single-episode static runs alone.
- Unsupervised open-world continual learning without fixed suites.
- Updating teacher weights jointly with student weights in an undifferentiated loop (must be labeled if ever tried).
- Proprietary eval hosts as the source of truth (DD-01 P1 still holds).
- Replacing deterministic scorecards with LLM-judge-only rewards for headline metrics.

---

## 3. Normative Principles (inherited + extension-specific)

### 3.1 Inherited from AMB-DD-01

- **P1** Artifacts are the source of truth.  
- **P2** Separate construction (manage) from consumption (search).  
- **P3** Organized vs verbatim contrast retained on evaluation episodes.  
- **P4** Determinism first for pass/fail.  
- **P5** Diagnostics do not gate vanity success.  
- **P9** Improvement claims require a frozen, **exposure-matched** baseline; relative improvement is primary; transfer eval worlds are no-feedback held-out.

### 3.2 Extension principles

**P10 — Role isolation for teaching.**  
Only the **teacher** role may write under designated `/skills` and `/policy` trees. Management and search may read those trees; they must not mutate them during graded episodes.

**P11 — Privilege disclosure.**  
Any teacher that sees scorecards, gold facts, or a stronger model than the student must be labeled in the run config (`teacher_mode`, `teacher_model_id`, `teacher_prompt_id`). Undisclosed privileged feedback invalidates a self-learning claim.

**P12 — Arm exclusivity for headline tables.**  
Primary self-learning tables report **exclusive** arms (baseline | context | tune). Stacked arms are secondary analyses with explicit cell labels.

**P13 — Same graders, new schedules.**  
Self-learning episodes reuse v1 check families and normalization (DD-05), including deterministic fact-matching and evidence-based citations (DD-02). What changes is *when* teaching/tuning occurs and *what* is allowed to persist across episode boundaries.

**P14 — Exposure-matched baseline.**  
When comparing arm \(L\) (context or tune) to `baseline`, both arms must process the **same ordered blocks** with the same chunk sets and the same evaluation queries. The baseline disables teaching and adapter updates but does **not** skip blocks. Wall-clock may differ; **information exposure** (tokens of stream + queries scored) must match. “Baseline saw only Block N” while the learner saw Blocks 1…N is a protocol violation.

**P15 — No-feedback held-out evaluation.**  
For protocol `transfer` (and for any block designated `eval_held_out: true`), the evaluation world MUST NOT contribute teacher inputs, preference pairs, or RL rewards **before** that world’s scorecard is finalized and sealed in the ledger. Post-hoc analysis of eval trajectories is allowed for debugging; using them to update skills, policy, or weights before reporting the eval score is forbidden for that claim.

---

## 4. Experimental Arms

### 4.1 Core arms (headline)

| Arm ID | Context teacher | Student weights | Intent |
|---|---|---|---|
| `baseline` | Off | Base (no adapter) | Exposure-matched frozen reference (P14) |
| `context` | On (writes skills/policy) | Base | Context-only self-teach |
| `tune` | Off | Adapter on (see §6) | Weight updates only |

All arms share: same suite definitions for evaluation blocks, same harness default, same scorecard families, organized + verbatim shapes on eval search, and **per-role** `model_id` / `prompt_id` pins (AMB-DD-01 §3.1).

**Baseline operational definition.** On a schedule with blocks \(1..N\) where teaching/tuning occurs after blocks in \(T \subset \{1..N-1\}\) and evaluation is on block \(E\):

- `context` / `tune`: run blocks in order; apply teach/train only on allowed train blocks; score \(E\).  
- `baseline`: run the **same** blocks in order with the same student `model_id`/`prompt_id`; skip teach/train; score \(E\).  

Baseline may still *write* ordinary declarative memory during manage steps; it simply receives no teacher artifacts and loads no adapters.

### 4.2 Reserved factorial cells (secondary)

| Cell ID | Context | Tune | When allowed |
|---|---|---|---|
| `context+tune` | On | On | After exclusive-arm tables exist |
| `context+tune_sft` / `_dpo` / `_rl` | On | Stage-specific | Ablations |

### 4.3 Implementation sequencing (not claim sequencing)

1. Ship and stabilize v1 static bench (`smoke`/`core`).  
2. Implement **`context`** arm end-to-end (first self-learning implementation).  
3. Implement **`tune`** ladder starting at SFT on **management** adapter.  
4. Add search adapter; then DPO; then RL.  
5. Optionally fill factorial cells.

Claims may only cite arms that were actually run under versioned configs.

---

## 5. Roles in the Extended System

```text
┌─────────────┐     chunks      ┌──────────────┐
│  Environment │ ──────────────► │  Management  │ ── writes declarative memory
└─────────────┘                 └──────┬───────┘
                                       │ store M
┌─────────────┐     queries     ┌──────▼───────┐
│   Evaluator  │ ──────────────► │    Search    │ ── answers + citations
└─────────────┘                 └──────────────┘
        │ scorecard
        ▼
┌─────────────┐   trajectories  ┌──────────────┐
│   Teacher    │ ◄───────────── │  Run ledger  │
│ (between     │                └──────────────┘
│  episodes)   │ ── writes /skills and /policy only
└─────────────┘
        │
        ▼  (tune arm only, offline)
┌─────────────┐
│  Trainer     │ ── produces versioned adapters from ledger data
└─────────────┘
```

| Role | Mutates declarative memory | Mutates `/skills`,`/policy` | Mutates weights |
|---|---|---|---|
| Management | Yes | No | No |
| Search | No (graded) | No | No |
| Teacher | No | Yes | No |
| Trainer | No | No | Yes (offline) |
| Verbatim builder | Builds dump only | No | No |

Teacher and trainer details: DD-07a and DD-07b.

---

## 6. Tuning Ladder (summary; normative outline)

Full specification: AMB-DD-07b.

| Stage | Method | Signal | First target role | Then |
|---|---|---|---|---|
| T1 | SFT | Successful (or high-scoring) trajectories | `manage_lora` | `search_lora` |
| T2 | DPO/KTO | Chosen/rejected pairs from scorecard | per-role adapters | — |
| T3 | RL (e.g. GRPO-class) | Scalar scorecard reward | after T1/T2 plateau | — |

**Order of role adapters:** management first (A), then separate manage/search adapters (D).  
**No shared single adapter** required for headline science; a shared adapter may appear only as an explicit ablation.

---

## 7. Teacher Modes (summary; normative outline)

Full specification: AMB-DD-07a.

### 7.1 Feedback privilege

| Mode | Teacher observes | Use |
|---|---|---|
| `blind` | Trajectories + stores only | Stricter “self-discovery” |
| `informed` | Trajectories + scorecard/diagnostics | Default for practical runs |

Gold facts for failed checks (`informed_gold`) are **not** default; if introduced later, they require a new mode id and privilege disclosure (P11).

### 7.2 Teacher identity

| Mode | Teacher model | Student model | Claim label |
|---|---|---|---|
| `self_teacher` | Same open weights as student (role prompt differs) | Under test | Self-teaching |
| `distill_teacher` | Stronger/other open model | Under test | Distillation / privileged teacher |

Both are in-design; results must never mix labels.

### 7.3 Context artifacts

Teacher may write:

- **Skills** — procedural guidance (how to integrate updates, how to structure people/projects, …).  
- **Policy notes** — declarative rules the management agent must read (e.g. update precedence, protected paths).

Both live in the filesystem memory tree under reserved prefixes (paths fixed in DD-07a).

---

## 8. Episode Protocols

Self-learning is meaningless without an explicit schedule. Two protocols are normative.

### 8.1 Protocol `continue` (in-world improvement)

```text
Block 1: manage stream X₁ → search Q₁ → scorecard S₁
         → teacher (context arm) and/or collect train data (tune arm)
Block 2: manage stream X₂ (continuation of same world) → search Q₂ → S₂
         → …
Block N: …
```

**Primary metric:** relative lift \(S_k - S_1\) (or vs baseline arm’s \(S_k\)) on later blocks, under P9.

**Risk:** memorizing world-specific facts rather than strategies. Mitigate with held-out queries within the same world and diagnostics that separate fact regurgitation from update skill.

### 8.2 Protocol `transfer` (cross-world improvement)

```text
Train world A: one or more blocks + teach/tune
Eval world B: fresh store; student may read transferred /skills+/policy
              and/or load adapters trained on A; then manage+search on B
              (no teacher feedback from B; no train updates from B — §8.4)
```

**Primary metric:** relative lift on world B vs **exposure-matched** `baseline` (same A schedule without teach/tune, then same B eval), same B suite version.

**Requirement:** world B must not be a textual paraphrase of A; different entities, overlapping *phenomena* (updates, multi-hop, meetings). Fixture authorship rules in DD-02 apply per world; `world_id` must differ.

### 8.3 Block contents

A **block** is a versioned slice: contiguous chunks + query set + check-set pin.  
`continue` blocks within one world SHOULD be chronological continuations of one stream.  
Static `smoke`/`core` remain single-block baselines and may serve as Block 1 material when version-compatible.

### 8.4 No-feedback held-out evaluation worlds

A world or block marked for headline evaluation under self-learning MUST satisfy:

1. **No teacher call** conditioned on that world’s trajectories, stores, or scorecards until the eval scorecard is sealed.  
2. **No dataset export** from that world into SFT/DPO/RL training for the adapter version under test.  
3. **No skill/policy mutation** triggered by that world before sealing.  
4. Config flags: `eval_world_id`, `eval_held_out: true`, and a sealed `scorecard_seal_hash` in the ledger.  
5. Optional post-seal analysis (debugging, paper figures) is allowed and must be timestamped after the seal.

Violations invalidate transfer / held-out claims. `continue` protocols may use within-world later blocks as eval only if those blocks are flagged `eval_held_out: true` and obey (1)–(3) relative to teach/train triggers.

---

## 9. Metrics and Claim Language

### 9.1 What to report

For each arm × protocol × suite-version × model:

| Quantity | Definition |
|---|---|
| Absolute scorecard | Pass rate (and per-family rates) on the **evaluation** block |
| Δ vs baseline | Evaluation score(arm) − score(baseline) under matched seeds/config |
| Δ vs self Block-1 | For `continue` only; optional secondary |
| Cost | Tokens, steps, wall time, VRAM; training steps for tune |
| Artifact digests | Suite digest, check_set_id, adapter_id, skills/policy tree hash |

### 9.2 Allowed claim templates

**Allowed:**

> Under protocol `transfer`, arm `context` (`informed` + `self_teacher`) improves manage update_precedence pass rate by +X pp vs `baseline` on world B suite `core_transfer_v1`, n=N seeds.

**Disallowed:**

- Citing absolute scores alone as “self-improved.”  
- Mixing `distill_teacher` results into a “self-teaching” headline.  
- Comparing tune-SFT to baseline that used different suite versions.  
- Using diagnostic metrics as the primary improvement claim.  
- Baseline that skipped train blocks the learner ran (**exposure mismatch**).  
- Teacher or trainer updates from a held-out eval world before seal (**feedback leakage**).  
- Runs missing per-role `model_id` / `prompt_id`.

### 9.3 Statistical reporting (minimum)

For any published Δ: report \(n\) seeds/repeats, mean, and spread (stddev or bootstrap CI). Single-run deltas may appear in exploratory notes only.

---

## 10. Ledger Extensions (preview; locked in DD-04 amendment)

Self-learning runs extend the v1 ledger with:

```text
run/
  config.json                 # arm_id, protocol, per-role model_id/prompt_id,
                              # teacher_*, adapter_*, eval_held_out, exposure_schedule
  episodes/
    block_01/...
    block_02/...
  teaching/                   # context arm
    teacher_mode.json
    skills_snapshot/          # post-teach tree
    policy_snapshot/
    teacher_trajectory.jsonl
  training/                   # tune arm
    stage: sft|dpo|rl
    dataset_digest.json       # must not include sealed eval world ids
    adapter_id
    train_metrics.json
  scorecard.json              # eval block(s)
  scorecard_seal.json         # hash + timestamp for held-out eval
  REPORT.md
```

Re-grade of evaluation blocks remains model-free for deterministic fields. Reproducing a tune arm requires adapter weights (or a public URI) plus config.

---

## 11. Threats to Validity

| Threat | Why it matters | Mitigation |
|---|---|---|
| Privilege laundering | Strong teacher or gold leakage looks like self-improvement | P11 labels; separate tables |
| World memorization | `continue` gains are fact stuffing | Prefer `transfer` for headline self-learn claims |
| Exposure mismatch | Baseline practiced less than learner | P14; identical block schedules |
| Eval feedback leakage | Held-out world trains the system | P15; seal + dataset audits |
| Reward hacking | Tune optimizes grader quirks | Hold out check variants; human spot-check stores |
| Non-exclusive stacking | Context+tune credited as “context” | P12; cell IDs |
| Adapter drift | Unversioned LoRAs | `adapter_id` + weight digest mandatory |
| Confounded harness / prompt swaps | Attribution breaks | Per-role prompt_id pins; freeze harness |
| Metadata side-channels | Gold leakage via chunk fields | DD-02 §5.4 whitelist |

---

## 12. Decision Record (frozen unless revised)

| Decision | Choice | Rationale |
|---|---|---|
| Track structure | Parallel to v1; not inside smoke/core | Keep static baseline clean |
| Science grid | Exclusive arms first; factorial later | Attribution |
| First implementation | Context arm | No training infra gate |
| Context artifacts | Skills + policy notes | Procedures + rules |
| Teacher role | Separate writer for `/skills`,`/policy` | P10 |
| Teacher feedback | `blind` + `informed` (default informed) | Science + pragmatism |
| Teacher identity | `self_teacher` + `distill_teacher` | Honest labeling |
| Episodes | `continue` + `transfer` | Easy runs + publishable transfer |
| Baseline | Exposure-matched (P14) | Fair Δ |
| Eval worlds | No-feedback held-out (P15) | Honest transfer |
| Role identity | Per-role model_id + prompt_id | Attribution |
| Tuning ladder | SFT → DPO → RL | Staged rigor on 3070 |
| Adapter order | Manage SFT first → separate manage/search | Fast win + clean ablations |
| Doc split | DD-07 / 07a / 07b | Reviewable depth |

---

## 13. Document Map (self-learning cluster)

| Doc | Status | Contents |
|---|---|---|
| **AMB-DD-07** | This doc (draft v0.2.0) | Arms, protocols, claims, sequencing, P10–P15 |
| **AMB-DD-07a** | Forthcoming | Teacher contract, FS layout for skills/policy, prompts boundary, teach triggers |
| **AMB-DD-07b** | Forthcoming | Dataset build from ledgers, SFT/DPO/RL configs, adapter registry, 3070 constraints |
| AMB-DD-04/05 | Forthcoming | Ledger fields + scorecard reuse amendments |

---

## 14. Acceptance Criteria for “Self-learning design overview”

This overview is accepted when reviewers agree that:

1. Arms and P9–P15 are unambiguous.  
2. `continue` vs `transfer` metrics are clear.  
3. Exposure-matched baseline and no-feedback held-out eval cannot be silently skipped.  
4. Privilege modes cannot be silently mixed.  
5. Tuning ladder and adapter order match the intended research program.  
6. v1 static suites remain untouched as the frozen baseline substrate.  
7. Per-role model/prompt IDs are mandatory in configs.

Implementation of teaching/training code is **not** required for acceptance of this overview.

---

## 15. Review Checklist

- [ ] Exclusive arms + later factorial matches your publishing plan.  
- [ ] Exposure-matched baseline (P14) is the right fairness rule.  
- [ ] No-feedback held-out eval (§8.4 / P15) is strict enough.  
- [ ] Context-first implementation order is acceptable.  
- [ ] `continue` + `transfer` both belong in v1 of the *extension* (even if transfer fixtures come later).  
- [ ] Claim templates feel strict enough for academic use.  
- [ ] Split into 07 / 07a / 07b is the right granularity.  

**Review outcome:** Approve · Approve with edits · Request rewrite  

---

*End of AMB-DD-07*
