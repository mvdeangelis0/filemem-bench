# Visual suite v2 — hybrid chrome + five boards

| Field | Value |
|---|---|
| **Status** | Approved |
| **Date** | 2026-08-02 |
| **Approved** | 2026-08-02 |
| **Project** | `agent_memory_bench` / filemem-bench |
| **Supersedes (style)** | v1 pure sketch on `fs-vs-rag` → restyle to hybrid C |
| **Depends on** | `docs/superpowers/specs/2026-08-02-fs-vs-rag-visual-design.md` (story for bakeoff board) |

---

## 0. Goal

Polish the bakeoff visual to a **more professional hybrid** look and ship **four additional** animated boards so visitors can see the main harness functions end-to-end: manage, search, grade, dual stores + bookkeeper, and FS vs RAG.

Display: **git** (README hero GIF + gallery link) and **site** (Pages / local HTML).

---

## 1. Locked decisions

| Topic | Choice |
|-------|--------|
| Professional look | **C** — clean chrome + sketch accents on paths/dots only |
| Board set | **3** — full pack (five boards) |
| Packaging | Shared design system + five HTML pages + gallery index |
| README | Keep **one** hero GIF (bakeoff); link to gallery for the rest |

---

## 2. Boards

| File | Function | One-line story |
|------|----------|----------------|
| `manage.html` | Management agent | Chunk arrives → tool loop (`create` / `str_replace` / …) → fact lands in organized tree |
| `search.html` | Search agent | Query + fresh context → `view` paths → answer + citations |
| `grade.html` | Graders | Ledger artifacts → check functions → scorecard / REPORT |
| `stores-bookkeeper.html` | Stores + bookkeeper | Organized ↔ verbatim twins; later_update_gate forces a later chunk read |
| `fs-vs-rag.html` | Bakeoff (polished) | Same `q_drink_current`: FS → coffee ✓, RAG → tea ✗ |

Plus `index.html` gallery linking all five (title, one sentence, open link).

---

## 3. Visual system (hybrid C)

**Chrome (professional)**

- Background: soft warm paper `#f7f4ef` (not loud craft beige)
- Text: near-black `#1c1917`; secondary stone `#57534e`
- Surfaces: white/cream panels, 1–1.5px borders, consistent radius (~10–12px), light shadow only if needed for separation
- Type: Source Sans 3 / IBM Plex Sans (or similar) for titles and body; small caps / mono-ish for ids (`q_drink_current`, `chunk_008`)
- Masthead: product name + board title + short subtitle
- Footer caption: one teaching sentence

**Sketch accents (only)**

- Dashed flow paths
- Traveling dots (SMIL `animateMotion` or CSS)
- Optional tiny handwritten caption on a path (Caveat), sparingly

**Semantics**

- Pass / correct: forest green
- Fail / stale: clay red
- Bookkeeper nudge: amber

**Motion**

- Loop ~14s per board; durations divide the loop evenly
- Parallel columns allowed (bakeoff, stores); linear pipelines for manage/search/grade

**Explicitly avoid:** purple gradients, glow, dashboard card grids, heavy wobble/rotate on boxes, emoji clutter.

---

## 4. Repo layout

| Path | Role |
|------|------|
| `docs/visuals/shared.css` | Tokens, masthead, footer, panels, SVG helpers |
| `docs/visuals/{manage,search,grade,stores-bookkeeper,fs-vs-rag}.html` | Boards |
| `docs/visuals/index.html` | Gallery |
| `docs/visuals/fs-vs-rag.gif` | README hero (regenerated after restyle) |
| `docs/visuals/render_gif.py` | Accept board basename; default `fs-vs-rag` |
| `docs/visuals/README.md` | How to open, gallery, Pages, re-export |
| Root `README.md` | Hero GIF + link to `docs/visuals/index.html` |

**GIF policy (v2):** Regenerate bakeoff GIF only for README. Other boards are HTML-first (optional GIF export documented, not required for merge).

---

## 5. Per-board beats (short)

**manage** — stream tick → agent → tools → `people/morgan.md` (or `memory.md`) updates drink/deadline.

**search** — query chip → view `chunk_001` → (optional) later path → `done` with answer + citation chips.

**grade** — folder icons (`trajectories/`, `stores/`, `search_outputs/`) → grader → `scorecard.json` / `REPORT.md` with pass fraction.

**stores-bookkeeper** — split: organized tree vs `chunks/`; gate rejects early `done` until `chunk_008` viewed.

**fs-vs-rag** — existing dual-column story under new chrome (same vocabulary).

---

## 6. Non-goals

- Live binding to run artifacts
- Five GIFs in the root README
- Dark theme
- Suite tier cutover work in this stream
- Pixel-perfect recreation of third-party sketch skills

---

## 7. Success criteria

1. Gallery opens all five boards; each loop teaches its function without prose docs.
2. Bakeoff still reads in one loop: coffee vs tea / representation differs.
3. Look is clearly more professional than v1 while paths still feel hand-drawn.
4. Root README: one GIF + gallery link; no broken paths.
5. `render_gif.py fs-vs-rag` regenerates the hero GIF.

---

## 8. Implementation order

1. Add `shared.css` + restyle `fs-vs-rag.html`
2. Build `manage`, `search`, `grade`, `stores-bookkeeper`
3. Build `index.html`; update visuals README + root README
4. Regenerate `fs-vs-rag.gif`
5. Spot-check in browser

---

## 9. Open points (resolved)

| Item | Resolution |
|------|------------|
| Look | Hybrid C |
| Scope | Full pack (5) |
| Packaging | Shared CSS + pages + gallery |
| README GIFs | Bakeoff only |
