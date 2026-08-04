# Continuous agent — model bakeoff (RTX 3070 / Ollama)

Explicit protocol to compare open-weight models on the **same** `crystal` loop.
Do not mix settings across arms.

Related: [continuous-agent.md](continuous-agent.md) · findings: [continuous-agent-findings-2026-08-03.md](continuous-agent-findings-2026-08-03.md)

## Fixed settings (all arms)

Defaults in a fresh `ambc` session (also saved to `.ambc_settings.json` when you `/set`):

| Knob | Value | Why |
|------|-------|-----|
| `llm` | `ollama` | Local GPU |
| `model` | `qwen2.5:7b-instruct-q4_K_M` | Primary bakeoff arm |
| `world` | `crystal` | Only continuous world shipped |
| `seed` | `0` | Comparable lab noise |
| `max_steps` | `30` | Enough signal without all-night runs |
| `num_ctx` | `4096` | Fits 8GB VRAM; avoid default huge ctx |
| `num_predict` | `512` | Cap tool-call / thinking tokens |
| `keep_alive` | `30m` | Avoid cold reload between steps |
| inject (optional) | same text every arm | See below |

Settings persist across restarts (cwd `.ambc_settings.json`, or `AMBC_SETTINGS`). Change model with `/set model …` — it auto-saves.

## Models to pull

Exact tags can vary; use `ollama list` after pull.

```bat
ollama pull qwen2.5:7b-instruct-q4_K_M
ollama pull qwen2.5:3b-instruct
ollama pull llama3.1:8b-instruct-q4_K_M
ollama pull mistral:7b-instruct
rem already have:
ollama pull deepseek-r1:7b-qwen-distill-q4_K_M
```

| Order | Model | Role |
|------:|-------|------|
| 1 | `qwen2.5:7b-instruct-q4_K_M` | Primary fast instruct |
| 2 | `llama3.1:8b-instruct-q4_K_M` | Alt instruct baseline |
| 3 | `mistral:7b-instruct` | Alt 7B |
| 4 | `qwen2.5:3b-instruct` | Speed / floor |
| 5 | `deepseek-r1:7b-qwen-distill-q4_K_M` | Slow reasoning arm (expect longer steps) |

## ambc checklist (one arm)

```bat
ambc
ambc> /curriculum
ambc> /run -v
ambc> /score
ambc> /report
```

`/curriculum` queues the standard temp-sweep inject for the **next** `/run` (written into that episode’s `INBOX.md` at start). `/inject <text>` does the same with custom text. Use `/inject --now …` only to write into the already-active run.

One-shot equivalent:

```bat
ambc run --llm ollama --model qwen2.5:7b-instruct-q4_K_M --max-steps 30 --seed 0 --num-ctx 4096 --num-predict 512 --keep-alive 30m -v
```

After each arm finishes, note the printed run dir, then `/set model <next>` and `/run` again (new timestamped folder). Compare with:

```bat
ambc score --run continuous_runs\<later> --compare continuous_runs\<earlier>
```

## What to record per arm

| Metric | Where |
|--------|--------|
| `stop_reason` | `REPORT.md` |
| Score pass_rate | `/score` → `scorecard.json` |
| Successful `lab_act` with real T/H | `actions.jsonl` (not fake `action` keys) |
| Protocol errors | count in `trajectory.jsonl` |
| Wall time / step | `-v` logs (`ollama chat #N … Xs`) |
| Final lab state | `lab/state.json` |

## What you are *not* losing by preferring instruct over R1

For this loop, success is **tool JSON + exploring T/H**, not long chain-of-thought. Instruct models usually give **more trials per hour**. Keep R1 as arm 5 to measure whether thinking helps the score enough to justify the cost.

## Other benches in this repo

| Surface | CLI | What it tests |
|---------|-----|----------------|
| **Continuous crystal** | `ambc` | Long-horizon tool use, memory/defer, lab discovery |
| **Suite `smoke`** | `amb run --suite suites/smoke` | Short FS memory bakeoff (Morgan KB, tea→coffee) |
| **Suite `core`** | `amb run --suite suites/core` | Fuller same world (more chunks/queries/checks) |
| **Mock oracle** | `amb run … --llm mock` | Harness/CI without a model |
| **Ollama suite** | `amb run … --llm ollama --manage-model … --search-model …` | Manage+search agents on GPU |
| **Bedrock suite** | `amb run … --llm bedrock` | Cloud upper bound (`pip install -e ".[bedrock]"`) |

Continuous has **only** `world=crystal` today. Suite bakeoffs are the main second track for “does our memory system work?” — especially `q_drink_current` (stale tea vs coffee). See [repro-drink-query.md](repro-drink-query.md) and the README FS vs RAG case.
