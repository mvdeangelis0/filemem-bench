from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from amb.continuous.deferred import list_deferred
from amb.continuous.inbox import consume_inbox
from amb.continuous.lab import load_world
from amb.continuous.layout import init_run_dir
from amb.continuous.memory_graph import MemoryGraph
from amb.continuous.policy import Policy
from amb.continuous.report import write_report
from amb.continuous.status import write_status
from amb.continuous.tools import ToolRuntime
from amb.continuous.web_trail import list_trail, read_cursor

_TOOL_SCHEMAS: list[dict[str, Any]] = [
    {"name": "lab_sense", "description": "Read lab instruments"},
    {"name": "lab_act", "description": "Set temperature/humidity and run a trial"},
    {"name": "view", "description": "Read a workspace file"},
    {"name": "create", "description": "Create a workspace file"},
    {"name": "str_replace", "description": "Replace text in a workspace file"},
    {"name": "run_bounded_python", "description": "Run bounded Python"},
    {"name": "search_allowlisted_web", "description": "Search allowlisted web"},
    {"name": "fetch_allowlisted_page", "description": "Fetch allowlisted URL"},
    {
        "name": "defer",
        "description": "Park an out-of-scope task for later (task, reason, need)",
    },
    {"name": "done", "description": "End the episode"},
]


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _read_prompt() -> str:
    candidates = [
        Path(__file__).resolve().parents[3] / "prompts" / "continuous" / "agent.v1.md",
        Path.cwd() / "prompts" / "continuous" / "agent.v1.md",
    ]
    for path in candidates:
        if path.is_file():
            return path.read_text(encoding="utf-8")
    return "You are a continuous lab research agent. Use one tool per turn."


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _action_key(tool: str, arguments: dict[str, Any]) -> str:
    return json.dumps({"tool": tool, "arguments": arguments}, sort_keys=True)


def _labels_for(tool: str, arguments: dict[str, Any], result: dict[str, Any]) -> list[str]:
    labels = [tool]
    for key in ("temperature", "humidity", "path"):
        if key in arguments:
            labels.append(f"{key}:{arguments[key]}")
    sense = result.get("result")
    if isinstance(sense, dict):
        for key in ("temperature", "humidity", "growth"):
            if key in sense:
                labels.append(str(key))
    return labels


def _build_user_message(run_dir: Path, *, graph_pack: list[dict], inbox_text: str) -> str:
    objective = (run_dir / "core" / "objective.md").read_text(encoding="utf-8")
    caps_path = run_dir / "core" / "capabilities.md"
    capabilities = (
        caps_path.read_text(encoding="utf-8")
        if caps_path.exists()
        else "(capabilities missing)"
    )
    status = (run_dir / "STATUS.md").read_text(encoding="utf-8")
    plan = (run_dir / "memory" / "current_plan.json").read_text(encoding="utf-8")
    deferred = list_deferred(run_dir, limit=8)
    deferred_txt = (
        json.dumps(deferred, indent=2) if deferred else "(none — good; stay in-scope)"
    )
    cursor = read_cursor(run_dir) or {}
    trail_tail = list_trail(run_dir, limit=5)
    web_left_off = cursor.get("left_off") or "(no web activity yet)"
    obs_path = run_dir / "memory" / "observations.jsonl"
    tail_lines: list[str] = []
    if obs_path.exists():
        lines = [ln for ln in obs_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        tail_lines = lines[-8:]
    parts = [
        "## Objective\n" + objective.strip(),
        "## Capabilities\n" + capabilities.strip(),
        "## Status\n" + status.strip(),
        "## Plan\n" + plan.strip(),
        "## Deferred (do not pretend these are done)\n" + deferred_txt,
        "## Web trail — where you left off\n"
        + web_left_off
        + "\n\nRecent trail:\n"
        + (json.dumps(trail_tail, indent=2) if trail_tail else "(empty)"),
        "## Pathway pack\n" + json.dumps(graph_pack, indent=2),
        "## Recent observations\n" + ("\n".join(tail_lines) if tail_lines else "(none)"),
    ]
    if inbox_text:
        parts.insert(0, "## Operator instruction (high priority)\n" + inbox_text)
    parts.append(
        "Choose the next single tool call. Prefer in-scope work; use defer for the rest."
    )
    return "\n\n".join(parts)


def run_episode(
    out_dir: Path | str,
    *,
    world: str,
    llm: Any,
    max_steps: int,
    seed: int,
    model_id: str,
    run_id: str | None = None,
    verbose: bool = True,
    web_allowlist: list[str] | None = None,
) -> Path:
    out_dir = Path(out_dir)
    if run_id is None:
        run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + f"__{world}"
    allow = list(web_allowlist or [])
    run_dir = init_run_dir(
        out_dir,
        run_id=run_id,
        world=world,
        seed=seed,
        model=model_id,
        web_allowlist=allow,
        max_steps=max_steps,
    )
    cfg = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
    cfg["max_steps"] = max_steps
    cfg["web_allowlist"] = allow
    (run_dir / "config.json").write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")

    policy = Policy(web_allowlist=allow)
    lab = load_world(world, run_dir / "lab", seed=seed)
    tools = ToolRuntime(run_dir, world=lab, policy=policy)
    graph = MemoryGraph(run_dir / "memory" / "graph.json")
    system = _read_prompt()

    stop_reason = "max_steps"
    consecutive_failures = 0
    last_key: str | None = None
    repeat_count = 0
    steps_done = 0

    write_status(
        run_dir,
        step=0,
        max_steps=max_steps,
        last_tool=None,
        last_ok=None,
        last_summary="starting",
    )

    try:
        for step in range(1, max_steps + 1):
            steps_done = step
            inbox_text = consume_inbox(run_dir)
            plan = json.loads((run_dir / "memory" / "current_plan.json").read_text(encoding="utf-8"))
            query_tokens = [str(plan.get("task", "")), world]
            graph_pack = graph.retrieve(query_tokens=query_tokens, top_k=5)
            messages = [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": _build_user_message(
                        run_dir, graph_pack=graph_pack, inbox_text=inbox_text
                    ),
                },
            ]
            response = llm.complete(messages, _TOOL_SCHEMAS)
            _append_jsonl(
                run_dir / "trajectory.jsonl",
                {"step": step, "response": response, "inbox": inbox_text},
            )

            if not isinstance(response, dict) or response.get("type") != "tool_call":
                consecutive_failures += 1
                write_status(
                    run_dir,
                    step=step,
                    max_steps=max_steps,
                    last_tool=None,
                    last_ok=False,
                    last_summary="protocol_error: expected tool_call",
                )
                if verbose:
                    _log(f"[continuous] step {step}/{max_steps} protocol_error")
                if consecutive_failures >= 3:
                    stop_reason = "protocol_failures"
                    break
                continue

            tool = str(response.get("tool") or "")
            arguments = dict(response.get("arguments") or {})
            key = _action_key(tool, arguments)
            if key == last_key:
                repeat_count += 1
            else:
                last_key = key
                repeat_count = 1

            if verbose:
                _log(f"[continuous] step {step}/{max_steps} tool={tool} args={arguments}")

            tools.step = step
            result = tools.execute(tool, arguments)
            ok = bool(result.get("ok"))
            _append_jsonl(
                run_dir / "actions.jsonl",
                {"step": step, "tool": tool, "arguments": arguments, "result": result},
            )

            obs_id = f"step_{step}"
            obs = {
                "id": obs_id,
                "step": step,
                "tool": tool,
                "arguments": arguments,
                "ok": ok,
                "result": result,
            }
            _append_jsonl(run_dir / "memory" / "observations.jsonl", obs)
            graph.observe(
                _labels_for(tool, arguments, result),
                observation_id=obs_id,
                success=ok and bool(result.get("informative", ok)),
            )

            summary = (
                result.get("error")
                or result.get("summary")
                or str(result.get("result", ""))[:200]
            )
            write_status(
                run_dir,
                step=step,
                max_steps=max_steps,
                last_tool=tool,
                last_ok=ok,
                last_summary=str(summary),
            )

            if not ok:
                consecutive_failures += 1
            else:
                consecutive_failures = 0

            if result.get("done"):
                stop_reason = "done"
                break
            if consecutive_failures >= 3:
                stop_reason = "consecutive_failures"
                break
            if repeat_count >= 3:
                # Give one structured observation then stop if still looping.
                _append_jsonl(
                    run_dir / "memory" / "observations.jsonl",
                    {
                        "id": f"loop_warn_{step}",
                        "step": step,
                        "warning": "repeated identical action; break the loop",
                    },
                )
                stop_reason = "loop_detected"
                if verbose:
                    _log(f"[continuous] loop detected at step {step}")
                break
    except Exception as e:  # noqa: BLE001 — always leave a REPORT.md
        stop_reason = f"crash:{type(e).__name__}"
        if verbose:
            _log(f"[continuous] crash: {type(e).__name__}: {e}")
        raise
    finally:
        write_report(run_dir, stop_reason=stop_reason, steps=steps_done)
        if verbose:
            _log(f"[continuous] stop_reason={stop_reason} steps={steps_done} dir={run_dir}")
    return run_dir
