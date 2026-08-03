from __future__ import annotations

import json
from pathlib import Path


def write_report(run_dir: Path, *, stop_reason: str, steps: int) -> Path:
    run_dir = Path(run_dir)
    cfg = {}
    cfg_path = run_dir / "config.json"
    if cfg_path.exists():
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    status = ""
    if (run_dir / "STATUS.md").exists():
        status = (run_dir / "STATUS.md").read_text(encoding="utf-8").strip()
    body = (
        f"# Continuous run report\n\n"
        f"- run_id: {cfg.get('run_id', run_dir.name)}\n"
        f"- world: {cfg.get('world')}\n"
        f"- model: {cfg.get('model')}\n"
        f"- steps: {steps}\n"
        f"- stop_reason: {stop_reason}\n\n"
        f"## Final status\n\n```\n{status}\n```\n"
    )
    path = run_dir / "REPORT.md"
    path.write_text(body, encoding="utf-8")
    return path
