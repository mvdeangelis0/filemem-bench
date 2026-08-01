# Agent Memory Bench — Design Document 03  
## Agent Contracts and Tool Harness

| Field | Value |
|---|---|
| **Status** | Approved |
| **Doc ID** | AMB-DD-03 |
| **Version** | 0.1.0 |
| **Date** | 2026-08-01 |
| **Approved** | 2026-08-01 |
| **Project** | `agent_memory_bench` |
| **Audience** | Implementers of the agent loop; reviewers of role isolation claims |
| **Depends on** | AMB-DD-01 (Approved v0.2.0); AMB-DD-02 (Draft v0.2.0) |
| **Supersedes** | — |
| **Next doc** | AMB-DD-04 — Run Ledger & Schema |
| **Related** | AMB-DD-07 / 07a (teacher role); this doc covers manage + search + harness defaults |

---

## 0. Abstract

This document specifies the **runtime contracts** for the management and search agents, the default **memory-tool harness**, stop conditions, observation envelopes, and the binding between **role-specific `model_id` / `prompt_id`** and execution. It also freezes how chunk metadata reaches agents (whitelist from AMB-DD-02 §5.4) and what must never appear in prompts.

Teacher and trainer contracts for self-learning are outlined only at the interface level; full teacher semantics live in AMB-DD-07a.

---

## 1. Purpose

Without hard role and harness contracts, score differences are uninterpretable: a “better” model may simply have seen gold tags, used a different tool set, or run under a mutated system prompt. This doc makes those axes explicit and versioned.

---

## 2. Role Identity Record

Every agent invocation is keyed by a **RoleSpec** recorded in the run config and ledger:

```yaml
roles:
  manage:
    model_id: "ollama/deepseek-r1-distill-qwen-7b:q4_K_M"
    prompt_id: "manage.memory_tool.v1"
    adapter_id: null                 # or registry id when tune arm on
    temperature: 0.0                 # default for graded runs
    max_steps: 30
  search:
    model_id: "ollama/deepseek-r1-distill-qwen-7b:q4_K_M"
    prompt_id: "search.memory_tool.v1"
    adapter_id: null
    temperature: 0.0
    max_steps: 20
  teacher:                           # optional; self-learning only
    model_id: "..."
    prompt_id: "teacher.informed.self.v1"
```

**Normative rules:**

1. `model_id` and `prompt_id` are mandatory for every role that runs.  
2. `prompt_id` resolves to an immutable prompt artifact (path + content digest) under `prompts/` (layout in DD-04).  
3. Changing prompt text without bumping `prompt_id` is a protocol violation.  
4. Graded comparisons must pin these IDs in the published table footnote or `config.json` digest.

---

## 3. Shared Agent Loop

Both manage and search use the same loop shape:

```text
state ← initial_observation
for step in 1..max_steps:
    model_out ← LLM(role.prompt, state, tools)
    if model_out is final_answer:
        return model_out
    if model_out is tool_call:
        obs ← harness.execute(tool_call, store_root, role_permissions)
        append (tool_call, obs) to trajectory
        state ← state + obs
    else:
        record protocol_error; abort or re-prompt once (suite policy)
fail with max_steps_exceeded
```

**Trajectory record (per step):** `step`, `timestamp`, `tool_name`, `arguments`, `observation`, `tokens_in`, `tokens_out` (when available). Full schema: DD-04.

---

## 4. Management Agent Contract

### 4.1 Goal

Given instruction \(\iota_{\mathrm{m}}\), chunk \(x_t\) (whitelist fields only), and store \(M_{t-1}\), produce \(M_t\) that integrates \(x_t\) and maintains usable organization. The agent may create, edit, rename, delete, and move files **except** under reserved prefixes (§7).

### 4.2 Inputs (allowed)

| Input | Source |
|---|---|
| System + role prompt | `prompt_id` artifact |
| Chunk envelope | Whitelisted fields only (DD-02 §5.4) |
| Store | Via harness tools under `stores/organized/` (working root) |
| Skills / policy trees | Read-only if present (self-learning); paths in §7 |

### 4.3 Inputs (forbidden)

Gold facts, query gold, check configs, denylisted chunk metadata, scorecards, other roles’ hidden state.

### 4.4 Outputs

| Output | Requirement |
|---|---|
| Mutated store \(M_t\) | Only via harness; no direct filesystem escape |
| Termination | Explicit `done` tool or final message per prompt contract |
| Trajectory | Complete tool trace in ledger |

### 4.5 Stop conditions

Success stop: agent invokes `done` (or emits `FINAL` per prompt) after finishing integration.  
Hard stop: `max_steps`, wall-clock budget, repeated identical tool calls (≥3), or harness permission error storm.

### 4.6 Invariants

- Starts from \(M_{t-1}\) snapshot for chunk \(t\) (no peek at future chunks).  
- Cannot read `suites/*/gold` or `checks`.  
- Cannot write outside store root.  
- Cannot write `/skills` or `/policy` (P10).

---

## 5. Search Agent Contract

### 5.1 Goal

Given instruction \(\iota_{\mathrm{s}}\), query \(q\), and **frozen** store \(M\), return answer \(a\) and citation set \(\Gamma\).

### 5.2 Permissions

| Operation class | Allowed |
|---|---|
| Read / list / search tools | Yes |
| Mutating tools (create, str_replace, insert, delete, rename) | **No** — harness enforces |
| Writing outside store | No |

If the harness cannot structurally disable writes, the prompt forbids them **and** any mutation detected in the store snapshot diff fails the run with `harness_integrity_error` (scorecard void for that query).

### 5.3 Required final payload

Search must terminate with a structured final object (prompt-enforced; validated by runner):

```json
{
  "answer": "coffee",
  "citations": ["people/morgan.md"],
  "confidence": "high"
}
```

Missing `citations` key → automatic fail of `citations_exist` / support checks. Schema frozen in DD-04.

### 5.4 Stop conditions

Analogous to management, typically lower `max_steps` (default 20).

---

## 6. Default Harness: `memory_tool_v1`

### 6.1 Tool set

Aligned with industry memory-tool style ops:

| Tool | Mutates? | Manage | Search |
|---|---|---|---|
| `view` | no | ✓ | ✓ |
| `create` | yes | ✓ | ✗ |
| `str_replace` | yes | ✓ | ✗ |
| `insert` | yes | ✓ | ✗ |
| `delete` | yes | ✓ | ✗ |
| `rename` | yes | ✓ | ✗ |
| `done` | no | ✓ | ✓ |

Optional read-only helpers (same harness version, flagged in config):

| Tool | Notes |
|---|---|
| `grep` | Line-level regex over store; read-only |
| `glob` | Path pattern listing; read-only |

Enabling `grep`/`glob` bumps a harness *feature flag* recorded as `harness_id: memory_tool_v1+grep` (or similar). Comparisons across different harness feature flags are a separate axis.

### 6.2 Path sandbox

- All paths are relative to the role’s store root.  
- Absolute paths, `..` segments, and symlinks escaping the root raise `path_error`.  
- Reserved prefixes (§7) are write-protected for manage/search.

### 6.3 Observation envelope

Successful tool result:

```json
{
  "ok": true,
  "tool": "view",
  "path": "people/morgan.md",
  "content": "...",
  "truncated": false
}
```

Large files may truncate with `truncated: true` and `content_digest`. Truncation policy is pinned in harness config (default: 32 KiB per view).

### 6.4 Reserved harness: `shell_v1`

Sandboxed shell over the store directory is **out of default v1 runs** but reserved (DD-01). Same fixtures; different `harness_id`. Not specified further here until activated.

---

## 7. Reserved Filesystem Prefixes

Within a working memory root:

| Prefix | Manage | Search | Teacher |
|---|---|---|---|
| `/` (declarative memory) | read/write | read | read |
| `/skills/` | read | read | read/write |
| `/policy/` | read | read | read/write |
| `/_amb/` | no | no | no |

`/_amb/` is harness bookkeeping (snapshots, locks); never shown to models.

Verbatim store roots have no skills/policy requirement; teacher artifacts apply to the organized (and eval) student store as specified in DD-07a.

---

## 8. Prompt Artifacts

### 8.1 Layout

```text
prompts/
  manage/
    memory_tool.v1.md
  search/
    memory_tool.v1.md
  teacher/
    informed.self.v1.md
    blind.self.v1.md
    ...
```

Each file begins with YAML frontmatter:

```yaml
---
prompt_id: manage.memory_tool.v1
role: manage
harness: memory_tool_v1
version: 1
---
```

### 8.2 Content rules

- State tool schemas or reference a generated tool card.  
- State reserved prefixes and write restrictions.  
- **Must not** include gold examples from the active suite.  
- May include abstract worked examples on fictional throwaway names not used in `smoke`/`core` worlds.  
- Instruct search to return the structured final JSON.  
- Instruct manage to call `done` when finished.

### 8.3 Binding

Runner loads `prompt_id` → file → verifies digest → injects as system message. Digest mismatch aborts the run.

---

## 9. Chunk Observation for Management

When chunk \(x_t\) is presented, the observation is exactly:

```json
{
  "type": "chunk",
  "chunk": {
    "id": "chunk_003",
    "t": 3,
    "timestamp": "2025-03-12T15:00:00Z",
    "channel": "meeting",
    "title": "Sync with Priya on Atlas",
    "text": "..."
  }
}
```

Fields filtered by `agent_visible_chunk_fields`. No `introduces` / `supersedes` / gold ids.

---

## 10. Integrity and Failure Classes

| Code | Meaning | Scorecard effect |
|---|---|---|
| `ok` | Normal completion | Grade as usual |
| `max_steps_exceeded` | Hit step cap | Fail open checks that need a final answer; store still graded for manage |
| `path_error` | Sandbox violation | Step fails; repeated → abort |
| `permission_error` | Search attempted mutate | Abort query; integrity fail |
| `harness_integrity_error` | Store mutated under search | Void search grades for that query |
| `protocol_error` | Unparseable model output | Retry once; then abort |
| `prompt_digest_mismatch` | Prompt pin broken | Abort run |

---

## 11. Determinism and Sampling

Default graded runs: `temperature: 0` (or backend equivalent).  
If the backend cannot honor zero temperature, record `sampling_note` and prefer \(n \ge 3\) seeds for published means (DD-01 risk table).

Seeds: runner passes `seed` to the backend when supported; always records it.

---

## 12. Interface Hooks for Self-Learning (non-normative detail)

| Hook | Behavior |
|---|---|
| Before manage chunk | If `/policy` or `/skills` exist, prompt instructs to consult them (read tools). |
| After block (context arm) | Teacher role runs under DD-07a; manage/search not invoked as teacher. |
| Tune arm | `adapter_id` attached to RoleSpec; weights loaded before loop. |

No self-learning logic is required to implement v1 static `smoke`/`core`.

---

## 13. Decision Record

| Decision | Choice | Rationale |
|---|---|---|
| Default harness | `memory_tool_v1` six ops + `done` | Paper/industry alignment |
| Search writes | Structurally forbidden | Frozen-store grading |
| Role IDs | Per-role model + prompt | DD-01 §3.1 |
| Chunk metadata | Whitelist envelope only | DD-02 §5.4 |
| Optional grep/glob | Feature-flagged harness id | Controllable axis |
| Shell harness | Reserved | DD-01 non-goal for default |
| Final search schema | JSON answer + citations | Enables citation graders |

---

## 14. Open Points Deferred to Later Docs

| Topic | Doc |
|---|---|
| Exact JSON schemas for trajectory / final payload | DD-04 |
| Grader algorithms consuming citations / facts | DD-05 |
| Teacher tool permissions and triggers | DD-07a |
| Adapter load mechanics | DD-07b |

---

## 15. Review Checklist

- [ ] Manage vs search permissions match your intent.  
- [ ] `memory_tool_v1` tool set is sufficient for v1.  
- [ ] Whitelist binding is clear enough to implement.  
- [ ] Prompt artifact rules are strict enough.  
- [ ] Integrity failure classes are complete enough for v1.  

**Review outcome:** Approve · Approve with edits · Request rewrite  

---

*End of AMB-DD-03*
