# filemem-bench (`agent_memory_bench`)

Open evaluation harness for **filesystem-based agent memory** (management + search), with deterministic scorecards and reproducible run ledgers — plus a sandboxed **continuous-agent loop** (`ambc`) to test whether persistent memory pathways improve long-horizon behavior on local models.

**Not a general desktop assistant.** Continuous mode is an experiment arm (policy-gated lab, STATUS/INBOX, weighted pathways) used to decide whether that direction is worth pursuing.

**Repo:** [mvdeangelis0/filemem-bench](https://github.com/mvdeangelis0/filemem-bench) (public). Package / CLIs: `agent-memory-bench`, `amb`, `ambc`.

![Architecture](docs/visuals/architecture.png)

*Stream → manage (write) → organized/ + verbatim/chunks/ → search (read-only) → grade(ledger).*

![FS vs RAG bakeoff](docs/visuals/fs-vs-rag.png)

Same query and gold (`q_drink_current`) — **FS + bookkeeper** reaches the later update (**coffee**); **lexical RAG** can stick on early evidence (**tea**).

| Arm (Haiku / `suites/core`) | Scorecard | `q_drink_current` verbatim |
|-----------------------------|-----------|------------------------------|
| FS tools + bookkeeper | **108/109** | coffee ✓ |
| RAG lexical (TF-IDF top-k) | **106/109** | tea ✗ (stale) |

Runs: `core__bedrock_haiku__20260802_164950__57bafb64`, `core__rag_lexical__20260802_165347__57bafb64`. Reproduce: [`docs/guides/repro-drink-query.md`](docs/guides/repro-drink-query.md) · figures: [`docs/visuals/`](docs/visuals/README.md)

Desktop (RTX 3070 + Ollama): [`docs/guides/desktop-rtx3070.md`](docs/guides/desktop-rtx3070.md) · Continuous agent: [`docs/guides/continuous-agent.md`](docs/guides/continuous-agent.md)

## Quick start

```bash
git clone https://github.com/mvdeangelis0/filemem-bench.git
cd filemem-bench
python3.12 -m venv .venv   # needs Python >=3.11
source .venv/bin/activate  # Windows: .venv\Scripts\activate
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

## Continuous agent (`ambc`)

Operator-facing shell for the sandboxed lab loop (slash commands). Bench suites stay on `amb run`.

```bash
ambc                  # interactive: /help /status /inject /run …
ambc help
ambc run --world crystal --llm ollama --model deepseek-r1:7b --max-steps 50 -v
```

Prefer ~4k–8k Ollama context on an 8GB RTX 3070. Details: [`docs/guides/continuous-agent.md`](docs/guides/continuous-agent.md).
