# Next experiments: bakeoff matrix + bookkeeper update rule

Date: 2026-08-02  
Basis: Bedrock Haiku smoke `smoke__bedrock_haiku__20260802_081601__57bafb64` — **31/33** after protocol harden.  
Only remaining miss: `q_drink_current` verbatim (answered `tea` from `chunk_001`, never opened `chunk_008`).

---

## 1. Three-arm bakeoff matrix

Same suite (`smoke` first, then `core`), same gold/checks, same model when possible. The point is to isolate **memory representation**, not prompt craft.

| Arm | Store the search agent sees | Who writes memory | What we are testing |
|-----|-----------------------------|-------------------|---------------------|
| **A. FS organized** | `people/`, `projects/`, … after manage | Manage agent (LLM) + tools | Addressable filesystem memory (north-star arm) |
| **B. Verbatim + bookkeeper** | Raw `chunks/` plus deterministic briefs/hints | Stream dump + **no LLM rewrite**; bookkeeper only | Can deterministic librarianship beat “read the log”? |
| **C. RAG-over-chunks** | Top-k retrieved chunk texts (no FS tools, or tools only over retrieved set) | Embeddings + retriever | Fair bakeoff baseline people will demand |

### Fixed across arms

- Suite, queries, gold, graders, seed
- Search model (start: same Haiku profile; later: Ollama R1 for local)
- Max search steps / temperature
- Report: pass rate + **protocol vs memory** failure split (see below)

### Allowed to differ

- What the first user message contains (store_map vs chunk_timeline vs retrieved passages)
- Whether manage runs (A yes; B/C no — verbatim store is built from the stream)

### What “win” means

Primary (smoke, then core):

1. **Search pass rate** on the shared scorecard (answer_match + citations_*).
2. **Update-awareness subset** (`q_drink_current` and any later update queries) — FS/bookkeeper must beat RAG if the north star is real.
3. **Cost / latency** per run (tokens or wall time) — secondary, not a veto.

Win criteria for a claim in writeups:

| Claim | Pass condition |
|-------|----------------|
| “Organized FS works” | Arm A ≥ 90% smoke search proxy with capable model (already ~true: 26/28 search, 14/14 organized) |
| “FS beats RAG on updates” | Arm A (or B) > Arm C on update_awareness checks by a clear margin (≥2 checks on smoke; revisit on core) |
| “Bookkeeper helps streams” | Arm B > raw verbatim-without-bookkeeper on the same model (control = today’s verbatim path) |
| “Not just protocol” | Memory fails ≫ protocol fails after harden |

Non-goals for v1 bakeoff: HITL, self-learning, LangGraph, multi-model manage/search mix.

### Failure taxonomy (add to report)

Every failed search check tagged:

- `protocol` — unparseable / non-tool / max_steps after protocol_error
- `memory` — on-protocol answer wrong, stale, or bad citations
- `abstain_miss` — should have known / should have unknown

Without this, Ollama vs Bedrock comparisons stay confounded.

### Suggested run order (cheap → dear)

1. **Control:** regrade/label current 31/33 run (A organized + B-without-bookkeeper verbatim already in one suite run).
2. **Implement B hint** (section 2) → one Haiku smoke (~$0.25).
3. **Arm C stub:** embed smoke chunks, retrieve top-3 per query, grade same gold (no tools) → one Haiku or even extractive baseline.
4. Same matrix on Ollama once B/C exist.
5. Promote to `core` only after smoke matrix is stable.

---

## 2. Smallest bookkeeper rule (drink / `chunk_008` case)

### What happened

```
view chunk_001  → tea
view chunk_010  → Atlas status (irrelevant)
done answer=tea citations=[chunk_001]
```

`chunk_008` exists in `store_map` and contains the superseding fact. Hint text alone did not force a later read.

### Smallest rule (deterministic, no LLM)

**Name:** `later_update_gate`  
**When:** search `done` on a **chunk store** (verbatim), non-abstain answer.  
**Do:**

1. Build a chunk timeline from files under `chunks/` (path, `t` from frontmatter or filename order, body text).
2. Let `cited` = citation paths on this `done`.
3. Let `cited_max_t` = max `t` among cited chunk files (0 if none).
4. Find **later update candidates**: chunks with `t > cited_max_t` whose body matches a cheap update heuristic **and** overlaps the query:
   - Update heuristic: line matches `(?i)\b(update:|now prefers|no longer|not tea|instead of)\b` **or** body contains both a gold-ish conflict pattern later (keep heuristic generic: `Update:` prefix or `now prefers`).
   - Query overlap: any query token length ≥4 appears in the later chunk body (casefold), or token from answer’s forbidden/stale forms if we only have the query string — **use query tokens only** so the gate stays suite-agnostic.
5. If any later update candidate exists, **reject** `done` with observation:
   - `error_code: later_update_unchecked`
   - `hint_paths: [...]` (sorted by `t`)
   - message: view these later chunks before answering; facts may have been updated.

That single reject would have forced Haiku to open `chunk_008` after citing `chunk_001` for the drink query (query token `prefer` / `drink` / `Morgan` appear in chunk_008).

### Explicitly out of scope for v1

- Writing organized files from the bookkeeper
- Embedding search
- Parsing “current drink = coffee” into a structured fact table
- Changing gold or soft-matching further

### Where it plugs in

- `Bookkeeper.chunk_timeline()` + `Bookkeeper.later_update_candidates(query, cited_paths)`
- `validate_citations` stays as-is; new check lives in `run_search` next to citation gate (search-only, chunk stores only)
- Optional: also inject `chunk_timeline` (id, t, title only — not full bodies) into the first user message so the model *sees* later updates exist before the gate fires

### Success check

Re-run Haiku smoke: `q_drink_current` verbatim passes (answer coffee, citation includes `chunk_008` or another supporting path). Overall ≥ 32/33. No manage regression.

---

## 3. Recommendation

Do **section 2** next (small, closes the only smoke miss, enables Arm B).  
Then stand up **Arm C** as a thin RAG script against the same verbatim chunks and print one comparison table.  
Only then widen to `core` / Ollama / writeup claims about beating embeddings.
