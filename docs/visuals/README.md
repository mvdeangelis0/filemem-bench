# Visuals

Static research figures for the [filemem-bench](https://github.com/mvdeangelis0/filemem-bench) README (figure-first hybrid).

| Asset | Role |
|-------|------|
| [`architecture.svg`](architecture.svg) / [`.png`](architecture.png) | Pipeline: stream → manage → stores → search → grade |
| [`fs-vs-rag.svg`](fs-vs-rag.svg) / [`.png`](fs-vs-rag.png) | Bakeoff: FS+bookkeeper vs lexical RAG on `q_drink_current` |

Edit the `.svg` sources; refresh PNG with Chrome/Playwright if needed:

```bash
# optional — README can embed .svg directly on GitHub
python - <<'PY'
# see docs/superpowers/plans if a render helper is added later
print('open the SVG in a browser and export, or use rsvg-convert / Inkscape')
PY
```

Reproduce the drink query: [`../guides/repro-drink-query.md`](../guides/repro-drink-query.md).

Animated HTML boards from earlier experiments live under [`archive/`](archive/) and are **not** linked from the root README.
