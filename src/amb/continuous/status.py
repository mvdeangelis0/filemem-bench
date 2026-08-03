from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from amb.continuous.deferred import count_deferred
from amb.continuous.web_trail import read_cursor


def write_status(
    run_dir: Path,
    *,
    step: int,
    max_steps: int,
    last_tool: str | None,
    last_ok: bool | None,
    last_summary: str,
) -> None:
    plan_path = Path(run_dir) / "memory" / "current_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8")) if plan_path.exists() else {}
    task = plan.get("task", "(no task)")
    plan_step = plan.get("step", "?")
    plan_total = plan.get("steps_total", "?")
    ok_s = "ok" if last_ok is True else ("err" if last_ok is False else "n/a")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    deferred_n = count_deferred(run_dir)
    cursor = read_cursor(run_dir) or {}
    left_off = cursor.get("left_off") or "(no web activity yet)"
    body = (
        f"# Status\n\n"
        f"Task: {task}\n"
        f"Plan step: {plan_step}/{plan_total}\n"
        f"Loop step: {step}/{max_steps}\n"
        f"Last action: {last_tool or '(none)'} ({ok_s})\n"
        f"Result: {last_summary}\n"
        f"Deferred tasks: {deferred_n}\n"
        f"Web left off: {left_off}\n"
        f"Budget: {max_steps - step} steps left\n"
        f"Updated: {now}\n"
    )
    (Path(run_dir) / "STATUS.md").write_text(body, encoding="utf-8")
