# Suite tier cutover (tiny / smoke / core)

| Field | Value |
|---|---|
| **Status** | Draft for review |
| **Date** | 2026-08-02 |
| **Decisions locked** | Long-term B (today’s core → smoke); approach 1 (rename in place) |
| **Depends on** | Metering in place (`usage.json`); bakeoff uses discriminating suite |

---

## 0. Why

Soft `suites/smoke` (10 chunks / soft gold) saturates at **33/33** for both FS and RAG under Haiku, so it cannot support bakeoff claims. Today’s `suites/core` (24 chunks / 18 queries) is the discriminating suite (FS 108/109 vs RAG 106/109; shared manage miss on Atlas leftover). Daily iteration and bakeoffs should run on that suite under the name **`smoke`**.

---

## 1. Target layout

| Path | Content after cutover | Role |
|------|----------------------|------|
| `suites/tiny` | Today’s soft smoke (10 chunks, soft scorecard) | Install / CI / mock “does it run?” only. **No bakeoff or paper claims.** |
| `suites/smoke` | Today’s core (24 chunks, 18 queries, hard traps) | Default daily suite; FS vs RAG bakeoff matrix. |
| `suites/core` | Copy of new smoke at cutover | Headline / longer suite; **must grow later**; smoke remains a **chunk+query prefix** of core. |

Default docs and CLI examples point at `suites/smoke`. `amb run --suite suites/core` remains valid but identical until core grows.

### Mechanical rename (approach 1)

```text
mv suites/smoke → suites/tiny
mv suites/core  → suites/smoke
cp -R suites/smoke → suites/core
```

Then rewrite `suite.yaml` ids / check_set ids / notes / README per §2. Do **not** leave two editable copies that drift without the prefix test.

---

## 2. Metadata after cutover

### `suites/tiny/suite.yaml`

- `id: tiny`
- `version: "1.0.0"` (content = old smoke 1.0.0)
- `check_set_id: tiny_scorecard_v1` (rename file + ids from `smoke_*`)
- `diagnostics_set_id: tiny_diagnostics_v1`
- Keep soft `min_chunks` / `min_queries` / categories as today
- Notes: install/CI only; not for bakeoff claims

### `suites/smoke/suite.yaml`

- `id: smoke`
- `version: "2.0.0"` (content bump: former core 1.0.0)
- `check_set_id: smoke_scorecard_v1` (rename from `core_scorecard_v1`; check **ids** stay stable where possible, e.g. `mgmt.update_precedence.atlas_deadline`)
- `diagnostics_set_id: smoke_diagnostics_v1`
- Keep core’s `min_*`, `categories_required`, `citation_support_policy`
- Notes: discriminating daily suite; former core content

### `suites/core/suite.yaml`

- `id: core`
- `version: "2.0.0"` (starts identical to smoke 2.0.0)
- `check_set_id: core_scorecard_v1` (copy of smoke scorecard; may diverge when core grows)
- `diagnostics_set_id: core_diagnostics_v1`
- Notes: **will grow**; smoke chunks (and shared query subset) must remain a prefix

---

## 3. Invariants & tests

1. **`smoke ⊆ core` (chunks):** `smoke.chunks[i] == core.chunks[i]` for all `i < len(smoke.chunks)` (id + text). Enforce in `tests/test_core_suite.py` (update from today’s soft-prefix test).
2. **Optional soft link:** `tiny` stream text for `chunk_001`…`chunk_010` matches the same ids in smoke (already true today). Keep as a warning-level or soft test; tiny gold may differ (e.g. soft Atlas date) — do **not** require tiny gold ⊂ smoke gold.
3. **Validate all three** suites in CI / `pytest`.
4. **Mock run:** scripted mock already covers hard-suite query ids; point mock CI at `tiny` (fast) and keep one mock run on `smoke` (≥0.95 pass).
5. **Graders / fixtures:** move fixture path references (`stale_drink` → tiny or smoke as appropriate; `stale_deadline` / `stale_editor` live under smoke+core).

---

## 4. Code & docs touch list

| Area | Change |
|------|--------|
| `tests/test_core_suite.py` | Prefix = smoke⊂core; add `test_tiny_validates`; smoke mock run |
| `tests/test_graders.py` | Fixture roots: soft drink → `suites/tiny/...`; deadline → `suites/smoke/...` |
| `tests/test_run_mock.py` | Prefer `suites/tiny` for speed |
| `README.md`, `docs/guides/*` | Default examples → `suites/smoke`; mention `tiny` for install |
| `docs/guides/bakeoff-and-bookkeeper-next.md` | Bakeoff primary suite = smoke (new); note old soft runs are historical |
| `scripted_smoke.py` | Rename optional (`scripted_mock`); behavior already covers hard queries — no logic change required |
| Historical `runs/*` | Leave as-is; suite path in `config.json` is archival |

Out of scope for this cutover: growing core with new chunks; fixing Atlas leftover-March-28 manage bug; changing graders.

---

## 5. Success criteria

- `amb validate-suite` OK on `tiny`, `smoke`, `core`
- `pytest` green, including smoke⊂core prefix
- Mock smoke pass_rate ≥ 0.95
- Docs default to `suites/smoke`
- No change to harness/agent behavior beyond suite paths

---

## 6. Explicit non-goals

- Shrinking smoke below today’s core size
- Alias / indirection loaders
- Retiring tiny
- Re-running paid Haiku bakeoff as part of the cutover (optional follow-up with metering)

---

## 7. Implementation order

1. Git mv/copy directories as in §1
2. Rewrite suite.yaml + check_set filenames/ids + READMEs
3. Update tests + docs references
4. `pytest` + validate-suite all three
5. Commit cutover alone (meter/cachePoint commits stay separate unless asked to bundle)
