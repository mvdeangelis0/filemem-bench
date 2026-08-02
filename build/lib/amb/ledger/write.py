from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class RunWriter:
    def __init__(self, run_dir: Path) -> None:
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        for sub in (
            "stream",
            "stores/organized",
            "stores/verbatim",
            "trajectories/manage",
            "trajectories/search/organized",
            "trajectories/search/verbatim",
            "search_outputs/organized",
            "search_outputs/verbatim",
            "prompts",
            "meta",
        ):
            (self.run_dir / sub).mkdir(parents=True, exist_ok=True)

    def write_json(self, rel: str, obj: Any) -> Path:
        path = self.run_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return path

    def write_config(self, config: dict[str, Any]) -> Path:
        return self.write_json("config.json", config)

    def write_chunks(self, chunks: list[dict[str, Any]], whitelist: list[str]) -> Path:
        path = self.run_dir / "stream" / "chunks.jsonl"
        with path.open("w", encoding="utf-8") as f:
            for c in chunks:
                filtered = {k: c[k] for k in whitelist if k in c}
                f.write(json.dumps(filtered, ensure_ascii=False) + "\n")
        return path

    def copy_prompt(self, prompt_id: str, src: Path) -> str:
        dest = self.run_dir / "prompts" / f"{prompt_id}.md"
        shutil.copy2(src, dest)
        return sha256_file(dest)

    def write_search_output(self, shape: str, query_id: str, payload: dict[str, Any]) -> Path:
        return self.write_json(f"search_outputs/{shape}/{query_id}.json", payload)

    def write_trajectory(self, rel: str, steps: list[dict[str, Any]]) -> Path:
        path = self.run_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for step in steps:
                f.write(json.dumps(step, ensure_ascii=False) + "\n")
        return path

    def write_scorecard(self, scorecard: dict[str, Any]) -> Path:
        return self.write_json("scorecard.json", scorecard)

    def write_diagnostics(self, diagnostics: dict[str, Any]) -> Path:
        return self.write_json("diagnostics.json", diagnostics)

    def write_manifest(self) -> Path:
        files = []
        for path in sorted(self.run_dir.rglob("*")):
            if not path.is_file():
                continue
            if path.name == "MANIFEST.json":
                continue
            rel = path.relative_to(self.run_dir).as_posix()
            files.append(
                {
                    "path": rel,
                    "sha256": sha256_file(path),
                    "bytes": path.stat().st_size,
                }
            )
        return self.write_json(
            "MANIFEST.json",
            {"schema_version": "amb_manifest_v1", "files": files},
        )

    def organized_root(self) -> Path:
        return self.run_dir / "stores" / "organized"

    def verbatim_root(self) -> Path:
        return self.run_dir / "stores" / "verbatim"
