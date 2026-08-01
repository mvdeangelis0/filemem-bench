from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from amb.agents.llm import LLM, OllamaLLM
from amb.agents.manage import run_manage
from amb.agents.scripted_smoke import manage_llm_for_smoke, search_llm_for_query
from amb.agents.search import run_search
from amb.graders.engine import grade
from amb.ledger.write import RunWriter
from amb.report import write_report
from amb.suite.load import load_suite
from amb.suite.validate import validate_suite
from amb.verbatim import build_verbatim

REPO_ROOT = Path(__file__).resolve().parents[2]


def _filter_chunk(chunk: dict[str, Any], whitelist: list[str]) -> dict[str, Any]:
    return {k: chunk[k] for k in whitelist if k in chunk}


def run_suite(
    suite_path: Path | str,
    *,
    out_dir: Path | str,
    llm_mode: str = "mock",
    seed: int = 0,
    manage_model: str = "mock",
    search_model: str = "mock",
    arm_id: str = "baseline",
    ollama_host: str | None = None,
) -> Path:
    suite_path = Path(suite_path)
    suite = load_suite(suite_path)
    errors = validate_suite(suite)
    if errors:
        raise ValueError("suite invalid:\n" + "\n".join(errors))

    whitelist = list(
        suite.meta.get("agent_visible_chunk_fields")
        or ["id", "t", "timestamp", "channel", "title", "text"]
    )
    short = hashlib.sha256(f"{seed}:{llm_mode}:{manage_model}".encode()).hexdigest()[:8]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_id = f"{suite.meta['id']}__{arm_id}__{stamp}__{short}"
    run_dir = Path(out_dir) / run_id
    writer = RunWriter(run_dir)

    manage_prompt = (REPO_ROOT / "prompts" / "manage" / "memory_tool.v1.md").read_text(
        encoding="utf-8"
    )
    search_prompt = (REPO_ROOT / "prompts" / "search" / "memory_tool.v1.md").read_text(
        encoding="utf-8"
    )
    manage_digest = writer.copy_prompt(
        "manage.memory_tool.v1", REPO_ROOT / "prompts" / "manage" / "memory_tool.v1.md"
    )
    search_digest = writer.copy_prompt(
        "search.memory_tool.v1", REPO_ROOT / "prompts" / "search" / "memory_tool.v1.md"
    )

    host = ollama_host or os.environ.get("OLLAMA_HOST") or "http://127.0.0.1:11434"
    if llm_mode == "mock":
        manage_model_id = "mock/scripted_smoke"
        search_model_id = "mock/scripted_smoke"
    else:
        manage_model_id = f"ollama/{manage_model}"
        search_model_id = f"ollama/{search_model}"

    config = {
        "schema_version": "amb_ledger_v1",
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "suite": {
            "id": suite.meta.get("id"),
            "version": suite.meta.get("version"),
            "path": str(suite_path.resolve()),
        },
        "arm_id": arm_id,
        "protocol": "static",
        "harness_id": suite.meta.get("harness_default", "memory_tool_v1"),
        "shapes": suite.meta.get("shapes", ["organized", "verbatim"]),
        "seed": seed,
        "roles": {
            "manage": {
                "model_id": manage_model_id,
                "prompt_id": "manage.memory_tool.v1",
                "prompt_digest": manage_digest,
                "adapter_id": None,
                "temperature": 0.0,
                "max_steps": 30,
            },
            "search": {
                "model_id": search_model_id,
                "prompt_id": "search.memory_tool.v1",
                "prompt_digest": search_digest,
                "adapter_id": None,
                "temperature": 0.0,
                "max_steps": 20,
            },
        },
        "check_set_id": suite.check_set_id,
        "diagnostics_set_id": suite.diagnostics_set_id,
        "agent_visible_chunk_fields": whitelist,
        "llm_mode": llm_mode,
        "ollama_host": host if llm_mode == "ollama" else None,
        "eval_held_out": False,
    }
    writer.write_config(config)
    writer.write_chunks(suite.chunks, whitelist)

    build_verbatim(writer.verbatim_root(), suite.chunks, whitelist)

    if llm_mode == "mock":
        manage_llm: LLM = manage_llm_for_smoke()
        for chunk in suite.chunks:
            visible = _filter_chunk(chunk, whitelist)
            steps = run_manage(
                manage_llm,
                writer.organized_root(),
                visible,
                manage_prompt,
                max_steps=30,
            )
            writer.write_trajectory(f"trajectories/manage/{chunk['id']}.jsonl", steps)

        for query in suite.queries:
            qid = query["id"]
            for shape in query.get("shapes") or ["organized"]:
                store = (
                    writer.organized_root()
                    if shape == "organized"
                    else writer.verbatim_root()
                )
                search_llm = search_llm_for_query(qid, shape=shape)
                payload, steps = run_search(
                    search_llm, store, query["q"], search_prompt, max_steps=20
                )
                payload["query_id"] = qid
                payload["shape"] = shape
                writer.write_search_output(shape, qid, payload)
                writer.write_trajectory(
                    f"trajectories/search/{shape}/{qid}.jsonl", steps
                )
    elif llm_mode == "ollama":
        if manage_model in {"mock", ""} or search_model in {"mock", ""}:
            raise ValueError(
                "ollama mode requires --manage-model and --search-model "
                "(e.g. deepseek-r1:7b)"
            )
        manage_llm = OllamaLLM(manage_model, base_url=host)
        search_llm_shared = OllamaLLM(search_model, base_url=host)

        for chunk in suite.chunks:
            visible = _filter_chunk(chunk, whitelist)
            steps = run_manage(
                manage_llm,
                writer.organized_root(),
                visible,
                manage_prompt,
                max_steps=30,
            )
            writer.write_trajectory(f"trajectories/manage/{chunk['id']}.jsonl", steps)

        for query in suite.queries:
            qid = query["id"]
            for shape in query.get("shapes") or ["organized"]:
                store = (
                    writer.organized_root()
                    if shape == "organized"
                    else writer.verbatim_root()
                )
                payload, steps = run_search(
                    search_llm_shared,
                    store,
                    query["q"],
                    search_prompt,
                    max_steps=20,
                )
                payload["query_id"] = qid
                payload["shape"] = shape
                writer.write_search_output(shape, qid, payload)
                writer.write_trajectory(
                    f"trajectories/search/{shape}/{qid}.jsonl", steps
                )
    else:
        raise ValueError(f"unknown llm_mode {llm_mode}")

    scorecard, diagnostics = grade(run_dir, suite)
    writer.write_scorecard(scorecard)
    writer.write_diagnostics(diagnostics)
    write_report(run_dir)
    writer.write_manifest()
    return run_dir
