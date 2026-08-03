# Continuous Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `amb continuous` — a policy-gated loop with STATUS/INBOX, crystal lab, weighted memory pathways, scoring, and Ollama — so we can measure whether persistent memory improves long-horizon lab discovery before any real assistant mode.

**Architecture:** New package `src/amb/continuous/` owns the loop, policy, lab, graph, and graders. Reuse `amb.agents.llm` (MockLLM / OllamaLLM) and `amb.harness.store` path helpers. Episodic `run` first; daemon is a thin wrapper. Observability via STATUS.md + trajectory.jsonl; operator steering via INBOX.md.

**Tech Stack:** Python 3.11+, pytest, existing httpx Ollama client, stdlib only for graph/lab (no LangGraph).

**Spec:** `docs/superpowers/specs/2026-08-02-continuous-agent-design.md`

---

## File map

| Path | Responsibility |
|---|---|
| `src/amb/continuous/__init__.py` | Package marker / version note |
| `src/amb/continuous/layout.py` | Create/load run directory skeleton + defaults |
| `src/amb/continuous/inbox.py` | inject / consume / archive INBOX.md |
| `src/amb/continuous/status.py` | Rewrite STATUS.md from structured fields |
| `src/amb/continuous/policy.py` | Allow/deny tools + loop detection helpers |
| `src/amb/continuous/tools.py` | Dispatch view/create/str_replace/lab/python/web/done |
| `src/amb/continuous/lab/__init__.py` | World registry (`crystal`) |
| `src/amb/continuous/lab/crystal.py` | Deterministic crystal lab + hidden laws |
| `src/amb/continuous/memory_graph.py` | Weighted pathway graph + top-k retrieve |
| `src/amb/continuous/loop.py` | Orchestrator: one episode |
| `src/amb/continuous/score.py` | Discovery quiz + episode compare |
| `src/amb/continuous/daemon.py` | Phase-2 wrapper (stop file + sleep) |
| `src/amb/continuous/report.py` | Write REPORT.md from run artifacts |
| `prompts/continuous/agent.v1.md` | Standing system prompt |
| `src/amb/cli.py` | Wire `continuous` subcommands |
| `.gitignore` | Ignore `continuous_runs/` |
| `tests/test_continuous_*.py` | Unit + mock integration |

---

### Task 1: Run layout + gitignore

**Files:**
- Create: `src/amb/continuous/__init__.py`
- Create: `src/amb/continuous/layout.py`
- Create: `tests/test_continuous_layout.py`
- Modify: `.gitignore`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_continuous_layout.py
from pathlib import Path
from amb.continuous.layout import init_run_dir, DEFAULT_OBJECTIVE

def test_init_run_dir_creates_skeleton(tmp_path: Path):
    run = init_run_dir(tmp_path / "continuous_runs", run_id="t1", world="crystal", seed=0)
    assert (run / "STATUS.md").is_file()
    assert (run / "INBOX.md").is_file()
    assert (run / "core" / "objective.md").read_text(encoding="utf-8").startswith("Your continuing purpose")
    assert (run / "memory" / "observations.jsonl").is_file()
    assert (run / "memory" / "current_plan.json").is_file()
    assert (run / "memory" / "graph.json").is_file()
    assert (run / "memory" / "lessons.md").is_file()
    assert (run / "lab").is_dir()
    assert (run / "inbox_archive").is_dir()
    cfg = (run / "config.json").read_text(encoding="utf-8")
    assert '"world": "crystal"' in cfg
    assert DEFAULT_OBJECTIVE
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/mike/Documents/ResearchProjects/agent_memory_bench && .venv/bin/pytest tests/test_continuous_layout.py -v`  
Expected: FAIL (import / module missing)

- [ ] **Step 3: Implement layout**

```python
# src/amb/continuous/__init__.py
"""Continuous policy-gated agent loop (sandbox lab)."""

# src/amb/continuous/layout.py
from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone

DEFAULT_OBJECTIVE = (
    "Your continuing purpose is to understand and improve knowledge of this "
    "simulated laboratory. Maintain continuity through the provided memory, "
    "select a useful next experiment, and document the result. "
    "Do not pursue self-preservation or escape."
)

DEFAULT_PLAN = {"task": "Explore instruments", "step": 1, "steps_total": 5}

def init_run_dir(out_dir: Path, *, run_id: str, world: str, seed: int, model: str = "mock") -> Path:
    root = Path(out_dir) / run_id
    root.mkdir(parents=True, exist_ok=False)
    (root / "inbox_archive").mkdir()
    (root / "core").mkdir()
    (root / "memory").mkdir()
    (root / "lab").mkdir()
    (root / "core" / "objective.md").write_text(DEFAULT_OBJECTIVE + "\n", encoding="utf-8")
    (root / "INBOX.md").write_text("", encoding="utf-8")
    (root / "STATUS.md").write_text("# Status\n\n(not started)\n", encoding="utf-8")
    (root / "memory" / "observations.jsonl").write_text("", encoding="utf-8")
    (root / "memory" / "lessons.md").write_text("# Lessons\n", encoding="utf-8")
    (root / "memory" / "current_plan.json").write_text(
        json.dumps(DEFAULT_PLAN, indent=2) + "\n", encoding="utf-8"
    )
    (root / "memory" / "graph.json").write_text(
        json.dumps({"nodes": {}, "edges": {}}, indent=2) + "\n", encoding="utf-8"
    )
    (root / "trajectory.jsonl").write_text("", encoding="utf-8")
    (root / "actions.jsonl").write_text("", encoding="utf-8")
    cfg = {
        "run_id": run_id,
        "world": world,
        "seed": seed,
        "model": model,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "web_allowlist": [],
        "max_steps": None,
    }
    (root / "config.json").write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    return root
```

Add `continuous_runs/` to `.gitignore`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_continuous_layout.py -v`  
Expected: PASS

- [ ] **Step 5: Commit** (if user requested commits)

```bash
git add src/amb/continuous .gitignore tests/test_continuous_layout.py
git commit -m "$(cat <<'EOF'
feat(continuous): add run directory layout skeleton

EOF
)"
```

---

### Task 2: Inbox + STATUS writers

**Files:**
- Create: `src/amb/continuous/inbox.py`
- Create: `src/amb/continuous/status.py`
- Create: `tests/test_continuous_inbox_status.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_continuous_inbox_status.py
from pathlib import Path
from amb.continuous.layout import init_run_dir
from amb.continuous.inbox import inject, consume_inbox
from amb.continuous.status import write_status

def test_inject_and_consume(tmp_path: Path):
    run = init_run_dir(tmp_path, run_id="i1", world="crystal", seed=0)
    inject(run, "Focus on humidity.")
    assert "humidity" in (run / "INBOX.md").read_text(encoding="utf-8")
    text = consume_inbox(run)
    assert "humidity" in text
    assert (run / "INBOX.md").read_text(encoding="utf-8").strip() == ""
    archived = list((run / "inbox_archive").glob("*.md"))
    assert len(archived) == 1

def test_write_status(tmp_path: Path):
    run = init_run_dir(tmp_path, run_id="s1", world="crystal", seed=0)
    write_status(
        run,
        step=3,
        max_steps=10,
        last_tool="lab_act",
        last_ok=True,
        last_summary="set temp=40",
    )
    body = (run / "STATUS.md").read_text(encoding="utf-8")
    assert "Explore instruments" in body  # from default plan
    assert "lab_act" in body
    assert "3/10" in body
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `.venv/bin/pytest tests/test_continuous_inbox_status.py -v`

- [ ] **Step 3: Implement**

```python
# src/amb/continuous/inbox.py
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path

def inject(run_dir: Path, text: str) -> None:
    path = Path(run_dir) / "INBOX.md"
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    chunk = text.strip()
    if not chunk:
        return
    sep = "\n" if existing and not existing.endswith("\n") else ""
    path.write_text(existing + sep + chunk + "\n", encoding="utf-8")

def consume_inbox(run_dir: Path) -> str:
    path = Path(run_dir) / "INBOX.md"
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    stripped = text.strip()
    if not stripped:
        return ""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    arch = Path(run_dir) / "inbox_archive" / f"{ts}.md"
    arch.write_text(stripped + "\n", encoding="utf-8")
    path.write_text("", encoding="utf-8")
    return stripped

# src/amb/continuous/status.py
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
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `.venv/bin/pytest tests/test_continuous_inbox_status.py -v`

- [ ] **Step 5: Commit** (if requested)

```bash
git add src/amb/continuous/inbox.py src/amb/continuous/status.py tests/test_continuous_inbox_status.py
git commit -m "$(cat <<'EOF'
feat(continuous): add INBOX inject/consume and STATUS writer

EOF
)"
```

---

### Task 3: Policy gate

**Files:**
- Create: `src/amb/continuous/policy.py`
- Create: `tests/test_continuous_policy.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_continuous_policy.py
from amb.continuous.policy import Policy, PolicyDecision

def test_allows_known_tools():
    p = Policy(web_allowlist=[])
    d = p.check("lab_sense", {})
    assert d.allowed
    d2 = p.check("view", {"path": "memory/lessons.md"})
    assert d2.allowed

def test_denies_unknown_and_shellish():
    p = Policy(web_allowlist=[])
    assert not p.check("bash", {"cmd": "ls"}).allowed
    assert not p.check("run_bounded_python", {"code": "import os; os.system('x')"}).allowed

def test_web_denied_when_allowlist_empty():
    p = Policy(web_allowlist=[])
    d = p.check("fetch_allowlisted_page", {"url": "https://example.com"})
    assert not d.allowed

def test_web_allowed_when_host_listed():
    p = Policy(web_allowlist=["example.com"])
    d = p.check("fetch_allowlisted_page", {"url": "https://example.com/a"})
    assert d.allowed

def test_path_escape_denied():
    p = Policy(web_allowlist=[])
    assert not p.check("view", {"path": "../secrets"}).allowed
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement policy**

```python
# src/amb/continuous/policy.py
from __future__ import annotations
from dataclasses import dataclass
from urllib.parse import urlparse
from amb.harness.store import canonicalize_rel_path

ALLOWED_TOOLS = frozenset({
    "lab_sense", "lab_act",
    "view", "create", "str_replace",
    "run_bounded_python",
    "search_allowlisted_web", "fetch_allowlisted_page",
    "done",
})

_FORBIDDEN_PY = ("import os", "import subprocess", "from os", "__import__", "socket", "subprocess")

@dataclass
class PolicyDecision:
    allowed: bool
    reason: str = ""

class Policy:
    def __init__(self, *, web_allowlist: list[str]) -> None:
        self.web_allowlist = [h.lower() for h in web_allowlist]

    def check(self, tool: str, arguments: dict) -> PolicyDecision:
        if tool not in ALLOWED_TOOLS:
            return PolicyDecision(False, f"tool not allowed: {tool}")
        if tool in ("view", "create", "str_replace"):
            path = arguments.get("path") or arguments.get("file_path") or ""
            canon, err = canonicalize_rel_path(path)
            if err or canon is None:
                return PolicyDecision(False, err or "bad path")
            if canon.startswith("inbox_archive/") is False and ".." in str(path):
                return PolicyDecision(False, "path escape")
        if tool == "run_bounded_python":
            code = str(arguments.get("code") or "")
            low = code.lower()
            for bad in _FORBIDDEN_PY:
                if bad in low:
                    return PolicyDecision(False, f"python blocked pattern: {bad}")
        if tool in ("search_allowlisted_web", "fetch_allowlisted_page"):
            if not self.web_allowlist:
                return PolicyDecision(False, "web allowlist empty")
            if tool == "fetch_allowlisted_page":
                url = str(arguments.get("url") or "")
                host = (urlparse(url).hostname or "").lower()
                if host not in self.web_allowlist:
                    return PolicyDecision(False, f"host not allowlisted: {host}")
        return PolicyDecision(True, "")
```

Note: keep path checks consistent with `canonicalize_rel_path` (it already rejects `..`).

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit** (if requested)

---

### Task 4: Crystal lab world

**Files:**
- Create: `src/amb/continuous/lab/__init__.py`
- Create: `src/amb/continuous/lab/crystal.py`
- Create: `tests/test_continuous_lab_crystal.py`

**Hidden laws (encode in code only):**  
`growth = max(0, 1.0 - abs(temp - 37) / 20) * (0.5 + 0.5 * (1 if 40 <= humidity <= 60 else 0.2))` plus seeded Gaussian noise. Ideal: temp≈37, humidity 40–60.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_continuous_lab_crystal.py
from pathlib import Path
from amb.continuous.lab.crystal import CrystalLab

def test_crystal_deterministic(tmp_path: Path):
    a = CrystalLab(tmp_path / "a", seed=7)
    b = CrystalLab(tmp_path / "b", seed=7)
    a.act({"temperature": 37, "humidity": 50})
    b.act({"temperature": 37, "humidity": 50})
    assert a.sense()["growth"] == b.sense()["growth"]

def test_near_ideal_beats_bad(tmp_path: Path):
    good = CrystalLab(tmp_path / "g", seed=1)
    bad = CrystalLab(tmp_path / "x", seed=1)
    good.act({"temperature": 37, "humidity": 50})
    bad.act({"temperature": 10, "humidity": 10})
    assert good.sense()["growth"] > bad.sense()["growth"]

def test_hidden_laws_not_in_public_state(tmp_path: Path):
    lab = CrystalLab(tmp_path / "l", seed=0)
    sense = lab.sense()
    assert "law" not in sense
    assert "ideal" not in str(sense).lower()
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement**

```python
# src/amb/continuous/lab/crystal.py
from __future__ import annotations
import json
import math
import random
from pathlib import Path

# Hidden — do not expose via sense()
_IDEAL_TEMP = 37.0
_HUM_LO, _HUM_HI = 40.0, 60.0

class CrystalLab:
    def __init__(self, lab_dir: Path, *, seed: int) -> None:
        self.lab_dir = Path(lab_dir)
        self.lab_dir.mkdir(parents=True, exist_ok=True)
        self.rng = random.Random(seed)
        self.state_path = self.lab_dir / "state.json"
        if not self.state_path.exists():
            self._save({"temperature": 25.0, "humidity": 30.0, "growth": 0.0, "trials": 0})

    def _load(self) -> dict:
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def _save(self, state: dict) -> None:
        self.state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    def _true_growth(self, temp: float, humidity: float) -> float:
        temp_term = max(0.0, 1.0 - abs(temp - _IDEAL_TEMP) / 20.0)
        hum_term = 1.0 if _HUM_LO <= humidity <= _HUM_HI else 0.2
        return max(0.0, temp_term * (0.5 + 0.5 * hum_term))

    def act(self, args: dict) -> dict:
        st = self._load()
        if "temperature" in args:
            st["temperature"] = float(args["temperature"])
        if "humidity" in args:
            st["humidity"] = float(args["humidity"])
        true = self._true_growth(st["temperature"], st["humidity"])
        noise = self.rng.gauss(0, 0.05)
        st["growth"] = max(0.0, min(1.5, true + noise))
        st["trials"] = int(st.get("trials", 0)) + 1
        self._save(st)
        return {"ok": True, "informative": True, "state": self.sense()}

    def sense(self) -> dict:
        st = self._load()
        return {
            "temperature": st["temperature"],
            "humidity": st["humidity"],
            "growth": st["growth"],
            "trials": st["trials"],
        }

# src/amb/continuous/lab/__init__.py
from amb.continuous.lab.crystal import CrystalLab

def load_world(world: str, lab_dir, *, seed: int):
    if world == "crystal":
        return CrystalLab(lab_dir, seed=seed)
    raise ValueError(f"unknown world: {world}")
```

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit** (if requested)

---

### Task 5: Weighted memory graph

**Files:**
- Create: `src/amb/continuous/memory_graph.py`
- Create: `tests/test_continuous_memory_graph.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_continuous_memory_graph.py
from pathlib import Path
from amb.continuous.memory_graph import MemoryGraph

def test_coaccess_strengthens_and_retrieve(tmp_path: Path):
    g = MemoryGraph(tmp_path / "graph.json")
    g.observe(["temperature", "growth"], observation_id="o1", success=False)
    g.observe(["temperature", "growth"], observation_id="o2", success=True)
    pack = g.retrieve(query_tokens=["temperature"], top_k=3)
    assert pack
    assert pack[0]["weight"] > 0
    # success boost => edge weight higher than single access
    data = g.load()
    edge = data["edges"]["growth|temperature"]  # canonical key sorted
    assert edge["weight"] >= 2.0  # 1 + 1 + success boost >= 2
```

Exact edge key format: `"|".join(sorted([a, b]))`. Access bump `+1.0`, success boost `+0.5` on edges touched that step.

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement**

```python
# src/amb/continuous/memory_graph.py
from __future__ import annotations
import json
from pathlib import Path

ACCESS_BUMP = 1.0
SUCCESS_BOOST = 0.5

def _norm(label: str) -> str:
    return " ".join(label.strip().lower().split())

def _edge_key(a: str, b: str) -> str:
    x, y = sorted([_norm(a), _norm(b)])
    return f"{x}|{y}"

class MemoryGraph:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        if not self.path.exists():
            self._save({"nodes": {}, "edges": {}})

    def load(self) -> dict:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _save(self, data: dict) -> None:
        self.path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    def observe(self, labels: list[str], *, observation_id: str, success: bool) -> None:
        labels = [_norm(x) for x in labels if _norm(x)]
        data = self.load()
        nodes, edges = data["nodes"], data["edges"]
        for lab in labels:
            n = nodes.setdefault(lab, {"visits": 0, "observations": []})
            n["visits"] += 1
            if observation_id not in n["observations"]:
                n["observations"].append(observation_id)
        for i, a in enumerate(labels):
            for b in labels[i + 1 :]:
                k = _edge_key(a, b)
                e = edges.setdefault(k, {"weight": 0.0, "count": 0})
                e["weight"] += ACCESS_BUMP
                e["count"] += 1
                if success:
                    e["weight"] += SUCCESS_BOOST
        self._save(data)

    def retrieve(self, *, query_tokens: list[str], top_k: int = 5) -> list[dict]:
        q = {_norm(t) for t in query_tokens if _norm(t)}
        data = self.load()
        scored: list[dict] = []
        for k, e in data["edges"].items():
            a, b = k.split("|", 1)
            overlap = (1 if a in q else 0) + (1 if b in q else 0)
            if overlap == 0 and q:
                continue
            scored.append({"edge": k, "a": a, "b": b, "weight": e["weight"] * (1 + overlap)})
        scored.sort(key=lambda x: x["weight"], reverse=True)
        return scored[:top_k]
```

- [ ] **Step 4: Run — expect PASS** (adjust assert if key order differs — use `_edge_key`)

- [ ] **Step 5: Commit** (if requested)

---

### Task 6: Tool dispatcher (workspace + lab; stub python/web)

**Files:**
- Create: `src/amb/continuous/tools.py`
- Create: `tests/test_continuous_tools.py`

- [ ] **Step 1: Write failing tests** for `view`/`create` inside run root, `lab_sense`/`lab_act`, `done`; python forbidden import already denied by policy (tools can still implement safe subset later).

```python
def test_workspace_create_view(tmp_path):
    run = init_run_dir(tmp_path, run_id="w1", world="crystal", seed=0)
    world = load_world("crystal", run / "lab", seed=0)
    rt = ToolRuntime(run, world=world, policy=Policy(web_allowlist=[]))
    r = rt.execute("create", {"path": "memory/notes.md", "file_text": "hello"})
    assert r["ok"]
    r2 = rt.execute("view", {"path": "memory/notes.md"})
    assert r2["ok"] and "hello" in r2["content"]

def test_lab_roundtrip(tmp_path):
    run = init_run_dir(tmp_path, run_id="w2", world="crystal", seed=0)
    world = load_world("crystal", run / "lab", seed=0)
    rt = ToolRuntime(run, world=world, policy=Policy(web_allowlist=[]))
    assert rt.execute("lab_act", {"temperature": 37, "humidity": 50})["ok"]
    sense = rt.execute("lab_sense", {})
    assert sense["ok"] and "growth" in sense["result"]
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement `ToolRuntime`**

- Call `policy.check` first; on deny return `{"ok": False, "error_code": "policy_denied", "error": reason}`.
- Workspace: use `canonicalize_rel_path` + `resolve_in_store(run_dir, …)` (treat entire run dir as store root).
- `lab_sense` / `lab_act` delegate to world.
- `run_bounded_python`: for this task, return `{"ok": False, "error_code": "not_implemented"}` OR implement minimal `exec` with empty builtins except `math` — prefer minimal safe exec in Task 10; stub here with clear error is OK only if Task 10 immediately follows. **Implement minimal safe exec in Task 10; here return not_implemented for python/web.**
- `done`: `{"ok": True, "done": True, "summary": ...}`.

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit** (if requested)

---

### Task 7: Loop orchestrator + mock integration

**Files:**
- Create: `src/amb/continuous/loop.py`
- Create: `src/amb/continuous/report.py`
- Create: `prompts/continuous/agent.v1.md`
- Create: `tests/test_continuous_loop_mock.py`

- [ ] **Step 1: Write failing integration test**

Scripted MockLLM turns: `lab_act` → `create` journal note claiming temp preference → `done`.

```python
def test_mock_episode_writes_artifacts(tmp_path):
    from amb.agents.llm import MockLLM, ScriptedTurn
    turns = [
        ScriptedTurn({"type": "tool_call", "tool": "lab_act", "arguments": {"temperature": 37, "humidity": 50}}),
        ScriptedTurn({"type": "tool_call", "tool": "create", "arguments": {"path": "memory/lessons.md", "file_text": "# Lessons\nPrefer temp near 37.\n"}}),
        ScriptedTurn({"type": "tool_call", "tool": "done", "arguments": {"summary": "trial done"}}),
    ]
    # Note: create may need str_replace if lessons.md exists — use str_replace or create notes.md
    run_dir = run_episode(
        out_dir=tmp_path,
        world="crystal",
        llm=MockLLM(turns),
        max_steps=10,
        seed=0,
        model_id="mock",
    )
    assert (run_dir / "STATUS.md").stat().st_size > 20
    assert (run_dir / "trajectory.jsonl").read_text(encoding="utf-8").strip()
    assert (run_dir / "actions.jsonl").read_text(encoding="utf-8").strip()
    assert (run_dir / "memory" / "graph.json").read_text(encoding="utf-8")
    assert "Stop" in (run_dir / "REPORT.md").read_text(encoding="utf-8") or "done" in (run_dir / "REPORT.md").read_text(encoding="utf-8").lower()
```

Fix scripted paths to match ToolRuntime (e.g. create `memory/notes.md` then leave lessons).

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement `run_episode`**

Pseudo-flow each step:

1. `consume_inbox` → optional operator message  
2. Build messages: system prompt + objective + STATUS snapshot + graph retrieve pack + recent observations tail  
3. `llm.complete(...)`  
4. Log trajectory  
5. If not tool_call → protocol failure counter  
6. `policy` + `tools.execute`  
7. Append observations.jsonl; `memory_graph.observe` with labels from tool/args/result keys; `success=result.get("informative")`  
8. `write_status`  
9. Stop on `done`, max_steps, consecutive failures ≥3, or repeated identical action ≥3  

Verbose print each step to stdout.

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit** (if requested)

---

### Task 8: CLI — `run` + `inject`

**Files:**
- Modify: `src/amb/cli.py`
- Create: `tests/test_continuous_cli.py`

- [ ] **Step 1: Failing test** using `main([...])` or argparse helper:

```python
def test_cli_inject(tmp_path, capsys):
    run = init_run_dir(tmp_path, run_id="c1", world="crystal", seed=0)
    from amb.cli import main
    main(["continuous", "inject", "--run", str(run), "Try humidity next"])
    assert "humidity" in (run / "INBOX.md").read_text(encoding="utf-8")
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Wire subparser**

```text
amb continuous run --world crystal --llm mock|ollama --model TAG --max-steps N --seed S --out continuous_runs
amb continuous inject --run DIR TEXT
```

For `--llm ollama`, construct `OllamaLLM` like suite runner does.

- [ ] **Step 4: Run pytest for CLI + full continuous tests**

- [ ] **Step 5: Commit** (if requested)

---

### Task 9: Scoring — discovery + episode compare

**Files:**
- Create: `src/amb/continuous/score.py`
- Create: `tests/test_continuous_score.py`

**Quiz gold (crystal):** agent journal/lessons/notes text should mention ideal temperature near 37 (±2) and humidity band overlapping 40–60.

```python
CRYSTAL_CHECKS = [
    {"id": "temp_near_37", "pattern": r"\b(3[5-9]|37)\b"},
    {"id": "humidity_band", "pattern": r"humid|\b4[0-9]\b|\b5[0-9]\b|\b60\b"},
]

def score_run(run_dir: Path) -> dict:
    # scan memory/*.md + observations for patterns
    # return scorecard with n_passed/n_total

def compare_episodes(early: Path, late: Path) -> dict:
    # late pass_rate >= early => improved True
```

- [ ] **Step 1: Failing tests** with fixture text files that should pass/fail checks

- [ ] **Step 2–4: Implement + pass + CLI `amb continuous score --run DIR` and `--compare A B`**

- [ ] **Step 5: Commit** (if requested)

---

### Task 10: Bounded Python + allowlisted web

**Files:**
- Modify: `src/amb/continuous/tools.py`
- Create: `tests/test_continuous_python_web.py`

- [ ] **Step 1: Tests**

```python
def test_bounded_python_math(tmp_path):
    # execute code "result = 2+2" with timeout; expect result 4 in output
def test_web_fetch_blocked_empty_allowlist(tmp_path):
    # policy deny
def test_web_fetch_allowlisted(tmp_path, httpx_mock_or_local):
    # optional: use httpx mock; or skip network and unit-test allowlist branch only
```

Implement `run_bounded_python` with `exec` in `{"__builtins__": {"abs": abs, "min": min, "max": max, "range": range, "len": len, "float": float, "int": int, "print": print}, "math": math}` capturing stdout; `signal`/thread timeout 2s; output cap 8KB.

Web: if allowlisted, `httpx.get` with timeout 5s size cap; else policy already denies.

- [ ] **Step 2–4: Implement + pass**

- [ ] **Step 5: Commit** (if requested)

---

### Task 11: Daemon wrapper + observer stub

**Files:**
- Create: `src/amb/continuous/daemon.py`
- Modify: `src/amb/cli.py`
- Create: `tests/test_continuous_daemon.py`

- [ ] **Step 1: Test** that daemon respects `STOP` file after one iteration when max_steps=1 and stop file pre-created mid-loop — simpler: `daemon_should_stop(run_dir)` true when `STOP` exists.

```python
def test_stop_file(tmp_path):
    run = init_run_dir(tmp_path, run_id="d1", world="crystal", seed=0)
    assert not should_stop(run)
    (run / "STOP").write_text("1\n", encoding="utf-8")
    assert should_stop(run)
```

CLI: `amb continuous daemon ...` runs episodes in a loop with `--idle-seconds`, exits when STOP present.  
CLI: `--observer` flag accepted and stored in config but no-op (prints once: observer not enabled).

- [ ] **Step 2–4: Implement + pass**

- [ ] **Step 5: Commit** (if requested)

---

### Task 12: Guide doc + smoke instructions

**Files:**
- Create: `docs/guides/continuous-agent.md`
- Modify: `docs/guides/desktop-rtx3070.md` (short pointer)

Document:

```bash
amb continuous run --world crystal --llm mock --max-steps 20 --out continuous_runs
# watch:
#   continuous_runs/<id>/STATUS.md
#   amb continuous inject --run continuous_runs/<id> "Focus on humidity"
amb continuous score --run continuous_runs/<id>
# live:
amb continuous run --world crystal --llm ollama --model deepseek-r1:7b --max-steps 50 --out continuous_runs -v
```

- [ ] **Step 1: Write guide**
- [ ] **Step 2: Run full continuous test suite**

Run: `.venv/bin/pytest tests/test_continuous_*.py -v`  
Expected: all PASS

- [ ] **Step 3: Commit** (if requested)

---

## Spec coverage checklist

| Spec item | Task |
|---|---|
| Run layout / objective / memory files | 1 |
| STATUS + INBOX inject | 2, 8 |
| Policy allowlist / path / web | 3, 10 |
| Crystal lab hidden laws | 4 |
| Weighted graph access + success boost | 5, 7 |
| Tools + done | 6, 10 |
| Loop + trajectory + verbose | 7 |
| CLI run/inject | 8 |
| Discovery + improvement scoring | 9 |
| Bounded python + allowlisted web | 10 |
| Daemon + observer stub | 11 |
| Operator docs / 3070 pointer | 12 |
| No self-preservation objective | 1 (DEFAULT_OBJECTIVE) |
| smoke/core untouched | (no suite file edits) |

## Self-review notes

- No TBD placeholders left in tasks; python/web deferred only from Task 6 stub → Task 10 implementation (explicit).
- Edge key format fixed as `"|".join(sorted(...))` in Task 5.
- `MockLLM` / `ScriptedTurn` already exist in `amb.agents.llm`.
- Commits are optional pending user request (repo rule).
- **Post-v1 (not in these 12 tasks):** TME-lite prompt packing → MRAgent-lite graph walk → editable prompt graphs; defer GoT/SAGE. See spec §11b.

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-02-continuous-agent.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks  
2. **Inline Execution** — execute tasks in this session with checkpoints  

Which approach?
