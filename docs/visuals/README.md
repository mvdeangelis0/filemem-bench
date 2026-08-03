# Visuals

Static research figures for the [filemem-bench](https://github.com/mvdeangelis0/filemem-bench) README (figure-first hybrid).

| Asset | Role |
|-------|------|
| [`architecture.svg`](architecture.svg) / [`.png`](architecture.png) | Pipeline: stream → manage → stores → search → grade |
| [`fs-vs-rag.svg`](fs-vs-rag.svg) / [`.png`](fs-vs-rag.png) | Bakeoff: FS+bookkeeper vs lexical RAG on `q_drink_current` |

Edit the `.svg` sources; refresh PNGs with `rsvg-convert` (do **not** use macOS Quick Look — it pads to a square and crops wide figures):

```bash
# brew install librsvg
rsvg-convert -w 1920 docs/visuals/architecture.svg -o docs/visuals/architecture.png
rsvg-convert -w 1920 docs/visuals/fs-vs-rag.svg -o docs/visuals/fs-vs-rag.png
```

Reproduce the drink query: [`../guides/repro-drink-query.md`](../guides/repro-drink-query.md).

Animated HTML boards from earlier experiments live under [`archive/`](archive/) and are **not** linked from the root README.
