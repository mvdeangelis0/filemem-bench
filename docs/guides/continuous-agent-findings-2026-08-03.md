# Continuous agent — first desktop findings (2026-08-03)

First live Ollama runs on the Windows RTX 3070 box (`deepseek-r1:7b-qwen-distill-q4_K_M`, `crystal` world, `max_steps=50`). Artifacts live under `continuous_runs/`.

**Bottom line:** the harness works end-to-end (sense/act, defer, policy, memory graph, STATUS/REPORT). The 7B model does **not** yet do scientific exploration of the hidden crystal laws. It mostly burns steps on protocol noise, fake `lab_act` knobs, and path-schema confusion. One harness bug aborted an early run on the first `create` (fixed in `4aef192`).

## Runs at a glance

| Run | Model | Steps | Stop | Lab trials / growth | Score\* | Notes |
|-----|--------|------:|------|---------------------|--------:|-------|
| `20260803_180809__crystal` | `deepseek-r1:7b` | 0 | aborted at start | 0 / 0 | 0.0 | Empty episode (never left “starting”) |
| `20260803_180858__crystal` | distill q4_K_M | ~6–7 | **crash** (no REPORT) | 1 / ~0.29 | 0.5 | Died on first `create` |
| `20260803_183032__crystal` | distill q4_K_M | 42 | `protocol_failures` | 24 / ~0.19 | 1.0\* | Longest useful trace |
| `smoke1` | mock | 2 | `max_steps` | — | — | Local mock smoke only |

\*`ambc score` regex checks are weak (see below). Pass ≠ discovered laws.

Default lab setpoints stayed at **T=25°C, H=30%**. Hidden optimum is ~**37°C** and humidity **40–60%**. Growth variance in the long run is almost entirely **noise around a bad setpoint**, not controlled sweeps.

## What worked

- **Ollama + `ambc` loop** on Windows: tool calls execute, STATUS updates, observations/actions/trajectory append, deferred queue + web cursor scaffolding present.
- **Policy + defer:** absolute paths and malformed edits were denied and parked in `memory/deferred.jsonl` instead of escaping the run dir.
- **Budgeted stop:** long run correctly halted after three consecutive protocol failures (step 42), with `REPORT.md`.
- **Crash diagnosis → fix:** first `create` wrote the file then raised `ValueError` because `path.relative_to(run_dir)` mixed an absolute resolved path with a relative `run_dir`. Fixed by resolving `run_dir` in `ToolRuntime`, JSON-serializing structured `create` content, catching tool exceptions, and always writing `REPORT.md` on loop crash (`4aef192`).

## What the agent actually did (long run)

Tool mix in `20260803_183032__crystal` (39 logged actions):

| Tool | Count | Role in practice |
|------|------:|------------------|
| `lab_act` | 24 | “Experiments” with invented keys like `action: test_action_optimized_growth_N` — **never set `temperature` / `humidity`** |
| `lab_sense` | 9 | Read instruments (always same T/H band) |
| `str_replace` | 3 | Tried to “fix” absolute-path errors by editing fictional paths |
| `run_bounded_python` | 1 | Wrong arg shape (`script` / nested `type`) → `empty_code` |
| `view` | 1 | `/path/to/data.json` → policy deny |
| `defer` | 1 | Echoed a prior deny into defer (good instinct, thin payload) |

Plan file stuck at step **1/5** (`Explore instruments`). `memory/lessons.md` stayed empty. No durable hypothesis about temp/humidity bands.

Late-run failure mode: after a path deny, the model **meta-edited the error text** (`str_replace` on placeholder paths / `people/morgan.md` from the error message) instead of using a relative workspace path. Then protocol broke (bad JSON / nested `tool_call` wrappers) → stop.

## Failure modes (ranked)

### 1. Tool-schema / protocol fragility (blocking)

DeepSeek often emits near-miss JSON:

- `{"tool_call": "lab_sense"}` (string, not object)
- `{"tool_call": {"tool": "...", "arguments": ...}}` (extra wrapper)
- `unparseable_json` mid-`create`
- Wrong arg names (`command` / `script` / `input` instead of `code` / `path` / `old_str`)

Harness counts these as failures; three in a row ends the episode. Small models need tighter parse recovery, few-shot tool examples, or constrained decoding.

### 2. Lab API misunderstood (core science fail)

`lab_act` only honors `temperature` and `humidity`. The model invents an `action` string and treats growth changes as if those strings mattered. With T/H fixed at (25, 30), every trial samples noise around a low true growth — looks like “optimization” while learning nothing.

### 3. Path / host confusion

Uses tutorial placeholders (`/path/to/data.json`) and then tries to rewrite policy error copy. Capabilities text mentions `people/morgan.md` as an example; the model treats that as a real target.

### 4. Premature / confused defer

Early run deferred `run_bounded_python` as “incomplete” then stuffed Python into `lab_sense`/`lab_act` `command` fields. Defer works as a safety valve; the model does not yet reliably continue with in-scope alternatives.

### 5. Harness bug (fixed)

`create` after successful write → uncaught `ValueError` → process death, no REPORT, STATUS frozen. Symptom matched run `180858`.

### 6. Scorecard overclaims

`score_run` passes if memory corpus regex-matches rough temp/humidity tokens. The long run scored **2/2** because numbers/words appeared in tool traces and deny messages — **not** because the agent stated or used the hidden law. Treat current scores as smoke checks, not science grades.

## Science outcome (crystal)

| Hidden law | Evidence agent found it? |
|------------|--------------------------|
| Ideal temp ≈ 37°C | No controlled temp sweep; never set temperature |
| Humidity band 40–60% | Never set humidity; stayed at 30% |
| Growth = f(T,H) + noise | Interpreted noise as progress from named “actions” |

**Verdict:** sandbox is measuring **tool-use + continuity**, not yet **discovery**. That is expected for v1 + 7B; the eval gate is not green for “understand the lab.”

## Operator / repo hygiene

- Prefer full Ollama tag (`…q4_K_M`) so runs are comparable.
- Do not commit `.venv/` or `__pycache__` from the Windows machine (already landed once in `ff35258` — clean up when convenient).
- After `4aef192`, `git pull` on desktop before the next `/run`; old crashed runs do not resume.

## Recommended next experiments

1. **Prompt / schema:** few-shot legal `lab_act` (`temperature`, `humidity` only) + reject/repair unknown keys with an informative tool error.
2. **Parse recovery:** accept common wrapper forms (`tool_call` object) before counting a protocol failure.
3. **Forced curriculum via INBOX:** e.g. “Run a temp sweep 20→45 at humidity 50; log a table; update lessons.md.”
4. **Stricter scorecard:** require written claims in `lessons.md` / notes that cite T≈37 and H∈[40,60], plus at least one `lab_act` that sets those fields — not corpus regex alone.
5. **Re-run 50 steps post-fix** and compare tool mix + whether T/H ever move.

## Fixes applied (2026-08-03, post-findings)

Shipped for the next desktop re-run:

- **Protocol unwrap** — nested `{"tool_call": {...}}` and string `{"tool_call": "lab_sense"}` normalize to real tool calls; list-of-dict `arguments` coerced.
- **Strict `lab_act`** — requires numeric `temperature` and/or `humidity`; invented `action` keys fail with `bad_args`. Python accepts `script` alias.
- **Path examples** — continuous policy/capabilities/errors say `memory/notes.md`, not `people/morgan.md`.
- **Honest scorecard** — needs successful in-band `lab_act`s plus a claim in `memory/lessons.md` or `memory/notes.md`. Historical run `20260803_183032__crystal` fails this card (by design).

Operator tip after `git pull`: optional `/inject Run a temperature sweep 20→45 at humidity 50; write findings to memory/lessons.md` then `/run -v`.

## Pointers

- Operator guide: `docs/guides/continuous-agent.md`
- Design: `docs/superpowers/specs/2026-08-02-continuous-agent-design.md`
- Create crash fix: `4aef192`
- Primary trace: `continuous_runs/20260803_183032__crystal/`
