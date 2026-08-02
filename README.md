# agent_memory_bench

Open evaluation harness for **filesystem-based agent memory** (management + search), with deterministic scorecards and reproducible run ledgers.

**Repo:** [mvdeangelis0/filemem-bench](https://github.com/mvdeangelis0/filemem-bench) (public). Local package name remains `agent-memory-bench` / `amb`.

Desktop (RTX 3070 + Ollama): [`docs/guides/desktop-rtx3070.md`](docs/guides/desktop-rtx3070.md).

## Quick start

```bash
git clone https://github.com/mvdeangelis0/filemem-bench.git
cd filemem-bench
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

`--llm mock` = scripted oracle (CI). Live GPU (Ollama):

```bash
amb run --suite suites/smoke --llm ollama \
  --manage-model deepseek-r1:7b \
  --search-model deepseek-r1:7b \
  --out runs
```

Optional cloud upper-bound (AWS Bedrock; needs `pip install -e ".[bedrock]"` + inference profile id):

```bash
amb run --suite suites/smoke --llm bedrock \
  --manage-model us.anthropic.claude-haiku-4-5-20251001-v1:0 \
  --search-model us.anthropic.claude-haiku-4-5-20251001-v1:0 \
  --out runs -v
```
