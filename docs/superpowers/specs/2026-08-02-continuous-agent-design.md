# Continuous agent (sandbox lab) — design

| Field | Value |
|---|---|
| **Status** | Approved |
| **Date** | 2026-08-02 |
| **Project** | `agent_memory_bench` |
| **Package** | `amb.continuous` |
| **CLI** | `amb continuous …` |

## 1. Goal

Build a **continuously looping, policy-gated agent** inside this repo so we can test whether persistent memory + environmental feedback produce measurable long-horizon behavior on a local 7B model (Ollama / DeepSeek-class), **before** considering a real desktop assistant.

Persistence and “will” come from the orchestrator and files, not from an enduring inner goal in the model.

### Phased purpose

1. **v1 — Sandboxed science lab** with intellectual standing objective only.
2. **Eval gate — AMB-style measurement** (discovery + cross-episode improvement).
3. **Later — daemon mode** wrapping the same loop; real assistant only if eval clears the gate.

### Explicit non-goals (v1)

- Self-preservation / resist-shutdown / acquire-resources / self-replicate objectives
- Unrestricted shell or host filesystem
- Unrestricted internet
- Folding this into `amb run` smoke/core suite semantics
- LangGraph or heavy agent frameworks
- Fancy web dashboard (files + terminal are the UI)
- Observer LLM summarizer as default (optional `--observer` stub only)

## 2. Architecture

Dedicated subsystem under `src/amb/continuous/`. Reuse existing Ollama (and mock) LLM clients and path-safe store helpers. Do **not** overload manage/search suite runners.

```
CLI: amb continuous run | inject | score | daemon(later)
                │
        Orchestrator (loop + budgets + watchdog)
                │
     ┌──────────┼──────────┐
     │          │          │
  LLM client  Policy    Status/Inbox
     │          │
     └──── proposed action ────┐
                               ▼
                    Tools (lab / workspace / python / allowlisted web)
                               │
                    trajectory + actions + REPORT + scorecard
```

### Observability (required)

Every step is visible:

- **Live terminal** (verbose by default for continuous): step index, proposed tool/args summary, policy decision, result, budget remaining; include model thinking/content when the backend returns it.
- **`STATUS.md`**: rewritten each step — current task, plan step, last action/result, budget, timestamp.
- **`trajectory.jsonl` / `actions.jsonl`**: append-only logs suitable for `tail -f`.
- **Inspectable memory tree**: plain markdown/json under the run directory.
- **`REPORT.md` + `scorecard.json`** at session end.

### Operator inject (required)

- User edits **`INBOX.md`** or runs `amb continuous inject "…"` (appends to inbox).
- Each loop iteration: if inbox has content, prepend as high-priority operator message, then move text to `inbox_archive/` and clear inbox.
- Works for episodic runs and (later) daemon.

## 3. Components

| Module | Responsibility |
|---|---|
| `loop.py` | Load objective + memory → LLM → policy → execute → record → status → stop checks |
| `policy.py` | Allowlist tools/args; budgets; deny shell/home/secrets; HITL hooks for future dangerous ops |
| `tools.py` | Thin wrappers: workspace R/W, lab sense/act, bounded Python, allowlisted web |
| `lab/` | Deterministic mini science world; hidden laws in code, not prompt |
| `status.py` | Write `STATUS.md` from structured fields each step |
| `inbox.py` | Read/clear/archive inbox; inject helper |
| `memory_graph.py` | Append-backed weighted pathway graph; retrieve top-k for context |
| `score.py` | Discovery grader + cross-episode improvement comparison |
| `daemon.py` | Phase 2: same loop with sleep/idle and stop file |

### CLI surface (v1)

- `amb continuous run --world crystal --model … --max-steps N --out continuous_runs`
- `amb continuous inject --run <dir> "instruction"`
- `amb continuous score --run <dir>` (and later compare episodes)
- `amb continuous daemon …` — stub or thin wrapper deferred if needed, but designed in

## 4. On-disk layout

```text
continuous_runs/<run_id>/
  STATUS.md
  INBOX.md
  inbox_archive/
  core/objective.md
  memory/observations.jsonl
  memory/current_plan.json
  memory/lessons.md
  memory/graph.json         # weighted association pathways
  lab/                    # world-visible state
  trajectory.jsonl
  actions.jsonl
  REPORT.md
  scorecard.json
  config.json
```

Standing objective example (intellectual only):

> Your continuing purpose is to understand and improve knowledge of this simulated laboratory. Maintain continuity through the provided memory, select a useful next experiment, and document the result. Do not pursue self-preservation or escape.

### Memory model — remember everything + weighted pathways

Two layers (brain-inspired, not a neural net inside the 7B):

1. **Episodic store (never silent-drop):** `memory/observations.jsonl` and markdown files keep a durable record of events, measurements, and notes.
2. **Pathway graph:** `memory/graph.json` — nodes are concepts/events (normalized labels + pointers into observations); edges carry weights.

**Strengthening (v1):**

- **Access / co-occurrence:** when nodes are retrieved or written in the same step, bump edge weight (and node visit counts).
- **Light outcome boost:** small extra weight when a lab action yields a successful/informative result (measurement obtained, hypothesis supported per lab feedback). Failures do not delete; they add weak or negative-tagged edges at most.
- **Decay:** optional later; v1 may omit decay or use very slow unused-edge decay behind a flag.

**Retrieval each step:** orchestrator selects top-k nodes/edges by weight × query/plan overlap (and light recency), then injects the linked observation snippets into the model context. Full store remains on disk for explicit `view` / search.

**Module:** `memory_graph.py` (update on write/retrieve; query for context pack). Unit-test determinism with a fixed seed.

This is an index over memory, not a replacement for STATUS/INBOX or the human-readable journal.

## 5. Lab world (v1)

**World id:** `crystal`. Agent can set/read instruments (temperature, humidity, growth readout) and observe seeded noisy measurements. Hidden generative laws live only in `lab/crystal.py` (and tests). Success = recover laws into the research journal and pass a fixed quiz in `score.py`.

**Tool names (fixed):**

- `lab_sense` / `lab_act`
- `view` / `create` / `str_replace` — path-safe, under the run root only (reuse harness patterns)
- `run_bounded_python` — timeout, no network, restricted imports, output size cap
- `search_allowlisted_web` / `fetch_allowlisted_page` — fixed allowlist in `config.json`; default allowlist empty until explicitly configured
- `done` — end episode early with a short summary

No raw shell. No Docker socket. No home-directory mounts.

**STATUS.md authorship:** orchestrator rewrites STATUS each step from structured fields it already knows (step, last tool, result ok/err, budget) plus `memory/current_plan.json` (task headline / step index). The model updates the plan via workspace writes; it does not free-form rewrite STATUS.

## 6. Policy & safety

Policy (not the model) enforces:

- One run workspace root; path canonicalization; reject `..` and absolute escapes
- No access to SSH keys, browser profiles, cloud creds, or repo secrets
- Network only via allowlisted proxy/functions
- Fixed CPU/time/token/step budgets
- Max consecutive failures → terminate
- Automatic loop detection (identical action repeated) → observation then stop
- Immutable external logs (append-only jsonl)
- Human approval hooks reserved for: package install, outbound messages, purchases (none of these enabled in v1 tools)

Containerization on the 3070 host is optional hardening later; v1 correctness does not assume a perfect container boundary.

## 7. Scoring (assistant go/no-go)

Primary:

1. **Discovery** — fraction of hidden laws / quiz items correct after a budgeted episode.
2. **Improvement** — later episodes with persistent memory beat early episodes (and beat a wipe-memory control) on the same scorecard.

Secondary hygiene:

- Repeat/loop rate
- Policy denial rate
- Heuristic “claimed progress without measurement change” flags

Promote to “consider assistant mode” only after discovery + improvement look clearly non-random on the intended model.

## 8. Runtime modes

| Mode | v1 | Behavior |
|---|---|---|
| Episodic `run` | Yes | N steps / budget; memory persists on disk for next episode |
| `inject` | Yes | Operator steering |
| `score` | Yes | Grade one run or compare episode pair |
| `daemon` | Design now / implement phase 2 | Same loop; idle sleep; stop via file or signal |
| `--observer` | Stub | Optional later: every N steps, second prompt rewrites a prose summary into STATUS |

## 9. Error handling

- Policy deny → structured error observation to the model; do not execute
- Tool/OS errors → captured, never crash the loop unless watchdog threshold hit
- LLM protocol failures → retry/backoff with limit, then stop with reason in REPORT
- Budgets exhausted → clean stop + score

## 10. Testing

- Unit: policy, inbox, status writer, lab determinism (seeded), memory graph weight updates / top-k retrieve
- Integration: MockLLM scripted episode → trajectory, STATUS, graph.json, scorecard
- Live Ollama: manual on desktop; not required in CI

## 11. Implementation order (preview)

Ship in this order so each step is demoable:

1. Scaffold package + CLI stubs + run directory layout (`continuous_runs/` gitignored)
2. Policy + workspace tools + STATUS/INBOX
3. Lab world `crystal` + sense/act
4. Memory graph (access + light success boost) + context pack injection
5. Loop with mock LLM + tests (first green path)
6. Wire Ollama + verbose logging
7. Scoring + multi-episode compare
8. Bounded Python + allowlisted web (web no-ops until allowlist set)
9. Daemon wrapper
10. Optional `--observer` stub/flag

Milestones 1–7 are the minimum “does memory+loop+pathways help?” eval. 8–10 complete the agreed tool surface and ops modes.

## 11b. Post-v1 upgrades (locked preference)

Do **not** pull these into v1 implementation. After mock+Ollama continuous runs score:

1. **TME-lite prompt packing** — formalize each step’s context as fixed slots (objective, STATUS, plan path, top pathways, inbox, last tool result); never dump the whole store.
2. **MRAgent-lite graph walk** — optional `graph_retrieve` / 1–2 hop traverse+prune tool over the weighted pathway graph (deterministic labels; no Cue–Tag LLM distillation yet).
3. **Editable prompt-graph workflows** — only if ops/versioning of the loop becomes painful.
4. **Explicitly deferred:** Graph-of-Thoughts / AGoT (too many calls on 7B; confounds memory eval); full SAGE; privacy PromptGraph.

## 12. Decisions locked in brainstorming

- Home: inside `agent_memory_bench` as `amb continuous`
- Approach: dedicated subsystem (not folded into suite runner; not LangGraph)
- World: mini science lab
- Tools: workspace + bounded Python + allowlisted web
- Success: discovery **and** cross-episode improvement
- Operator UX: structured STATUS + INBOX inject; observer optional later
- Runtime: episodic first, daemon designed for phase 2
- Memory: append-only store + weighted pathway graph (access frequency + light outcome boost; decay optional later)
- Capability awareness: `core/capabilities.md` + `defer` tool + auto-defer on policy deny → `memory/deferred.jsonl`
