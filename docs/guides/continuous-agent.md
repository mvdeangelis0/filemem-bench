# Continuous agent (sandbox lab)

Windows-first notes for the RTX 3070 desktop. Spec: `docs/superpowers/specs/2026-08-02-continuous-agent-design.md`.

## Setup (Windows)

```bat
cd agent_memory_bench
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
pytest tests\test_continuous_*.py -q
```

Ollama should already be running locally (`http://127.0.0.1:11434`). Prefer **4k–8k** context on an 8GB 3070; do not max out advertised context.

## Dedicated CLI: `ambc`

Interactive slash-command shell (recommended on the desktop):

```bat
ambc
ambc> /help
ambc> /set llm ollama
ambc> /set model deepseek-r1:7b
ambc> /set max_steps 50
ambc> /run -v
ambc> /status
ambc> /inject Focus on humidity next
ambc> /tail 20
ambc> /graph
ambc> /score
ambc> /quit
```

One-shot:

```bat
ambc help
ambc run --llm ollama --model deepseek-r1:7b --max-steps 50 --out continuous_runs -v
ambc status --run continuous_runs\<run_id>
ambc inject --run continuous_runs\<run_id> "Focus on humidity"
ambc score --run continuous_runs\<run_id>
```

`amb continuous …` still works for scripts; `ambc` is the operator-facing front end.

## Mock smoke

```bat
ambc run --world crystal --llm mock --max-steps 20 --out continuous_runs -v
```

Empty mock LLM will stop on protocol failures; for a scripted path use pytest `test_continuous_loop_mock.py`.

## Watch + steer

```bat
ambc> /status
ambc> /inject Focus on humidity next
ambc> /open memory/graph.json
```

Also on disk:

- `trajectory.jsonl` / `actions.jsonl` — every step  
- `memory\graph.json` — weighted pathways  
- `INBOX.md` — your instructions  

## Score

```bat
ambc score --run continuous_runs\<run_id>
ambc score --run continuous_runs\<later> --compare continuous_runs\<earlier>
```

## Daemon

```bat
ambc daemon --world crystal --llm ollama --model deepseek-r1:7b --max-steps 30 --max-episodes 5 --idle-seconds 2 --out continuous_runs -v
```

Or from the shell: `/daemon --max-episodes 5` then `/stop` from another terminal (writes `continuous_runs\STOP`).

`--observer` is accepted but currently a no-op stub.

## Safety

No raw shell. Workspace paths are confined to the run directory. Web tools need an explicit `--web-allowlist host1,host2` (default: empty = denied). Bounded Python uses a restricted exec (Windows-safe timeout via threads, not signals).
