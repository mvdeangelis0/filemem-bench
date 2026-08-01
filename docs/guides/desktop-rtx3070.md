# Desktop setup (RTX 3070 + Ollama)

This repo is a **standalone git project** (`agent_memory_bench`). Do not nest it under another product’s remote.

## 1. Get the code

```bash
git clone https://github.com/Marrett-io/agent_memory_bench.git
cd agent_memory_bench
```

Or copy the folder once, then:

```bash
cd agent_memory_bench
git remote -v   # should be THIS project's remote only
```

## 2. Python env

```bash
python3.12 -m venv .venv   # 3.11+ required
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
```

## 3. Ollama

```bash
ollama serve   # if not already a service
ollama pull deepseek-r1:7b   # or another 7B Q4/Q5 that fits 8GB
ollama list
```

Optional: `export OLLAMA_HOST=http://127.0.0.1:11434`

## 4. First live run (smoke only)

```bash
amb run --suite suites/smoke --llm ollama \
  --manage-model deepseek-r1:7b \
  --search-model deepseek-r1:7b \
  --out runs
```

Expect lower pass rates than mock (mock is scripted oracle). Inspect `runs/<id>/REPORT.md` and failed checks.

Then scale to `suites/core` overnight if smoke looks sane.

## 5. Security note

Do **not** bind raw Ollama (`0.0.0.0:11434`) to the public internet. Keep it local; tunnel later behind an authenticated API if needed.
