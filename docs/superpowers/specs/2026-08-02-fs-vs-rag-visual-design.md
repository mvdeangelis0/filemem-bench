# FS vs RAG bakeoff visual (animated sketch)

| Field | Value |
|---|---|
| **Status** | Approved |
| **Date** | 2026-08-02 |
| **Approved** | 2026-08-02 |
| **Project** | `agent_memory_bench` / [filemem-bench](https://github.com/mvdeangelis0/filemem-bench) |
| **Audience** | Repo visitors (README + GitHub Pages) |

---

## 0. Goal

Ship a **hand-drawn, ink-on-beige animated diagram** that teaches the north-star bakeoff claim: **same query and gold, different memory representation** — filesystem tools + bookkeeper vs lexical RAG — using the real drink-update miss (`coffee` vs `tea`).

Display on **git (README GIF)** and **site (Pages HTML)** from one story.

---

## 1. Locked decisions

| Topic | Choice |
|-------|--------|
| Story | Bakeoff contrast only (not full manage→grade E2E) |
| Surfaces | GIF in README **and** interactive HTML on Pages |
| Style | Hand-drawn sketch (ink on beige), kin to [animated-sketch-diagram](https://github.com/OLDyade/animated-sketch-diagram) |
| Layout | Hybrid: shared query header + dual columns |
| Build method | Hand-authored SVG + CSS in-repo (approach 1) |

---

## 2. Narrative storyboard

**Shared header**

- Query (spoken-language): *What drink does Morgan prefer now?*
- Small meta: `q_drink_current` · same suite / gold

**Left column — Arm A: FS + bookkeeper**

1. Search sees store map / chunk timeline (sketch icons, not full UI chrome).
2. Dot visits early `chunk_001` (tea).
3. Bookkeeper / later-update nudge highlights later path.
4. Dot opens `chunk_008` (coffee).
5. Answer badge: **coffee** (correct).

**Right column — Arm C: RAG lexical**

1. Top-k passages appear (early tea-heavy chunks).
2. Dot settles on early tea evidence; no forced later read.
3. Answer badge: **tea** (wrong / stale).

**Footer caption**

- *Same gold. Memory representation differs.*
- Optional tiny note: illustrative of the core bakeoff gap (Haiku FS vs RAG on `q_drink_current`).

**Motion**

- Seamless loop ~12–18s.
- Sequence: query pulse → both arms advance in parallel → left updates / right stalls → answers light → brief hold → reset.
- Motion narrates topology (traveling dots on paths); no decorative-only sparkle.

---

## 3. Visual system

- Background: warm paper beige (sketch family; intentional for this artifact).
- Strokes: dark ink, slightly imperfect boxes/lines (CSS or hand-tuned SVG paths — not glossy cards).
- Typography: handwriting-like webfont **self-hosted or system fallback** (e.g. Patrick Hand / Caveat OFL if embedded; otherwise a single Google Fonts link only in the HTML Pages version — GIF must not depend on network).
- Accent: restrained ink red/green for wrong/right answers only.
- No dark-mode default; no purple glow; no dashboard chrome.

---

## 4. Repo artifacts

| Path | Purpose |
|------|---------|
| `docs/visuals/fs-vs-rag.html` | Self-contained interactive sketch (SVG + CSS; minimal or zero JS) |
| `docs/visuals/fs-vs-rag.gif` | Seamless loop for README |
| `docs/visuals/README.md` | How to open HTML; how to re-export GIF |
| `docs/visuals/render-gif.mjs` (or `.sh`) | Optional: headless Chrome + ffmpeg export |

**README.md (repo root)**

- Near top (after one-line pitch): embed GIF + link to interactive version.
- Link target: GitHub Pages URL when enabled; until then, link to `docs/visuals/fs-vs-rag.html` on `main`.

**GitHub Pages**

- Prefer `/docs` site root (or document `docs/visuals/` as entry).
- Enabling Pages in repo settings is a human step; shipping files does not require Pages to be live on day one.

---

## 5. Technical constraints

- README cannot run JS → **GIF (or APNG)** for in-markdown animation.
- HTML must open offline by double-click where possible (embed fonts as data-URI only if size stays reasonable; otherwise Pages + system fallback).
- Prefer pure SVG + CSS `@keyframes` / `offset-path` (or SMIL) for the loop.
- Labels use real vocabulary: `chunk_001`, `chunk_008`, coffee, tea, bookkeeper / later update, RAG top-k.
- Do not claim live scores inside the graphic; caption may say “illustrative.”

---

## 6. Non-goals (v1)

- Full run film (stream → manage → dual store → grade).
- Live wiring to `usage.json` / scorecards.
- Arm B (verbatim-only without bakeoff frame) as a third column.
- Pixel-perfect clone of upstream sketch skill internals.
- Auto-enable GitHub Pages via API (document the click).

---

## 7. Success criteria

1. Someone new understands in one loop: **FS path gets coffee; RAG path gets tea; reason is representation.**
2. GIF embeds cleanly in GitHub README.
3. HTML opens in a browser and loops without a build step.
4. Copy matches suite language; no invented APIs.
5. Files live under `docs/visuals/` and are linked from root README.

---

## 8. Implementation order (after spec approval)

1. Author `fs-vs-rag.html` to the storyboard.
2. Export `fs-vs-rag.gif` (script or one-shot capture); verify seamless loop.
3. Write `docs/visuals/README.md`.
4. Patch root `README.md` with hero embed + link.
5. Note Pages setup in visuals README.
6. Stop — no suite cutover or agent code changes in this workstream.

---

## 9. Open points (resolved)

| Item | Resolution |
|------|------------|
| Primary story | Bakeoff B |
| Hosting | GIF + Pages (C) |
| Style | Sketch A |
| Layout | Hybrid 3 |
| Build | Hand-authored in-repo |
