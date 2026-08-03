from __future__ import annotations

import time
from pathlib import Path
from typing import Any


def should_stop(run_dir: Path) -> bool:
    return (Path(run_dir) / "STOP").exists()


def run_daemon(
    *,
    run_episode_fn: Any,
    out_dir: Path,
    world: str,
    llm: Any,
    max_steps: int,
    seed: int,
    model_id: str,
    idle_seconds: float = 1.0,
    max_episodes: int | None = None,
    web_allowlist: list[str] | None = None,
    verbose: bool = True,
) -> list[Path]:
    """Run episodes until STOP file appears in the latest run or max_episodes.

    For simplicity, STOP is checked on each finished episode directory and also
    on out_dir/STOP (global stop).
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    runs: list[Path] = []
    episode = 0
    while True:
        if (out_dir / "STOP").exists():
            break
        if max_episodes is not None and episode >= max_episodes:
            break
        episode += 1
        run_dir = run_episode_fn(
            out_dir,
            world=world,
            llm=llm,
            max_steps=max_steps,
            seed=seed + episode - 1,
            model_id=model_id,
            run_id=f"daemon_{episode:04d}",
            verbose=verbose,
            web_allowlist=web_allowlist,
        )
        runs.append(run_dir)
        if should_stop(run_dir) or (out_dir / "STOP").exists():
            break
        if idle_seconds > 0:
            time.sleep(idle_seconds)
    return runs
