from __future__ import annotations

import hashlib
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from amb.agents.llm import BedrockLLM, LLM, OllamaLLM, probe_bedrock, probe_ollama
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


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _filter_chunk(chunk: dict[str, Any], whitelist: list[str]) -> dict[str, Any]:
    return {k: chunk[k] for k in whitelist if k in chunk}


def _run_live_manage_search(
    *,
    suite: Any,
    writer: RunWriter,
    whitelist: list[str],
    manage_llm: LLM,
    search_llm: LLM,
    manage_prompt: str,
    search_prompt: str,
) -> None:
    n_chunks = len(suite.chunks)
    for i, chunk in enumerate(suite.chunks, 1):
        _log(f"[amb] manage {i}/{n_chunks} chunk={chunk['id']}")
        t0 = time.perf_counter()
        visible = _filter_chunk(chunk, whitelist)
        steps = run_manage(
            manage_llm,
            writer.organized_root(),
            visible,
            manage_prompt,
            max_steps=30,
            progress=True,
        )
        writer.write_trajectory(f"trajectories/manage/{chunk['id']}.jsonl", steps)
        _log(
            f"[amb] manage {i}/{n_chunks} done in {time.perf_counter() - t0:.1f}s "
            f"({len(steps)} steps)"
        )

    search_jobs = [
        (q, shape)
        for q in suite.queries
        for shape in (q.get("shapes") or ["organized"])
    ]
    for j, (query, shape) in enumerate(search_jobs, 1):
        qid = query["id"]
        _log(f"[amb] search {j}/{len(search_jobs)} query={qid} shape={shape}")
        t0 = time.perf_counter()
        store = (
            writer.organized_root() if shape == "organized" else writer.verbatim_root()
        )
        payload, steps = run_search(
            search_llm,
            store,
            query["q"],
            search_prompt,
            max_steps=20,
            progress=True,
        )
        payload["query_id"] = qid
        payload["shape"] = shape
        writer.write_search_output(shape, qid, payload)
        writer.write_trajectory(f"trajectories/search/{shape}/{qid}.jsonl", steps)
        _log(
            f"[amb] search {j}/{len(search_jobs)} done in {time.perf_counter() - t0:.1f}s "
            f"({len(steps)} steps)"
        )


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
    aws_region: str | None = None,
    verbose: bool = False,
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

    # Progress on by default for long live runs; -v adds per-call timing.
    progress = verbose or llm_mode in {"ollama", "bedrock"}
    t_run = time.perf_counter()
    if progress:
        _log(
            f"[amb] run_id={run_id} suite={suite.meta.get('id')} "
            f"chunks={len(suite.chunks)} queries={len(suite.queries)} llm={llm_mode}"
        )

    manage_prompt_path = REPO_ROOT / "prompts" / "manage" / "memory_tool.v2.md"
    search_prompt_path = REPO_ROOT / "prompts" / "search" / "memory_tool.v2.md"
    manage_prompt = manage_prompt_path.read_text(encoding="utf-8")
    search_prompt = search_prompt_path.read_text(encoding="utf-8")
    manage_digest = writer.copy_prompt("manage.memory_tool.v2", manage_prompt_path)
    search_digest = writer.copy_prompt("search.memory_tool.v2", search_prompt_path)

    host = ollama_host or os.environ.get("OLLAMA_HOST") or "http://127.0.0.1:11434"
    region = (
        aws_region
        or os.environ.get("AWS_REGION")
        or os.environ.get("AWS_DEFAULT_REGION")
        or "us-east-1"
    )
    if llm_mode == "mock":
        manage_model_id = "mock/scripted_smoke"
        search_model_id = "mock/scripted_smoke"
    elif llm_mode == "bedrock":
        manage_model_id = f"bedrock/{manage_model}"
        search_model_id = f"bedrock/{search_model}"
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
                "prompt_id": "manage.memory_tool.v2",
                "prompt_digest": manage_digest,
                "adapter_id": None,
                "temperature": 0.0,
                "max_steps": 30,
            },
            "search": {
                "model_id": search_model_id,
                "prompt_id": "search.memory_tool.v2",
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
        "aws_region": region if llm_mode == "bedrock" else None,
        "eval_held_out": False,
    }
    writer.write_config(config)
    writer.write_chunks(suite.chunks, whitelist)

    build_verbatim(writer.verbatim_root(), suite.chunks, whitelist)

    if llm_mode == "mock":
        manage_llm: LLM = manage_llm_for_smoke()
        n_chunks = len(suite.chunks)
        for i, chunk in enumerate(suite.chunks, 1):
            if progress:
                _log(f"[amb] manage {i}/{n_chunks} chunk={chunk['id']}")
            visible = _filter_chunk(chunk, whitelist)
            steps = run_manage(
                manage_llm,
                writer.organized_root(),
                visible,
                manage_prompt,
                max_steps=30,
            )
            writer.write_trajectory(f"trajectories/manage/{chunk['id']}.jsonl", steps)

        search_jobs = [
            (q, shape)
            for q in suite.queries
            for shape in (q.get("shapes") or ["organized"])
        ]
        for j, (query, shape) in enumerate(search_jobs, 1):
            qid = query["id"]
            if progress:
                _log(f"[amb] search {j}/{len(search_jobs)} query={qid} shape={shape}")
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
            writer.write_trajectory(f"trajectories/search/{shape}/{qid}.jsonl", steps)
    elif llm_mode == "ollama":
        if manage_model in {"mock", ""} or search_model in {"mock", ""}:
            raise ValueError(
                "ollama mode requires --manage-model and --search-model "
                "(e.g. deepseek-r1:7b)"
            )
        probe_ollama(host, manage_model)
        if search_model != manage_model:
            probe_ollama(host, search_model)
        _run_live_manage_search(
            suite=suite,
            writer=writer,
            whitelist=whitelist,
            manage_llm=OllamaLLM(manage_model, base_url=host, verbose=verbose),
            search_llm=OllamaLLM(search_model, base_url=host, verbose=verbose),
            manage_prompt=manage_prompt,
            search_prompt=search_prompt,
        )
    elif llm_mode == "bedrock":
        if manage_model in {"mock", ""} or search_model in {"mock", ""}:
            raise ValueError(
                "bedrock mode requires --manage-model and --search-model "
                "(inference profile ids, e.g. us.anthropic.claude-haiku-4-5-20251001-v1:0)"
            )
        probe_bedrock(manage_model, region=region)
        if search_model != manage_model:
            probe_bedrock(search_model, region=region)
        _run_live_manage_search(
            suite=suite,
            writer=writer,
            whitelist=whitelist,
            manage_llm=BedrockLLM(
                manage_model, region=region, verbose=verbose
            ),
            search_llm=BedrockLLM(
                search_model, region=region, verbose=verbose
            ),
            manage_prompt=manage_prompt,
            search_prompt=search_prompt,
        )
    else:
        raise ValueError(f"unknown llm_mode {llm_mode}")

    if progress:
        _log("[amb] grading …")
    scorecard, diagnostics = grade(run_dir, suite)
    writer.write_scorecard(scorecard)
    writer.write_diagnostics(diagnostics)
    write_report(run_dir)
    writer.write_manifest()
    if progress:
        _log(f"[amb] finished in {time.perf_counter() - t_run:.1f}s → {run_dir}")
    return run_dir
