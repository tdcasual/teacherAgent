# Upload & Exam Handlers Extraction Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move assignment/exam upload HTTP handlers and their immediate error/validation logic into dedicated handler modules while keeping `app_core.py` focused on wiring.

**Architecture:** Introduce `handlers/assignment_upload_handlers.py` and `handlers/exam_upload_handlers.py` with small deps dataclasses. `app_core` builds deps and delegates handler calls. Error mapping stays in handlers for easier debugging and extension.

**Tech Stack:** Python 3.11, FastAPI, pytest (anyio)

---

### Task 1: Add upload handlers + tests

**Files:**
- Create: `/Users/lvxiaoer/Documents/New project/services/api/handlers/assignment_upload_handlers.py`
- Create: `/Users/lvxiaoer/Documents/New project/services/api/handlers/exam_upload_handlers.py`
- Test: `/Users/lvxiaoer/Documents/New project/tests/test_upload_handlers.py`

**Step 1: Write the failing test**

Create `/Users/lvxiaoer/Documents/New project/tests/test_upload_handlers.py`:

```python
import pytest
from fastapi import HTTPException
from pathlib import Path

from services.api.api_models import UploadConfirmRequest
from services.api.handlers import assignment_upload_handlers, exam_upload_handlers
from services.api.exam_upload_api_service import ExamUploadApiError
from services.api.assignment_upload_start_service import AssignmentUploadStartError


def _exam_deps(**overrides):
    def start_exam_upload(*_args, **_kwargs):
        return {"ok": True}

    def exam_upload_status(_job_id):
        return {"ok": True}

    def exam_upload_draft(_job_id):
        return {"ok": True}

    def exam_upload_draft_save(**_kwargs):
        return {"ok": True}

    def exam_upload_confirm(_job_id):
        return {"ok": True}

    deps = exam_upload_handlers.ExamUploadHandlerDeps(
        start_exam_upload=start_exam_upload,
        exam_upload_status=exam_upload_status,
        exam_upload_draft=exam_upload_draft,
        exam_upload_draft_save=exam_upload_draft_save,
        exam_upload_confirm=exam_upload_confirm,
    )
    for key, value in overrides.items():
        setattr(deps, key, value)
    return deps


def _assignment_deps(tmp_path, **overrides):
    def assignment_upload_legacy(**_kwargs):
        return {"ok": True}

    async def start_assignment_upload(**_kwargs):
        return {"ok": True}

    def assignment_upload_status(_job_id):
        return {"ok": True}

    def assignment_upload_draft(_job_id):
        return {"ok": True}

    def assignment_upload_draft_save(*_args, **_kwargs):
        return {"ok": True}

    def load_upload_job(_job_id):
        return {"job_id": _job_id, "status": "done"}

    def ensure_assignment_upload_confirm_ready(_job):
        return None

    def confirm_assignment_upload(*_args, **_kwargs):
        return {"ok": True}

    def upload_job_path(_job_id):
        return Path(tmp_path)

    deps = assignment_upload_handlers.AssignmentUploadHandlerDeps(
        assignment_upload_legacy=assignment_upload_legacy,
        start_assignment_upload=start_assignment_upload,
        assignment_upload_status=assignment_upload_status,
        assignment_upload_draft=assignment_upload_draft,
        assignment_upload_draft_save=assignment_upload_draft_save,
        load_upload_job=load_upload_job,
        ensure_assignment_upload_confirm_ready=ensure_assignment_upload_confirm_ready,
        confirm_assignment_upload=confirm_assignment_upload,
        upload_job_path=upload_job_path,
    )
    for key, value in overrides.items():
        setattr(deps, key, value)
    return deps


@pytest.mark.anyio
async def test_exam_upload_status_maps_error():
    def exam_upload_status(_job_id):
        raise ExamUploadApiError(400, "bad")

    deps = _exam_deps(exam_upload_status=exam_upload_status)

    with pytest.raises(HTTPException) as exc:
        await exam_upload_handlers.exam_upload_status("job-1", deps=deps)

    assert exc.value.status_code == 400


@pytest.mark.anyio
async def test_assignment_upload_start_maps_error(tmp_path):
    async def start_assignment_upload(**_kwargs):
        raise AssignmentUploadStartError(400, "bad")

    deps = _assignment_deps(tmp_path, start_assignment_upload=start_assignment_upload)

    with pytest.raises(HTTPException) as exc:
        await assignment_upload_handlers.assignment_upload_start(
            assignment_id="a1",
            date="",
            due_at="",
            scope="",
            class_name="",
            student_ids="",
            files=[],
            answer_files=None,
            ocr_mode="FREE_OCR",
            language="zh",
            deps=deps,
        )

    assert exc.value.status_code == 400


@pytest.mark.anyio
async def test_assignment_upload_confirm_not_found(tmp_path):
    def load_upload_job(_job_id):
        raise FileNotFoundError("missing")

    deps = _assignment_deps(tmp_path, load_upload_job=load_upload_job)

    with pytest.raises(HTTPException) as exc:
        await assignment_upload_handlers.assignment_upload_confirm(
            UploadConfirmRequest(job_id="job-1"),
            deps=deps,
        )

    assert exc.value.status_code == 404


@pytest.mark.anyio
async def test_assignment_upload_confirm_returns_ready(tmp_path):
    def ensure_assignment_upload_confirm_ready(_job):
        return {"ok": True}

    deps = _assignment_deps(tmp_path, ensure_assignment_upload_confirm_ready=ensure_assignment_upload_confirm_ready)

    result = await assignment_upload_handlers.assignment_upload_confirm(
        UploadConfirmRequest(job_id="job-1"),
        deps=deps,
    )

    assert result == {"ok": True}
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_upload_handlers.py -v`
Expected: FAIL (module/function missing)

**Step 3: Implement handlers**

Create `/Users/lvxiaoer/Documents/New project/services/api/handlers/exam_upload_handlers.py`:

```python
from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Callable

from fastapi import HTTPException

from ..api_models import ExamUploadConfirmRequest, ExamUploadDraftSaveRequest
from ..exam_upload_api_service import ExamUploadApiError


@dataclass
class ExamUploadHandlerDeps:
    start_exam_upload: Callable[..., Any]
    exam_upload_status: Callable[[str], Any]
    exam_upload_draft: Callable[[str], Any]
    exam_upload_draft_save: Callable[..., Any]
    exam_upload_confirm: Callable[[str], Any]


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def _call_exam_api(fn: Callable[..., Any], *args, **kwargs):
    try:
        return await _maybe_await(fn(*args, **kwargs))
    except ExamUploadApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


async def exam_upload_start(
    *,
    exam_id: str,
    date: str,
    class_name: str,
    paper_files,
    score_files,
    answer_files,
    ocr_mode: str,
    language: str,
    deps: ExamUploadHandlerDeps,
):
    try:
        return await _maybe_await(
            deps.start_exam_upload(
                exam_id,
                date,
                class_name,
                paper_files,
                score_files,
                answer_files,
                ocr_mode,
                language,
                deps=None,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


async def exam_upload_status(job_id: str, *, deps: ExamUploadHandlerDeps):
    return await _call_exam_api(deps.exam_upload_status, job_id)


async def exam_upload_draft(job_id: str, *, deps: ExamUploadHandlerDeps):
    return await _call_exam_api(deps.exam_upload_draft, job_id)


async def exam_upload_draft_save(req: ExamUploadDraftSaveRequest, *, deps: ExamUploadHandlerDeps):
    return await _call_exam_api(
        deps.exam_upload_draft_save,
        job_id=req.job_id,
        meta=req.meta,
        questions=req.questions,
        score_schema=req.score_schema,
        answer_key_text=req.answer_key_text,
    )


async def exam_upload_confirm(req: ExamUploadConfirmRequest, *, deps: ExamUploadHandlerDeps):
    return await _call_exam_api(deps.exam_upload_confirm, req.job_id)
```

Create `/Users/lvxiaoer/Documents/New project/services/api/handlers/assignment_upload_handlers.py`:

```python
from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Callable

from fastapi import HTTPException

from ..api_models import UploadConfirmRequest, UploadDraftSaveRequest
from ..assignment_upload_confirm_gate_service import AssignmentUploadConfirmGateError
from ..assignment_upload_confirm_service import AssignmentUploadConfirmError
from ..assignment_upload_draft_save_service import AssignmentUploadDraftSaveError
from ..assignment_upload_legacy_service import AssignmentUploadLegacyError
from ..assignment_upload_query_service import AssignmentUploadQueryError
from ..assignment_upload_start_service import AssignmentUploadStartError


@dataclass
class AssignmentUploadHandlerDeps:
    assignment_upload_legacy: Callable[..., Any]
    start_assignment_upload: Callable[..., Any]
    assignment_upload_status: Callable[[str], Any]
    assignment_upload_draft: Callable[[str], Any]
    assignment_upload_draft_save: Callable[..., Any]
    load_upload_job: Callable[[str], Any]
    ensure_assignment_upload_confirm_ready: Callable[[Any], Any]
    confirm_assignment_upload: Callable[..., Any]
    upload_job_path: Callable[[str], Any]


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def assignment_upload(**kwargs):
    deps: AssignmentUploadHandlerDeps = kwargs.pop("deps")
    try:
        return await _maybe_await(deps.assignment_upload_legacy(**kwargs))
    except AssignmentUploadLegacyError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


async def assignment_upload_start(
    *,
    assignment_id: str,
    date: str,
    due_at: str,
    scope: str,
    class_name: str,
    student_ids: str,
    files,
    answer_files,
    ocr_mode: str,
    language: str,
    deps: AssignmentUploadHandlerDeps,
):
    try:
        return await _maybe_await(
            deps.start_assignment_upload(
                assignment_id=assignment_id,
                date=date,
                due_at=due_at,
                scope=scope,
                class_name=class_name,
                student_ids=student_ids,
                files=files,
                answer_files=answer_files,
                ocr_mode=ocr_mode,
                language=language,
                deps=None,
            )
        )
    except AssignmentUploadStartError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


async def assignment_upload_status(job_id: str, *, deps: AssignmentUploadHandlerDeps):
    try:
        return await _maybe_await(deps.assignment_upload_status(job_id))
    except AssignmentUploadQueryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


async def assignment_upload_draft(job_id: str, *, deps: AssignmentUploadHandlerDeps):
    try:
        return await _maybe_await(deps.assignment_upload_draft(job_id))
    except AssignmentUploadQueryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


async def assignment_upload_draft_save(req: UploadDraftSaveRequest, *, deps: AssignmentUploadHandlerDeps):
    try:
        return await _maybe_await(
            deps.assignment_upload_draft_save(
                req.job_id,
                req.requirements,
                req.questions,
                deps=None,
            )
        )
    except AssignmentUploadDraftSaveError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


async def assignment_upload_confirm(req: UploadConfirmRequest, *, deps: AssignmentUploadHandlerDeps):
    try:
        job = deps.load_upload_job(req.job_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="job not found")

    try:
        ready = deps.ensure_assignment_upload_confirm_ready(job)
    except AssignmentUploadConfirmGateError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    if ready is not None:
        return ready

    strict = True if req.strict_requirements is None else bool(req.strict_requirements)
    job_dir = deps.upload_job_path(req.job_id)
    try:
        return await _maybe_await(
            deps.confirm_assignment_upload(
                req.job_id,
                job,
                job_dir,
                requirements_override=req.requirements_override,
                strict_requirements=strict,
                deps=None,
            )
        )
    except AssignmentUploadConfirmError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
```

**Step 4: Run tests to verify pass**

Run: `python3 -m pytest tests/test_upload_handlers.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add /Users/lvxiaoer/Documents/New\ project/services/api/handlers/assignment_upload_handlers.py \
  /Users/lvxiaoer/Documents/New\ project/services/api/handlers/exam_upload_handlers.py \
  /Users/lvxiaoer/Documents/New\ project/tests/test_upload_handlers.py
git commit -m "refactor: add upload handlers"
```

---

### Task 2: Delegate app_core upload/exam endpoints to handlers

**Files:**
- Modify: `/Users/lvxiaoer/Documents/New project/services/api/app_core.py`

**Step 1: Write failing test (if needed)**

No new tests required beyond Task 1; keep route tests intact.

**Step 2: Update app_core to use handlers**

In `/Users/lvxiaoer/Documents/New project/services/api/app_core.py`:

- Import handlers:

```python
from .handlers import assignment_upload_handlers, exam_upload_handlers
```

- Add deps builders:

```python
def _exam_upload_handlers_deps():
    return exam_upload_handlers.ExamUploadHandlerDeps(
        start_exam_upload=lambda *args, **kwargs: _start_exam_upload_impl(*args, **kwargs, deps=_exam_upload_start_deps()),
        exam_upload_status=lambda job_id: _exam_upload_status_api_impl(job_id, deps=_exam_upload_api_deps()),
        exam_upload_draft=lambda job_id: _exam_upload_draft_api_impl(job_id, deps=_exam_upload_api_deps()),
        exam_upload_draft_save=lambda **kwargs: _exam_upload_draft_save_api_impl(**kwargs, deps=_exam_upload_api_deps()),
        exam_upload_confirm=lambda job_id: _exam_upload_confirm_api_impl(job_id, deps=_exam_upload_api_deps()),
    )


def _assignment_upload_handlers_deps():
    return assignment_upload_handlers.AssignmentUploadHandlerDeps(
        assignment_upload_legacy=lambda **kwargs: _assignment_upload_legacy_impl(deps=_assignment_upload_legacy_deps(), **kwargs),
        start_assignment_upload=lambda **kwargs: _start_assignment_upload_impl(deps=_assignment_upload_start_deps(), **kwargs),
        assignment_upload_status=lambda job_id: _get_assignment_upload_status_impl(job_id, deps=_assignment_upload_query_deps()),
        assignment_upload_draft=lambda job_id: _get_assignment_upload_draft_impl(job_id, deps=_assignment_upload_query_deps()),
        assignment_upload_draft_save=lambda job_id, requirements, questions, deps=None: _save_assignment_upload_draft_impl(job_id, requirements, questions, deps=_assignment_upload_draft_save_deps()),
        load_upload_job=load_upload_job,
        ensure_assignment_upload_confirm_ready=_ensure_assignment_upload_confirm_ready_impl,
        confirm_assignment_upload=lambda *args, **kwargs: _confirm_assignment_upload_impl(*args, **kwargs, deps=_assignment_upload_confirm_deps()),
        upload_job_path=upload_job_path,
    )
```

- Replace bodies of the upload endpoints to delegate:

```python
async def assignment_upload(...):
    return await assignment_upload_handlers.assignment_upload(
        assignment_id=assignment_id,
        date=date,
        scope=scope,
        class_name=class_name,
        student_ids=student_ids,
        files=files,
        answer_files=answer_files,
        ocr_mode=ocr_mode,
        language=language,
        deps=_assignment_upload_handlers_deps(),
    )

async def exam_upload_start(...):
    return await exam_upload_handlers.exam_upload_start(
        exam_id=exam_id,
        date=date,
        class_name=class_name,
        paper_files=paper_files,
        score_files=score_files,
        answer_files=answer_files,
        ocr_mode=ocr_mode,
        language=language,
        deps=_exam_upload_handlers_deps(),
    )

async def exam_upload_status(job_id: str):
    return await exam_upload_handlers.exam_upload_status(job_id, deps=_exam_upload_handlers_deps())

async def exam_upload_draft(job_id: str):
    return await exam_upload_handlers.exam_upload_draft(job_id, deps=_exam_upload_handlers_deps())

async def exam_upload_draft_save(req: ExamUploadDraftSaveRequest):
    return await exam_upload_handlers.exam_upload_draft_save(req, deps=_exam_upload_handlers_deps())

async def exam_upload_confirm(req: ExamUploadConfirmRequest):
    return await exam_upload_handlers.exam_upload_confirm(req, deps=_exam_upload_handlers_deps())

async def assignment_upload_start(...):
    return await assignment_upload_handlers.assignment_upload_start(
        assignment_id=assignment_id,
        date=date,
        due_at=due_at,
        scope=scope,
        class_name=class_name,
        student_ids=student_ids,
        files=files,
        answer_files=answer_files,
        ocr_mode=ocr_mode,
        language=language,
        deps=_assignment_upload_handlers_deps(),
    )

async def assignment_upload_status(job_id: str):
    return await assignment_upload_handlers.assignment_upload_status(job_id, deps=_assignment_upload_handlers_deps())

async def assignment_upload_draft(job_id: str):
    return await assignment_upload_handlers.assignment_upload_draft(job_id, deps=_assignment_upload_handlers_deps())

async def assignment_upload_draft_save(req: UploadDraftSaveRequest):
    return await assignment_upload_handlers.assignment_upload_draft_save(req, deps=_assignment_upload_handlers_deps())

async def assignment_upload_confirm(req: UploadConfirmRequest):
    return await assignment_upload_handlers.assignment_upload_confirm(req, deps=_assignment_upload_handlers_deps())
```

**Step 3: Run targeted tests**

Run:
- `python3 -m pytest tests/test_upload_handlers.py -v`
- `python3 -m pytest tests/test_app_queue_backend_mode.py -v`

Expected: PASS

**Step 4: Commit**

```bash
git add /Users/lvxiaoer/Documents/New\ project/services/api/app_core.py
git commit -m "refactor: delegate upload endpoints to handlers"
```

---

### Task 3: Regression sweep

**Files:**
- None

**Step 1: Run core tests**

Run: `python3 -m pytest tests/test_settings.py tests/test_runtime_state.py tests/test_queue_runtime.py tests/test_upload_handlers.py tests/test_app_queue_backend_mode.py tests/test_tenant_admin_and_dispatcher.py -v`
Expected: PASS

**Step 2: Commit (if any test-only tweaks)**

```bash
git status -sb
```

---

Plan complete and saved to `/Users/lvxiaoer/Documents/New project/.worktrees/codex/phase2-upload-exam-handlers/docs/plans/2026-02-09-upload-exam-handlers-refactor.md`.

Two execution options:

1. Subagent-Driven (this session) — I dispatch a fresh subagent per task, review between tasks
2. Parallel Session (separate) — Open a new session using executing-plans and run the plan step-by-step

Which approach?
