# Reproducing `q_drink_current` (drink update bakeoff)

Pinned suite fact: Morgan’s drink goes **tea → coffee**. Gold answer is **coffee**; **tea** is forbidden.

| Pin | Value |
|-----|--------|
| Query id | `q_drink_current` |
| Suite wording | `What does Morgan prefer to drink?` ([`suites/core/gold/queries.yaml`](../suites/core/gold/queries.yaml)) |
| Early evidence | `chunk_001` (tea) |
| Update evidence | `chunk_008` (coffee) |
| Gold | `answers_any: [coffee]` · `answers_forbidden_any: [tea]` |
| Checks | `search.answer_match.q_drink_current` (+ citations_*) |

Visuals paraphrase the question for readability; **runs must use the suite YAML**, not the visual caption.

---

## Fully deterministic (any machine, no API)

```bash
cd filemem-bench   # or agent_memory_bench
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

amb validate-suite suites/core
amb run --suite suites/core --llm mock --seed 42 --arm repro_drink --out runs
```

Mock search is scripted to answer coffee with the right citations. Use this to verify graders/plumbing in a new environment.

Inspect:

```bash
rg -n "q_drink_current" runs/*repro_drink*/scorecard.json
cat runs/*repro_drink*/REPORT.md
```

---

## Live bakeoff pair (same seed, two search modes)

Pin **suite path**, **seed**, **models**, and **arm** names so runs are comparable across machines.

```bash
SUITE=suites/core
SEED=42
# Example Bedrock Haiku — replace with your inference profile ids
MODEL=us.anthropic.claude-haiku-4-5-20251001-v1:0

pip install -e ".[dev,bedrock]"

amb run --suite "$SUITE" --llm bedrock --seed "$SEED" \
  --manage-model "$MODEL" --search-model "$MODEL" \
  --search-mode tools --arm fs_tools --out runs -v

amb run --suite "$SUITE" --llm bedrock --seed "$SEED" \
  --manage-model "$MODEL" --search-model "$MODEL" \
  --search-mode rag --rag-top-k 3 --arm rag_lexical --out runs -v
```

Local GPU (Ollama) — same pins, different `--llm` / model ids:

```bash
amb run --suite "$SUITE" --llm ollama --seed "$SEED" \
  --manage-model deepseek-r1:7b --search-model deepseek-r1:7b \
  --search-mode tools --arm fs_tools --out runs -v
```

Compare `q_drink_current` rows in each `scorecard.json` / `REPORT.md`. FS+bookkeeper should reach **coffee**; lexical RAG may answer **tea** if top‑k buries `chunk_008`.

---

## Regrade without re-running models

```bash
amb regrade runs/<run_id> --suite suites/core
```

Same suite version ⇒ same checks. Do not edit gold mid-comparison.

---

## What must stay identical for a claim

1. Suite directory (or tagged commit containing that suite)
2. `--seed`
3. `--search-mode` (`tools` vs `rag`) and `--rag-top-k` for RAG
4. Manage/search model ids (and provider)
5. Harness / package version (`amb --version`)

Record these in `config.json` inside the run dir (written by the runner). Publish run dirs or REPORT excerpts with the commit SHA.

---

## Minimal content check (no LLM)

Confirm the stream still encodes the trap:

```bash
rg -n "tea|coffee|prefers" suites/core/stream/chunks.yaml
```

You should see tea early (`chunk_001`) and a later coffee update (`chunk_008`).
