from __future__ import annotations

import json
import re
from pathlib import Path

_TEMP_BAND = (35.0, 40.0)
_HUM_BAND = (40.0, 60.0)
_CLAIM_TEMP = re.compile(r"(?i)(?:temp(?:erature)?|t)\s*[≈~=:]?\s*(3[5-9]|40)\b|\b(3[5-9]|40)\s*°?\s*c\b")
_CLAIM_HUM = re.compile(
    r"(?i)humid(?:ity)?\s*[≈~=:]?\s*(4[0-9]|5[0-9]|60)\b|"
    r"\b(4[0-9]|5[0-9]|60)\s*%|\bH\s*[≈~=:]?\s*(4[0-9]|5[0-9]|60)\b"
)


def _iter_actions(run_dir: Path) -> list[dict]:
    path = Path(run_dir) / "actions.jsonl"
    if not path.is_file():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _successful_lab_acts(run_dir: Path) -> list[dict]:
    out: list[dict] = []
    for row in _iter_actions(run_dir):
        if row.get("tool") != "lab_act":
            continue
        result = row.get("result") or {}
        if not result.get("ok"):
            continue
        args = row.get("arguments") or {}
        out.append(args if isinstance(args, dict) else {})
    return out


def _claim_corpus(run_dir: Path) -> str:
    """Only operator-facing writeups — not raw observations (avoids false greens)."""
    parts: list[str] = []
    for name in ("lessons.md", "notes.md"):
        path = Path(run_dir) / "memory" / name
        if path.is_file():
            try:
                parts.append(path.read_text(encoding="utf-8"))
            except OSError:
                continue
    return "\n".join(parts)


def _has_lab_act_in_band(acts: list[dict], key: str, lo: float, hi: float) -> bool:
    for args in acts:
        if key not in args:
            continue
        try:
            val = float(args[key])
        except (TypeError, ValueError):
            continue
        if lo <= val <= hi:
            return True
    return False


def score_run(run_dir: Path, *, world: str | None = None) -> dict:
    run_dir = Path(run_dir)
    cfg = {}
    if (run_dir / "config.json").exists():
        cfg = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
    world = world or str(cfg.get("world") or "crystal")
    acts = _successful_lab_acts(run_dir)
    claims = _claim_corpus(run_dir)
    results = [
        {
            "id": "lab_act_temp_35_40",
            "pass": _has_lab_act_in_band(acts, "temperature", *_TEMP_BAND),
        },
        {
            "id": "lab_act_humidity_40_60",
            "pass": _has_lab_act_in_band(acts, "humidity", *_HUM_BAND),
        },
        {
            "id": "lessons_or_notes_claim",
            "pass": bool(_CLAIM_TEMP.search(claims) and _CLAIM_HUM.search(claims)),
        },
    ]
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
