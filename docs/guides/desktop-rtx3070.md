# Desktop setup (RTX 3070 + Ollama)

This repo is a **standalone git project** (`agent_memory_bench`). Do not nest it under another product’s remote.

## 1. Get the code

```bash
git clone https://github.com/mvdeangelis0/filemem-bench.git
cd filemem-bench
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
  --out runs -v
```

You should see `[amb] probing Ollama…`, then `manage 1/N`, `ollama chat #…` lines. Trust `nvidia-smi` for GPU util. Prompts are `memory_tool.v2` (relative-path few-shots). After a run, check `stores/organized/` is non-empty.

Expect lower pass rates than mock (mock is scripted oracle). Inspect `runs/<id>/REPORT.md` and failed checks.

Then scale to `suites/core` overnight if smoke looks sane.

## 5. Optional Bedrock upper-bound arm

Requires AWS creds + `pip install -e ".[bedrock]"`. Use an **inference profile** id (not the raw foundation model id):

```bash
amb run --suite suites/smoke --llm bedrock \
  --manage-model us.anthropic.claude-haiku-4-5-20251001-v1:0 \
  --search-model us.anthropic.claude-haiku-4-5-20251001-v1:0 \
  --aws-region us-east-1 \
  --out runs -v
```

This is a cloud comparison arm (costs money). Local Ollama remains the primary 24/7 target.

## 6. Continuous sandboxed agent

See [continuous-agent.md](continuous-agent.md). Preferred operator UI: **`ambc`** (interactive `/help`, `/status`, `/inject`, `/run`, …). Prefer 4k–8k Ollama context on 8GB VRAM (`/set num_ctx 4096`, `/set num_predict 512`, `/set keep_alive 30m`).

Model bakeoff checklist: [continuous-model-bakeoff.md](continuous-model-bakeoff.md).

## 7. Security note

Do **not** bind raw Ollama (`0.0.0.0:11434`) to the public internet. Keep it local; tunnel later behind an authenticated API if needed.
