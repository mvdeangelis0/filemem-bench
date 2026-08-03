#!/usr/bin/env node
/**
 * Export docs/visuals/fs-vs-rag.html → fs-vs-rag.gif
 *
 * Requires: Node 18+, npx playwright (or local), ffmpeg optional.
 * Prefer the Python helper: python docs/visuals/render_gif.py
 *
 * Usage:
 *   node docs/visuals/render-gif.mjs
 */
console.log(
  "Prefer:  .venv/bin/python docs/visuals/render_gif.py\n" +
    "(Playwright + Pillow; no ffmpeg required)"
);
process.exit(0);
