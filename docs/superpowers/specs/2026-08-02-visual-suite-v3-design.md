# Visual suite v3 — deeper beats + livelier motion

| Field | Value |
|---|---|
| **Status** | Approved |
| **Date** | 2026-08-02 |
| **Approved** | 2026-08-02 |
| **Project** | filemem-bench / `docs/visuals` |
| **Supersedes** | Motion/depth of v2 boards; keeps hybrid chrome from `2026-08-02-visual-suite-v2-design.md` |

---

## 0. Problem

v2 boards look professional but feel **dead** (single slow dot) and **shallow** (labels without why). Visitors don’t learn the gate, top‑k failure mode, or harness artifacts.

## 1. Locked decisions

| Topic | Choice |
|-------|--------|
| Depth | **C** — narrative captions + real mechanism callouts |
| Motion | **C** — beat-synced spotlight + one light flying token |
| Engine | Pure CSS keyframes (GIF-safe, no JS runtime) |
| Loop | ~22s, typically 6 beats |
| Priority rebuild | fs-vs-rag + stores-bookkeeper first, then manage/search/grade |

## 2. Beat engine (`shared.css`)

- `--loop: 22s` (boards may set `--beats` conceptually as equal slices)
- `.narration` — stacked captions; only active beat at full opacity
- `.mech` — monospace chip/drawer with tool JSON, gate error, top‑k scores, or check ids
- `.step[data-i]` — dim inactive (~0.35); active = full opacity + accent ring
- `.token` — single flying element on a path
- `.progress` — beat dots 1…N synced to the timeline

Keep v2 hybrid tokens (paper, ink, ok/bad/nudge). Sketch accents remain on paths/dots only.

## 3. Board scripts

### FS vs RAG (hero)

1. Same query both arms — `q_drink_current`
2. FS views early chunk — tea — `{"tool":"view","arguments":{"path":"chunks/chunk_001.md"}}`
3. Gate rejects premature done — `later_update_unchecked`, hint `chunk_008`
4. FS views update — coffee ✓ — cite `chunk_008`
5. RAG top‑k — early tea ranked above update — score callout `001 ≫ 008`
6. Side-by-side finals — coffee ✓ vs tea ✗ — “representation differs”

### Stores + bookkeeper

Twin panels → premature done on `chunk_001` → gate payload → forced view `chunk_008` → organized path note.

### Manage / search / grade

Five–six beats each: real tool names, artifact folders, check ids (`mgmt.update_precedence…`, `search.answer_match…`). Same engine.

## 4. Delivery

- Rebuild all five HTML boards + extend `shared.css`
- Update gallery one-liners if needed
- `render_gif.py`: default loop **22s**; regenerate `fs-vs-rag.gif`
- Root README still one hero GIF + gallery link

## 5. Non-goals

- JS stepper / Lottie / video
- Live binding to runs
- Five README GIFs

## 6. Success criteria

1. Someone new can explain *why* FS gets coffee and RAG gets tea after one loop.
2. At least one real harness string visible per beat (tool, gate code, or check id).
3. Motion feels stepped (spotlight), not a single drifting dot.
4. GIF still loops on GitHub README.

## 7. Implementation order

1. Beat primitives in `shared.css`
2. Rebuild `fs-vs-rag.html`, `stores-bookkeeper.html`
3. Rebuild `manage.html`, `search.html`, `grade.html`
4. Regenerate GIF; smoke-open gallery
