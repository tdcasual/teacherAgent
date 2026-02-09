# Assignment Core Handlers Extraction Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extract assignment core endpoints (requirements, detail/today, assignments/progress) into a dedicated handler module so `app_core.py` only wires deps and delegates.

**Architecture:** Introduce `handlers/assignment_handlers.py` with a small deps dataclass that wraps list/progress/requirements/detail/today functions. `app_core.py` builds deps (binding existing service deps) and delegates. Error mapping stays in handlers for testability.

**Tech Stack:** Python 3.11, FastAPI, pytest (anyio)

---

### Task 1: Add assignment handlers + tests

**Files:**
- Create: `/Users/lvxiaoer/Documents/New project/services/api/handlers/assignment_handlers.py`
- Test: `/Users/lvxiaoer/Documents/New project/tests/test_assignment_handlers.py`

**Step 1: Write the failing test**

Create `/Users/lvxiaoer/Documents/New project/tests/test_assignment_handlers.py`:

```python
import pytest
from fastapi import HTTPException
from pathlib import Path

from services.api.api_models import AssignmentRequirementsRequest
from services.api.handlers import assignment_handlers


def _deps(tmp_path, **overrides):
    def list_assignments():
        return {"assignments": []}

    def compute_assignment_progress(assignment_id: str, include_students: bool = True):
        return {"ok": True, "assignment_id": assignment_id, "updated_at": "2024-01-01T00:00:00"}

    def parse_date_str(value):
        return str(value or "")

    def save_assignment_requirements(assignment_id, requirements, date_str, created_by):
        return {"ok": True, "assignment_id": assignment_id}

    def resolve_assignment_dir(assignment_id: str) -> Path:
        return Path(tmp_path) / assignment_id

    def load_assignment_requirements(folder: Path):
        return {"difficulty": "medium"}

    def assignment_today(**_kwargs):
        return {"ok": True}

    def get_assignment_detail_api(_assignment_id: str):
        return {"ok": True}

    deps = assignment_handlers.AssignmentHandlerDeps(
        list_assignments=list_assignments,
        compute_assignment_progress=compute_assignment_progress,
        parse_date_str=parse_date_str,
        save_assignment_requirements=save_assignment_requirements,
        resolve_assignment_dir=resolve_assignment_dir,
        load_assignment_requirements=load_assignment_requirements,
        assignment_today=assignment_today,
        get_assignment_detail_api=get_assignment_detail_api,
    )
    for key, value in overrides.items():
        setattr(deps, key, value)
    return deps


@pytest.mark.anyio
async def test_assignment_requirements_maps_error(tmp_path):
    def save_assignment_requirements(*_args, **_kwargs):
        return {"error": "bad"}

    deps = _deps(tmp_path, save_assignment_requirements=save_assignment_requirements)

    with pytest.raises(HTTPException) as exc:
        await assignment_handlers.assignment_requirements(
            AssignmentRequirementsRequest(assignment_id="a1", requirements={}),
            deps=deps,
        )

    assert exc.value.status_code == 400


@pytest.mark.anyio
async def test_assignment_requirements_get_invalid_id(tmp_path):
    def resolve_assignment_dir(_assignment_id: str):
        raise ValueError("invalid assignment_id")

    deps = _deps(tmp_path, resolve_assignment_dir=resolve_assignment_dir)

    with pytest.raises(HTTPException) as exc:
        await assignment_handlers.assignment_requirements_get("bad", deps=deps)

    assert exc.value.status_code == 400


@pytest.mark.anyio
async def test_assignment_requirements_get_missing(tmp_path):
    deps = _deps(tmp_path)

    with pytest.raises(HTTPException) as exc:
        await assignment_handlers.assignment_requirements_get("missing", deps=deps)

    assert exc.value.status_code == 404


@pytest.mark.anyio
async def test_assignment_detail_maps_not_found(tmp_path):
    def get_assignment_detail_api(_assignment_id: str):
        return {"error": "assignment_not_found"}

    deps = _deps(tmp_path, get_assignment_detail_api=get_assignment_detail_api)

    with pytest.raises(HTTPException) as exc:
        await assignment_handlers.assignment_detail("a1", deps=deps)

    assert exc.value.status_code == 404


@pytest.mark.anyio
async def test_teacher_assignment_progress_requires_id(tmp_path):
    deps = _deps(tmp_path)

    with pytest.raises(HTTPException) as exc:
        await assignment_handlers.teacher_assignment_progress("", include_students=True, deps=deps)

    assert exc.value.status_code == 400


@pytest.mark.anyio
async def test_teacher_assignment_progress_maps_not_found(tmp_path):
    def compute_assignment_progress(_assignment_id: str, include_students: bool = True):
        return {"ok": False, "error": "assignment_not_found"}

    deps = _deps(tmp_path, compute_assignment_progress=compute_assignment_progress)

    with pytest.raises(HTTPException) as exc:
        await assignment_handlers.teacher_assignment_progress("a1", include_students=True, deps=deps)

    assert exc.value.status_code == 404


@pytest.mark.anyio
async def test_teacher_assignments_progress_filters_and_sorts(tmp_path):
    def parse_date_str(_value):
        return "2024-01-02"

    def list_assignments():
        return {
            "assignments": [
                {"assignment_id": "a1", "date": "2024-01-02"},
                {"assignment_id": "a2", "date": "2024-01-02"},
                {"assignment_id": "a3", "date": "2024-01-01"},
            ]
        }

    def compute_assignment_progress(assignment_id: str, include_students: bool = False):
        updated = "2024-01-02T09:00:00" if assignment_id == "a1" else "2024-01-02T10:00:00"
        return {"ok": True, "assignment_id": assignment_id, "updated_at": updated}

    deps = _deps(
        tmp_path,
        parse_date_str=parse_date_str,
        list_assignments=list_assignments,
        compute_assignment_progress=compute_assignment_progress,
    )

    result = await assignment_handlers.teacher_assignments_progress(date="ignored", deps=deps)

    assert [item["assignment_id"] for item in result["assignments"]] == ["a2", "a1"]


@pytest.mark.anyio
async def test_assignment_today_returns_result(tmp_path):
    def assignment_today(**kwargs):
        return {"ok": True, "student_id": kwargs["student_id"]}

    deps = _deps(tmp_path, assignment_today=assignment_today)

    result = await assignment_handlers.assignment_today(
        student_id="s1",
        date=None,
        auto_generate=False,
        generate=True,
        per_kp=5,
        deps=deps,
    )

    assert result == {"ok": True, "student_id": "s1"}
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_assignment_handlers.py -v`
Expected: FAIL (module not found)

**Step 3: Write minimal implementation**

Create `/Users/lvxiaoer/Documents/New project/services/api/handlers/assignment_handlers.py`:

```python
from __future__ import annotations

import inspect
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from fastapi import HTTPException

from ..api_models import AssignmentRequirementsRequest


@dataclass
class AssignmentHandlerDeps:
    list_assignments: Callable[[], Dict[str, Any]]
    compute_assignment_progress: Callable[[str, bool], Dict[str, Any]]
    parse_date_str: Callable[[Optional[str]], str]
    save_assignment_requirements: Callable[[str, Dict[str, Any], str, str], Dict[str, Any]]
    resolve_assignment_dir: Callable[[str], Path]
    load_assignment_requirements: Callable[[Path], Dict[str, Any]]
    assignment_today: Callable[..., Any]
    get_assignment_detail_api: Callable[[str], Dict[str, Any]]


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def assignments(*, deps: AssignmentHandlerDeps):
    return await _maybe_await(deps.list_assignments())


async def teacher_assignment_progress(
    assignment_id: str,
    *,
    include_students: bool = True,
    deps: AssignmentHandlerDeps,
):
    assignment_id = (assignment_id or "").strip()
    if not assignment_id:
        raise HTTPException(status_code=400, detail="assignment_id is required")
    result = await _maybe_await(deps.compute_assignment_progress(assignment_id, bool(include_students)))
    if not result.get("ok") and result.get("error") == "assignment_not_found":
        raise HTTPException(status_code=404, detail="assignment not found")
    return result


async def teacher_assignments_progress(
    *,
    date: Optional[str] = None,
    deps: AssignmentHandlerDeps,
):
    date_str = deps.parse_date_str(date)
    items = (await _maybe_await(deps.list_assignments())).get("assignments") or []
    out = []
    for it in items:
        if (it.get("date") or "") != date_str:
            continue
        aid = str(it.get("assignment_id") or "")
        if not aid:
            continue
        prog = await _maybe_await(deps.compute_assignment_progress(aid, False))
        if prog.get("ok"):
            out.append(prog)
    out.sort(key=lambda x: (x.get("updated_at") or ""), reverse=True)
    return {"ok": True, "date": date_str, "assignments": out}


async def assignment_requirements(
    req: AssignmentRequirementsRequest,
    *,
    deps: AssignmentHandlerDeps,
):
    date_str = deps.parse_date_str(req.date)
    result = deps.save_assignment_requirements(
        req.assignment_id,
        req.requirements,
        date_str,
        created_by=req.created_by or "teacher",
    )
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result)
    return result


async def assignment_requirements_get(assignment_id: str, *, deps: AssignmentHandlerDeps):
    try:
        folder = deps.resolve_assignment_dir(assignment_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not folder.exists():
        raise HTTPException(status_code=404, detail="assignment not found")
    requirements = deps.load_assignment_requirements(folder)
    if not requirements:
        return {"assignment_id": assignment_id, "requirements": None}
    return {"assignment_id": assignment_id, "requirements": requirements}


async def assignment_today(
    *,
    student_id: str,
    date: Optional[str],
    auto_generate: bool,
    generate: bool,
    per_kp: int,
    deps: AssignmentHandlerDeps,
):
    return await _maybe_await(
        deps.assignment_today(
            student_id=student_id,
            date=date,
            auto_generate=auto_generate,
            generate=generate,
            per_kp=per_kp,
        )
    )


async def assignment_detail(assignment_id: str, *, deps: AssignmentHandlerDeps):
    result = await _maybe_await(deps.get_assignment_detail_api(assignment_id))
    if result.get("error") == "assignment_not_found":
        raise HTTPException(status_code=404, detail="assignment not found")
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result)
    return result
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_assignment_handlers.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add /Users/lvxiaoer/Documents/New\ project/services/api/handlers/assignment_handlers.py \
  /Users/lvxiaoer/Documents/New\ project/tests/test_assignment_handlers.py
git commit -m "refactor: add assignment handlers"
```

---

### Task 2: Delegate assignment endpoints to handlers

**Files:**
- Modify: `/Users/lvxiaoer/Documents/New project/services/api/app_core.py`

**Step 1: Write failing test (if needed)**

No new route tests required beyond Task 1; keep existing route tests intact.

**Step 2: Update app_core to use handlers**

In `/Users/lvxiaoer/Documents/New project/services/api/app_core.py`:

- Import handler module:

```python
from .handlers import assignment_handlers
```

- Add deps builder near other handlers deps:

```python
def _assignment_handlers_deps() -> assignment_handlers.AssignmentHandlerDeps:
    return assignment_handlers.AssignmentHandlerDeps(
        list_assignments=list_assignments,
        compute_assignment_progress=compute_assignment_progress,
        parse_date_str=parse_date_str,
        save_assignment_requirements=save_assignment_requirements,
        resolve_assignment_dir=resolve_assignment_dir,
        load_assignment_requirements=load_assignment_requirements,
        assignment_today=lambda student_id, date=None, auto_generate=False, generate=True, per_kp=5: _assignment_today_impl(
            student_id=student_id,
            date=date,
            auto_generate=auto_generate,
            generate=generate,
            per_kp=per_kp,
            deps=_assignment_today_deps(),
        ),
        get_assignment_detail_api=lambda assignment_id: _get_assignment_detail_api_impl(
            assignment_id,
            deps=_assignment_api_deps(),
        ),
    )
```

- Replace endpoint bodies to delegate:

```python
async def assignments():
    return await assignment_handlers.assignments(deps=_assignment_handlers_deps())

async def teacher_assignment_progress(assignment_id: str, include_students: bool = True):
    return await assignment_handlers.teacher_assignment_progress(
        assignment_id,
        include_students=include_students,
        deps=_assignment_handlers_deps(),
    )

async def teacher_assignments_progress(date: Optional[str] = None):
    return await assignment_handlers.teacher_assignments_progress(
        date=date,
        deps=_assignment_handlers_deps(),
    )

async def assignment_requirements(req: AssignmentRequirementsRequest):
    return await assignment_handlers.assignment_requirements(req, deps=_assignment_handlers_deps())

async def assignment_requirements_get(assignment_id: str):
    return await assignment_handlers.assignment_requirements_get(assignment_id, deps=_assignment_handlers_deps())

async def assignment_today(
    student_id: str,
    date: Optional[str] = None,
    auto_generate: bool = False,
    generate: bool = True,
    per_kp: int = 5,
):
    return await assignment_handlers.assignment_today(
        student_id=student_id,
        date=date,
        auto_generate=auto_generate,
        generate=generate,
        per_kp=per_kp,
        deps=_assignment_handlers_deps(),
    )

async def assignment_detail(assignment_id: str):
    return await assignment_handlers.assignment_detail(assignment_id, deps=_assignment_handlers_deps())
```

**Step 3: Run targeted tests**

Run:
- `python3 -m pytest tests/test_assignment_handlers.py -v`
- `python3 -m pytest tests/test_app_queue_backend_mode.py -v`

Expected: PASS

**Step 4: Commit**

```bash
git add /Users/lvxiaoer/Documents/New\ project/services/api/app_core.py
git commit -m "refactor: delegate assignment endpoints to handlers"
```

---

### Task 3: Regression sweep

**Files:**
- None

**Step 1: Run core tests**

Run: `python3 -m pytest tests/test_settings.py tests/test_runtime_state.py tests/test_queue_runtime.py tests/test_assignment_handlers.py tests/test_app_queue_backend_mode.py tests/test_tenant_admin_and_dispatcher.py -v`
Expected: PASS

**Step 2: Commit (if any test-only tweaks)**

```bash
git status -sb
```
