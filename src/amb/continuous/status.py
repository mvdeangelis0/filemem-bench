from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


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
    body = (
        f"# Status\n\n"
        f"Task: {task}\n"
        f"Plan step: {plan_step}/{plan_total}\n"
        f"Loop step: {step}/{max_steps}\n"
        f"Last action: {last_tool or '(none)'} ({ok_s})\n"
        f"Result: {last_summary}\n"
        f"Budget: {max_steps - step} steps left\n"
        f"Updated: {now}\n"
    )
    (Path(run_dir) / "STATUS.md").write_text(body, encoding="utf-8")
