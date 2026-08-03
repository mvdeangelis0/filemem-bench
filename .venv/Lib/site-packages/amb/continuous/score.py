from __future__ import annotations

import json
import re
from pathlib import Path

CRYSTAL_CHECKS = [
    {"id": "temp_near_37", "pattern": r"\b(3[5-9]|40)\b"},
    {"id": "humidity_band", "pattern": r"(?i)humid|\b4[0-9]\b|\b5[0-9]\b|\b60\b"},
]


def _memory_corpus(run_dir: Path) -> str:
    parts: list[str] = []
    mem = Path(run_dir) / "memory"
    if mem.is_dir():
        for path in sorted(mem.rglob("*")):
            if path.is_file() and path.suffix.lower() in {".md", ".json", ".jsonl", ".txt"}:
                try:
                    parts.append(path.read_text(encoding="utf-8"))
                except OSError:
                    continue
    return "\n".join(parts)


def score_run(run_dir: Path, *, world: str | None = None) -> dict:
    run_dir = Path(run_dir)
    cfg = {}
    if (run_dir / "config.json").exists():
        cfg = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
    world = world or str(cfg.get("world") or "crystal")
    checks = CRYSTAL_CHECKS if world == "crystal" else CRYSTAL_CHECKS
    corpus = _memory_corpus(run_dir)
    results = []
    for check in checks:
        ok = re.search(check["pattern"], corpus) is not None
        results.append({"id": check["id"], "pass": ok})
    n_passed = sum(1 for r in results if r["pass"])
    n_total = len(results)
    scorecard = {
        "world": world,
        "checks": results,
        "summary": {
            "n_passed": n_passed,
            "n_total": n_total,
            "pass_rate": (n_passed / n_total) if n_total else 0.0,
        },
    }
    (run_dir / "scorecard.json").write_text(
        json.dumps(scorecard, indent=2) + "\n", encoding="utf-8"
    )
    return scorecard


def compare_episodes(early: Path, late: Path) -> dict:
    early_sc = score_run(Path(early))
    late_sc = score_run(Path(late))
    early_rate = float(early_sc["summary"]["pass_rate"])
    late_rate = float(late_sc["summary"]["pass_rate"])
    return {
        "early": early_sc["summary"],
        "late": late_sc["summary"],
        "improved": late_rate >= early_rate,
        "delta": late_rate - early_rate,
    }
