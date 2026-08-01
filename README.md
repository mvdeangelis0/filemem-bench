# agent_memory_bench

Open evaluation harness for **filesystem-based agent memory** (management + search), with deterministic scorecards and reproducible run ledgers.

**Repo:** [mvdeangelis0/filemem-bench](https://github.com/mvdeangelis0/filemem-bench) (public). Local package name remains `agent-memory-bench` / `amb`.

Design docs: [`docs/design/`](docs/design/).  
Desktop (RTX 3070 + Ollama): [`docs/guides/desktop-rtx3070.md`](docs/guides/desktop-rtx3070.md).  
Implementation plan (smoke v1): [`docs/superpowers/plans/2026-08-01-amb-smoke-v1.md`](docs/superpowers/plans/2026-08-01-amb-smoke-v1.md).

## Quick start

```bash
cd agent_memory_bench
python3.12 -m venv .venv   # needs Python >=3.11
source .venv/bin/activate
pip install -e ".[dev]"
pytest
amb validate-suite suites/smoke
amb validate-suite suites/core
amb run --suite suites/core --llm mock --out runs
amb regrade runs/<run_id> --suite suites/core
```

Suites: `smoke` (10 chunks) ⊂ `core` (24 chunks, same `morgan_personal_v1` world).

`--llm mock` = scripted oracle (CI). Live GPU:

```bash
amb run --suite suites/smoke --llm ollama \
  --manage-model deepseek-r1:7b \
  --search-model deepseek-r1:7b \
  --out runs
```
