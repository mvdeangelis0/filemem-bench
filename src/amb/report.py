from __future__ import annotations

import json
from pathlib import Path


def write_report(run_dir: Path) -> Path:
    run_dir = Path(run_dir)
    config = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
    scorecard = {}
    if (run_dir / "scorecard.json").exists():
        scorecard = json.loads((run_dir / "scorecard.json").read_text(encoding="utf-8"))
    usage = {}
    if (run_dir / "usage.json").exists():
        usage = json.loads((run_dir / "usage.json").read_text(encoding="utf-8"))
    summary = scorecard.get("summary") or {}
    failed = [
        r
        for r in scorecard.get("results") or []
        if r.get("gate") == "scorecard" and not r.get("passed")
    ]
    lines = [
        f"# Run {config.get('run_id', run_dir.name)}",
        "",
        f"- Suite: `{config.get('suite', {}).get('id')}@{config.get('suite', {}).get('version')}`",
        f"- Arm: `{config.get('arm_id')}`",
        f"- Harness: `{config.get('harness_id')}`",
        f"- Seed: `{config.get('seed')}`",
        "",
        "## Roles",
        "",
    ]
    for role, spec in (config.get("roles") or {}).items():
        lines.append(
            f"- **{role}**: model=`{spec.get('model_id')}` prompt=`{spec.get('prompt_id')}`"
        )
    lines += [
        "",
        "## Scorecard",
        "",
        f"- Pass rate: **{summary.get('pass_rate', 'n/a')}** "
        f"({summary.get('n_passed', 0)}/{summary.get('n_scorecard', 0)})",
        f"- Manage proxy: `{summary.get('by_role_proxy', {}).get('management')}`",
        f"- Search proxy: `{summary.get('by_role_proxy', {}).get('search')}`",
        "",
    ]
    if usage:
        total = usage.get("total") or {}
        est = usage.get("estimate") or {}
        by = usage.get("by_role") or {}
        usd = est.get("usd")
        usd_s = f"${usd:.4f}" if isinstance(usd, (int, float)) else "n/a"
        lines += [
            "## Usage",
            "",
            f"- Calls: `{total.get('n_calls')}` "
            f"(manage `{((by.get('manage') or {}).get('n_calls'))}`, "
            f"search `{((by.get('search') or {}).get('n_calls'))}`)",
            f"- Tokens: in=`{total.get('input_tokens')}` out=`{total.get('output_tokens')}`",
            f"- Estimated cost: **{usd_s}** "
            f"({est.get('note', 'list-price estimate')})",
            "",
        ]
    lines += [
        "## Failed checks",
        "",
    ]
    if not failed:
        lines.append("_None_")
    else:
        for r in failed:
            lines.append(
                f"- `{r.get('check_id')}` ({r.get('family')}): {r.get('detail')}"
            )
    lines += [
        "",
        "## Disclaimer",
        "",
        "This run measures static management/search under the pinned suite and check set. "
        "It is not a self-learning claim unless arm/protocol say otherwise.",
        "",
    ]
    path = run_dir / "REPORT.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
