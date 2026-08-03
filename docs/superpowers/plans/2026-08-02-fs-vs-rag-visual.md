# FS vs RAG Visual Implementation Plan

> **For agentic workers:** Execute task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a hand-drawn ink-on-beige animated FS-vs-RAG bakeoff diagram as HTML + GIF, linked from the README.

**Architecture:** One self-contained HTML (SVG + CSS keyframes, no runtime JS) under `docs/visuals/`; export a seamless-loop GIF for GitHub README; short visuals README documents open/re-export and Pages.

**Tech Stack:** HTML5, SVG, CSS `@keyframes` / `offset-path`, optional Node+Chrome+ffmpeg for GIF; Google Fonts (Patrick Hand) for Pages HTML only.

**Spec:** `docs/superpowers/specs/2026-08-02-fs-vs-rag-visual-design.md`

---

## File map

| File | Responsibility |
|------|----------------|
| `docs/visuals/fs-vs-rag.html` | Full interactive sketch |
| `docs/visuals/fs-vs-rag.gif` | README embed |
| `docs/visuals/README.md` | Usage + Pages note |
| `docs/visuals/render-gif.mjs` | Headless export helper |
| `README.md` | Hero GIF + link |

---

### Task 1: Create `docs/visuals/fs-vs-rag.html`

**Files:**
- Create: `docs/visuals/fs-vs-rag.html`

- [ ] **Step 1:** Build a single HTML file with:
  - Beige paper background + subtle grain
  - Title + shared query header (`What drink does Morgan prefer now?` / `q_drink_current`)
  - Two columns: **FS + bookkeeper** | **RAG lexical**
  - SVG paths with traveling dots; left path visits `chunk_001` then `chunk_008` after update nudge; right path settles on `chunk_001`
  - Answer badges: coffee ✓ / tea ✗
  - Footer caption: *Same gold. Memory representation differs.*
  - CSS loop duration 16s; all animation durations divide evenly for seamless reset
  - Font: Patrick Hand (link) with `cursive` fallback

- [ ] **Step 2:** Open in browser (or Playwright snapshot) and confirm both columns animate and labels are readable.

---

### Task 2: GIF export tooling + asset

**Files:**
- Create: `docs/visuals/render-gif.mjs`
- Create: `docs/visuals/fs-vs-rag.gif`

- [ ] **Step 1:** Write `render-gif.mjs` that loads the HTML via `file://`, records ~16s at 12–15 fps with Playwright/Puppeteer or Chrome headless, pipes frames to ffmpeg → GIF.

- [ ] **Step 2:** Run export (or fallback: Playwright screenshots + Pillow/ffmpeg). Commit the resulting `fs-vs-rag.gif` under ~3–5 MB if possible.

---

### Task 3: Docs wiring

**Files:**
- Create: `docs/visuals/README.md`
- Modify: `README.md` (after pitch paragraph)

- [ ] **Step 1:** Visuals README: open HTML locally, re-export GIF command, enable GitHub Pages from `/docs`.
- [ ] **Step 2:** Root README: embed `![FS vs RAG bakeoff](docs/visuals/fs-vs-rag.gif)` + link to interactive HTML.

---

### Task 4: Verify

- [ ] HTML opens offline (font may need network once).
- [ ] GIF loops in a viewer.
- [ ] README paths resolve.

**Commits:** Only when user asks — do not auto-commit.

---

## Spec coverage

| Spec section | Task |
|--------------|------|
| §2 Storyboard | Task 1 |
| §3 Visual system | Task 1 |
| §4 Artifacts + README | Tasks 2–3 |
| §5 Constraints | Tasks 1–2 |
| §6 Non-goals | Not implemented (correct) |
| §7 Success criteria | Task 4 |
