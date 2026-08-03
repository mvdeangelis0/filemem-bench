# Visual Suite v2 Implementation Plan

> **For agentic workers:** Execute inline; checkbox tracking optional.

**Goal:** Hybrid professional chrome + five animated boards + gallery; regenerate bakeoff GIF.

**Architecture:** `shared.css` tokens/chrome; per-board HTML with SVG+CSS/SMIL motion; `index.html` gallery; README links gallery; GIF only for `fs-vs-rag`.

**Tech Stack:** HTML, CSS, SVG SMIL, Python Playwright+Pillow for GIF.

**Spec:** `docs/superpowers/specs/2026-08-02-visual-suite-v2-design.md`

### Tasks
1. Create `docs/visuals/shared.css`
2. Rewrite `fs-vs-rag.html` to use shared chrome
3. Create `manage.html`, `search.html`, `grade.html`, `stores-bookkeeper.html`
4. Create `index.html`; update visuals + root README
5. Extend `render_gif.py`; regenerate `fs-vs-rag.gif`
