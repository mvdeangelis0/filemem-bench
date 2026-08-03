from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def deferred_path(run_dir: Path) -> Path:
    return Path(run_dir) / "memory" / "deferred.jsonl"


def append_deferred(
    run_dir: Path,
    *,
    task: str,
    reason: str,
    need: str,
    source: str = "agent",
    tool: str | None = None,
) -> dict[str, Any]:
    """Append one deferred task. need examples: web, shell, pip, host_fs, larger_model."""
    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "task": task.strip(),
        "reason": reason.strip(),
        "need": need.strip().lower() or "unknown",
        "source": source,
        "tool": tool,
        "status": "deferred",
    }
    path = deferred_path(run_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def list_deferred(run_dir: Path, *, limit: int | None = None) -> list[dict[str, Any]]:
    path = deferred_path(run_dir)
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    if limit is not None:
        return rows[-limit:]
    return rows


def count_deferred(run_dir: Path) -> int:
    return len(list_deferred(run_dir))


def infer_need_from_policy(tool: str, reason: str) -> str:
    r = (reason or "").lower()
    t = (tool or "").lower()
    if "web" in t or "allowlist" in r or "host not" in r:
        return "web"
    if "python" in t or "blocked pattern" in r:
        return "python_privilege"
    if "path" in r or "escape" in r:
        return "host_fs"
    if "not allowed" in r or "unknown tool" in r:
        if any(x in t for x in ("bash", "shell", "terminal")):
            return "shell"
        return "capability"
    return "capability"


def render_capabilities(
    *,
    world: str,
    web_allowlist: list[str] | None,
    max_steps: int | None = None,
) -> str:
    web = list(web_allowlist or [])
    web_line = (
        f"- Web: enabled for hosts {', '.join(web)}"
        if web
        else "- Web: DISABLED (empty allowlist)"
    )
    steps = (
        f"- Budget: max_steps={max_steps}"
        if max_steps is not None
        else "- Budget: set at run time"
    )
    return (
        "# Capabilities (this run)\n\n"
        "You must only attempt work covered below. Anything else: use tool "
        "`defer` with a clear task + need tag, then continue with in-scope work.\n\n"
        "## Allowed now\n"
        f"- World: `{world}` lab tools (`lab_sense`, `lab_act`)\n"
        "- `lab_act` arguments are only `temperature` and/or `humidity` (numbers)\n"
        "- Workspace files under this run directory only (`view`, `create`, `str_replace`)\n"
        "- Paths must be relative — examples: `memory/notes.md`, `lab/state.json` "
        "(never absolute paths or `/path/to/...`)\n"
        "- Bounded Python (no os/subprocess/network imports); pass `{\"code\": \"...\"}`\n"
        f"{web_line}\n"
        "- End episode early with `done`\n"
        "- Park out-of-scope work with `defer`\n\n"
        "## Not allowed\n"
        "- Shell / OS commands\n"
        "- Leaving the run directory (absolute paths, `..`, home, secrets)\n"
        "- Package install, Docker, SSH, purchases, messaging\n"
        "- Self-preservation, escape, replication, or resisting shutdown\n"
        "- Claiming a deferred task is complete\n\n"
        f"{steps}\n"
    )
