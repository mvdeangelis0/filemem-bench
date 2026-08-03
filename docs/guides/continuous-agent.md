# Continuous agent (sandbox lab)

Windows-first notes for the RTX 3070 desktop. Spec: `docs/superpowers/specs/2026-08-02-continuous-agent-design.md`.

First live-run writeup (what the 7B actually did, crash fix, score caveats): `docs/guides/continuous-agent-findings-2026-08-03.md`.

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

## Capabilities + deferred tasks

Every run includes `core/capabilities.md` (what is allowed *now*). Out-of-scope work should go to `memory/deferred.jsonl` via:

- tool `defer` `{task, reason, need}`, or
- automatic enqueue when policy denies a tool

Watch with:

```bat
ambc> /use D:\ambc_lab\<run_id>
ambc> /deferred
ambc> /trail
ambc> /status
```

STATUS shows a deferred count and **Web left off** (last browse breadcrumb).

## Web trail

When web tools are used, the agent leaves breadcrumbs:

- `memory/web_trail.jsonl` — append-only history (when, action, url/query, title, snippet, ok)
- `memory/web_cursor.json` — where it left off (resume pointer)

Each step’s prompt includes the cursor + recent trail so it can continue instead of restarting cold. Use `/trail` to inspect.

## Track, map, and ask (operator)

All durable state for a run lives under one folder. Manage it with:

```bat
ambc> /use D:\ambc_lab\<run_id>
ambc> /tree          rem inventory of stored files
ambc> /map           rem writes OPERATOR_MAP.md (roles, pathways, deferred, trail)
ambc> /ask What did we learn about humidity?
ambc> /open memory/notes.md
```

`/ask` does lexical retrieval over the run’s text files, then answers with your configured LLM (`/set llm ollama` + `/set model …`). Sources are listed after the answer. This is **read-only Q&A for you** — it does not grant the agent new tools.
