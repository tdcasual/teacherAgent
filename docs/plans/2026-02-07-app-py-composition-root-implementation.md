# App.py Composition Root Migration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Migrate all remaining business logic out of `/Users/lvxiaoer/Documents/New project/services/api/app.py` so it only contains routing, dependency assembly, request/response mapping, and HTTP error mapping, with final line count `<= 5000`.

**Architecture:** Use a strangler pattern by domain: extract callable service modules first, then replace `app.py` function bodies with thin delegations, then delete duplicated in-app logic. Keep API contracts stable by preserving route signatures and JSON shapes while moving behavior into explicit deps dataclasses and service entrypoints.

**Tech Stack:** Python 3.9, FastAPI, `unittest` (`python3 -m unittest`), dataclass-based dependency injection pattern (`*_api_service.py`), existing service modules under `services/api/`.

---

## Preconditions

- Execute inside worktree: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root`.
- Use `@superpowers:test-driven-development` for every task.
- If any test fails unexpectedly, apply `@superpowers:systematic-debugging` before changing logic.
- Before any completion claim, run `@superpowers:verification-before-completion`.
- Commit after each task (small reversible commits).

---

### Task 1: Extract Chat Runtime and Agent Services

**Files:**
- Create: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/services/api/chat_preflight.py`
- Create: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/services/api/chat_runtime_service.py`
- Create: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/services/api/agent_service.py`
- Create: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/tests/test_chat_runtime_service.py`
- Create: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/tests/test_agent_service.py`
- Modify: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/services/api/app.py:7251`

**Step 1: Write the failing tests**

```python
from services.api.chat_runtime_service import call_llm_runtime
from services.api.agent_service import run_agent_runtime
```

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_chat_runtime_service tests.test_agent_service -v`  
Expected: `ModuleNotFoundError` for new modules.

**Step 3: Write minimal implementation**

```python
# app.py delegation target
from .chat_runtime_service import call_llm_runtime as _call_llm_runtime_impl
from .agent_service import run_agent_runtime as _run_agent_runtime_impl

def call_llm(...):
    return _call_llm_runtime_impl(..., deps=_chat_runtime_deps())

def run_agent(...):
    return _run_agent_runtime_impl(..., deps=_agent_runtime_deps())
```

**Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_chat_runtime_service tests.test_agent_service tests.test_chat_job_flow -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add services/api/chat_preflight.py services/api/chat_runtime_service.py services/api/agent_service.py services/api/app.py tests/test_chat_runtime_service.py tests/test_agent_service.py
git commit -m "refactor: extract chat runtime and agent services"
```

---

### Task 2: Extract Chat Start/Worker/Status/Job Orchestration

**Files:**
- Create: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/services/api/chat_start_service.py`
- Create: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/services/api/chat_worker_service.py`
- Create: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/services/api/chat_status_service.py`
- Create: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/services/api/chat_job_service.py`
- Create: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/tests/test_chat_worker_service.py`
- Create: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/tests/test_chat_status_flow.py`
- Modify: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/services/api/app.py:605`
- Modify: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/services/api/app.py:8136`

**Step 1: Write the failing test**

```python
from services.api.chat_start_service import start_chat_orchestration
from services.api.chat_worker_service import process_chat_job
from services.api.chat_status_service import get_chat_status
```

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_chat_start_flow tests.test_chat_worker_service tests.test_chat_status_flow -v`  
Expected: `ModuleNotFoundError`.

**Step 3: Write minimal implementation**

```python
@app.post("/chat/start")
async def chat_start(req: ChatStartRequest):
    return _start_chat_api_impl(req, deps=_chat_api_deps())

def start_chat_worker() -> None:
    _start_chat_worker_impl(deps=_chat_worker_deps())
```

**Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_chat_start_flow tests.test_chat_job_flow tests.test_chat_worker_service tests.test_chat_status_flow -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add services/api/chat_start_service.py services/api/chat_worker_service.py services/api/chat_status_service.py services/api/chat_job_service.py services/api/app.py tests/test_chat_start_flow.py tests/test_chat_worker_service.py tests/test_chat_status_flow.py
git commit -m "refactor: extract chat orchestration services"
```

---

### Task 3: Extract Teacher Workspace/Context/Session Services

**Files:**
- Create: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/services/api/teacher_workspace_service.py`
- Create: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/services/api/teacher_context_service.py`
- Create: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/services/api/teacher_session_compaction_service.py`
- Create: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/tests/test_teacher_workspace_service.py`
- Create: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/tests/test_teacher_context_service.py`
- Create: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/tests/test_teacher_session_compaction_service.py`
- Modify: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/services/api/app.py:1161`

**Step 1: Write the failing test**

```python
from services.api.teacher_workspace_service import ensure_teacher_workspace
from services.api.teacher_context_service import build_teacher_context
```

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_teacher_workspace_service tests.test_teacher_context_service tests.test_teacher_session_compaction_service -v`  
Expected: `ModuleNotFoundError`.

**Step 3: Write minimal implementation**

```python
from .teacher_workspace_service import ensure_teacher_workspace as _ensure_teacher_workspace_impl

def ensure_teacher_workspace(teacher_id: str) -> Path:
    return _ensure_teacher_workspace_impl(teacher_id, deps=_teacher_workspace_deps())
```

**Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_teacher_workspace_service tests.test_teacher_context_service tests.test_teacher_session_compaction_service tests.test_chat_job_flow -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add services/api/teacher_workspace_service.py services/api/teacher_context_service.py services/api/teacher_session_compaction_service.py services/api/app.py tests/test_teacher_workspace_service.py tests/test_teacher_context_service.py tests/test_teacher_session_compaction_service.py
git commit -m "refactor: extract teacher workspace and context services"
```

---

### Task 4: Extract Teacher Memory Data and Scoring Services

**Files:**
- Create: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/services/api/teacher_memory_proposal_store.py`
- Create: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/services/api/teacher_memory_time_service.py`
- Create: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/services/api/teacher_memory_scoring_service.py`
- Create: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/services/api/teacher_memory_dedupe_service.py`
- Create: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/services/api/teacher_memory_conflict_service.py`
- Create: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/services/api/teacher_memory_search_service.py`
- Create: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/services/api/teacher_memory_records_service.py`
- Create: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/services/api/teacher_memory_infer_service.py`
- Create: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/tests/test_teacher_memory_scoring_service.py`
- Create: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/tests/test_teacher_memory_search_service.py`
- Create: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/tests/test_teacher_memory_records_service.py`
- Modify: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/services/api/app.py:1300`

**Step 1: Write the failing test**

```python
from services.api.teacher_memory_scoring_service import score_proposal
from services.api.teacher_memory_search_service import teacher_memory_search
```

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_teacher_memory_scoring_service tests.test_teacher_memory_search_service tests.test_teacher_memory_records_service -v`  
Expected: `ModuleNotFoundError`.

**Step 3: Write minimal implementation**

```python
def teacher_memory_search(teacher_id: str, query: str, limit: int = 5) -> Dict[str, Any]:
    return _teacher_memory_search_impl(
        teacher_id=teacher_id,
        query=query,
        limit=limit,
        deps=_teacher_memory_search_deps(),
    )
```

**Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_teacher_memory_scoring_service tests.test_teacher_memory_search_service tests.test_teacher_memory_records_service tests.test_teacher_memory_api_service -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add services/api/teacher_memory_proposal_store.py services/api/teacher_memory_time_service.py services/api/teacher_memory_scoring_service.py services/api/teacher_memory_dedupe_service.py services/api/teacher_memory_conflict_service.py services/api/teacher_memory_search_service.py services/api/teacher_memory_records_service.py services/api/teacher_memory_infer_service.py services/api/app.py tests/test_teacher_memory_scoring_service.py tests/test_teacher_memory_search_service.py tests/test_teacher_memory_records_service.py
git commit -m "refactor: extract teacher memory data and scoring services"
```

---

### Task 5: Extract Teacher Memory Orchestration and API Delegates

**Files:**
- Create: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/services/api/teacher_memory_auto_service.py`
- Create: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/services/api/teacher_memory_telemetry_service.py`
- Create: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/services/api/teacher_memory_session_index_service.py`
- Create: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/services/api/teacher_memory_apply_service.py`
- Create: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/services/api/teacher_memory_propose_service.py`
- Create: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/services/api/teacher_memory_insights_service.py`
- Create: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/tests/test_teacher_memory_apply_service.py`
- Create: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/tests/test_teacher_memory_propose_service.py`
- Create: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/tests/test_teacher_memory_insights_service.py`
- Create: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/tests/test_teacher_memory_auto_service.py`
- Modify: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/services/api/app.py:1585`
- Modify: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/services/api/app.py:8655`

**Step 1: Write the failing test**

```python
from services.api.teacher_memory_propose_service import teacher_memory_propose
from services.api.teacher_memory_apply_service import teacher_memory_apply
from services.api.teacher_memory_insights_service import teacher_memory_insights
```

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_teacher_memory_propose_service tests.test_teacher_memory_apply_service tests.test_teacher_memory_insights_service tests.test_teacher_memory_auto_service -v`  
Expected: `ModuleNotFoundError`.

**Step 3: Write minimal implementation**

```python
@app.get("/teacher/memory/proposals")
async def teacher_memory_proposals(...):
    return _list_teacher_memory_proposals_api_impl(..., deps=_teacher_memory_api_deps())

def teacher_memory_apply(...):
    return _teacher_memory_apply_impl(..., deps=_teacher_memory_apply_deps())
```

**Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_teacher_memory_api_service tests.test_teacher_memory_propose_service tests.test_teacher_memory_apply_service tests.test_teacher_memory_insights_service tests.test_teacher_memory_auto_service -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add services/api/teacher_memory_auto_service.py services/api/teacher_memory_telemetry_service.py services/api/teacher_memory_session_index_service.py services/api/teacher_memory_apply_service.py services/api/teacher_memory_propose_service.py services/api/teacher_memory_insights_service.py services/api/app.py tests/test_teacher_memory_apply_service.py tests/test_teacher_memory_propose_service.py tests/test_teacher_memory_insights_service.py tests/test_teacher_memory_auto_service.py
git commit -m "refactor: extract teacher memory orchestration services"
```

---

### Task 6: Extract Lesson Core Tool and Chart Agent Run

**Files:**
- Create: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/services/api/lesson_core_tool_service.py`
- Create: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/services/api/chart_agent_run_service.py`
- Create: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/tests/test_lesson_core_tool_service.py`
- Create: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/tests/test_chart_agent_run_service.py`
- Modify: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/services/api/app.py:6926`
- Modify: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/services/api/app.py:7121`

**Step 1: Write the failing test**

```python
from services.api.lesson_core_tool_service import lesson_capture
from services.api.chart_agent_run_service import chart_agent_run
```

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_lesson_core_tool_service tests.test_chart_agent_run_service -v`  
Expected: `ModuleNotFoundError`.

**Step 3: Write minimal implementation**

```python
def chart_agent_run(args: Dict[str, Any]) -> Dict[str, Any]:
    return _chart_agent_run_impl(args, deps=_chart_agent_run_deps())

def lesson_capture(args: Dict[str, Any]) -> Dict[str, Any]:
    return _lesson_capture_impl(args, deps=_lesson_core_tool_deps())
```

**Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_lesson_core_tool_service tests.test_chart_agent_run_service tests.test_tool_dispatch_service -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add services/api/lesson_core_tool_service.py services/api/chart_agent_run_service.py services/api/app.py tests/test_lesson_core_tool_service.py tests/test_chart_agent_run_service.py
git commit -m "refactor: extract lesson core and chart agent services"
```

---

### Task 7: Delete In-App Duplicate Logic and Enforce Composition Root Guardrails

**Files:**
- Modify: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/services/api/app.py`
- Modify: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/tests/test_app_modularization_guardrails.py`
- Create: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/tests/test_app_line_budget.py`
- Create: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/tests/test_app_composition_root_structure.py`

**Step 1: Write the failing tests**

```python
from pathlib import Path

def test_app_py_line_budget():
    count = len(Path("services/api/app.py").read_text(encoding="utf-8").splitlines())
    assert count <= 5000
```

```python
def test_no_business_impl_symbols_left():
    import services.api.app as app_mod
    for name in ("run_agent", "call_llm", "process_chat_job", "teacher_memory_search"):
        assert not hasattr(app_mod, f"_legacy_{name}")
```

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_app_line_budget tests.test_app_composition_root_structure -v`  
Expected: FAIL (line count too high / structure assertions fail).

**Step 3: Write minimal implementation**

```python
# app.py keeps only route handlers + deps factories + adapters
# remove duplicated business function bodies once all call sites delegate to services
```

**Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_app_line_budget tests.test_app_composition_root_structure tests.test_app_modularization_guardrails -v`  
Expected: PASS (`app.py <= 5000`).

**Step 5: Commit**

```bash
git add services/api/app.py tests/test_app_line_budget.py tests/test_app_composition_root_structure.py tests/test_app_modularization_guardrails.py
git commit -m "refactor: enforce app.py composition-root boundaries"
```

---

### Task 8: Final Verification and Documentation

**Files:**
- Modify: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/README.md`
- Modify: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/docs/http_api.md`
- Create: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/docs/app_composition_root_map.md`
- Create: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/tests/test_docs_composition_root.py`

**Step 1: Write the failing docs consistency test**

```python
from pathlib import Path

def test_docs_include_composition_root_map():
    text = Path("docs/app_composition_root_map.md").read_text(encoding="utf-8")
    assert "services/api/app.py" in text
    assert "composition root" in text.lower()
```

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_docs_composition_root -v`  
Expected: FAIL (`ModuleNotFoundError` or file missing).

**Step 3: Write minimal implementation**

```markdown
# App Composition Root Map
- routes -> api_service delegates
- api_service -> domain service modules
- app.py responsibilities and forbidden logic
```

**Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_docs_composition_root -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add README.md docs/http_api.md docs/app_composition_root_map.md tests/test_docs_composition_root.py
git commit -m "docs: add composition root migration map and verification notes"
```

---

## Final Verification Checklist

- Run: `python3 -m unittest discover -s tests -p 'test_*.py'`
- Run: `python3 -m unittest tests.test_app_line_budget tests.test_app_composition_root_structure tests.test_app_modularization_guardrails -v`
- Run: `python3 -m unittest tests.test_chat_start_flow tests.test_chat_job_flow tests.test_teacher_memory_api_service tests.test_tool_dispatch_service -v`
- Confirm: `/Users/lvxiaoer/Documents/New project/.worktrees/app-py-composition-root/services/api/app.py` line count `<= 5000`.

## Expected Outcome

- `app.py` becomes strict composition root (route + DI + mapping only).
- Remaining business logic fully moved into domain service modules.
- Guard tests prevent logic from drifting back into `app.py`.
- Full test suite and domain regression tests remain green.
