# Visuals

Animated explainers for [filemem-bench](https://github.com/mvdeangelis0/filemem-bench).

## Gallery

Open [`index.html`](index.html) for the full set:

| Board | File |
|-------|------|
| Management agent | [`manage.html`](manage.html) |
| Search agent | [`search.html`](search.html) |
| Grade the ledger | [`grade.html`](grade.html) |
| Stores + bookkeeper | [`stores-bookkeeper.html`](stores-bookkeeper.html) |
| FS vs RAG bakeoff | [`fs-vs-rag.html`](fs-vs-rag.html) |

Shared look: [`shared.css`](shared.css) (professional chrome + sketch accents on flows).

## README hero GIF

[`fs-vs-rag.gif`](fs-vs-rag.gif) — ~22s six-beat loop for the bakeoff board.

### Re-export

```bash
pip install playwright Pillow
python docs/visuals/render_gif.py            # fs-vs-rag (default)
python docs/visuals/render_gif.py manage     # optional other boards
```

Uses system Chrome (`channel=chrome`).

### GitHub Pages

Settings → Pages → Deploy from branch → `/docs`.  
Gallery: `https://<user>.github.io/filemem-bench/visuals/index.html`
