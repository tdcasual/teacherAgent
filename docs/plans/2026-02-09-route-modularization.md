# API Route Modularization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move FastAPI route handlers out of `services/api/app_core.py` into dedicated `services/api/routes/*.py` modules and register them with `APIRouter` in `services/api/app_routes.py` without changing behavior.

**Architecture:** Each routes module exposes `build_router(core)` and defines the existing route functions, delegating to `core` helpers and handler deps. `register_routes` composes routers via `app.include_router` and keeps a minimal `/health` fallback when `core` is missing.

**Tech Stack:** Python 3, FastAPI, Pydantic, pytest.

---

### Task 1: Add routes package and assignment routes

**Files:**
- Create: `services/api/routes/__init__.py`
- Create: `services/api/routes/assignment_routes.py`
- Test: `tests/test_assignment_routes.py`

**Step 1: Write the failing test**

```python
from services.api.routes import assignment_routes


def _has_route(router, method, path):
    return any(
        path == route.path and method in (route.methods or set())
        for route in router.routes
    )


def test_assignment_routes_build_router():
    router = assignment_routes.build_router(object())
    assert _has_route(router, "GET", "/assignments")
    assert _has_route(router, "GET", "/assignment/{assignment_id}")
    assert _has_route(router, "POST", "/assignment/requirements")
    assert _has_route(router, "POST", "/assignment/upload")
    assert _has_route(router, "POST", "/assignment/upload/start")
    assert _has_route(router, "POST", "/assignment/upload/confirm")
    assert _has_route(router, "GET", "/assignment/{assignment_id}/download")
    assert _has_route(router, "POST", "/assignment/questions/ocr")
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_assignment_routes.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'services.api.routes'`.

**Step 3: Write minimal implementation**

Create `services/api/routes/__init__.py`:

```python
from __future__ import annotations
```

Create `services/api/routes/assignment_routes.py`:

```python
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, File, Form, UploadFile

from ..api_models import AssignmentRequirementsRequest, UploadConfirmRequest, UploadDraftSaveRequest


def build_router(core) -> APIRouter:
    router = APIRouter()

    @router.get("/assignments")
    async def assignments():
        return await core.assignment_handlers.assignments(deps=core._assignment_handlers_deps())

    @router.get("/teacher/assignment/progress")
    async def teacher_assignment_progress(assignment_id: str, include_students: bool = True):
        return await core.assignment_handlers.teacher_assignment_progress(
            assignment_id,
            include_students=include_students,
            deps=core._assignment_handlers_deps(),
        )

    @router.get("/teacher/assignments/progress")
    async def teacher_assignments_progress(date: Optional[str] = None):
        return await core.assignment_handlers.teacher_assignments_progress(
            date=date,
            deps=core._assignment_handlers_deps(),
        )

    @router.post("/assignment/requirements")
    async def assignment_requirements(req: AssignmentRequirementsRequest):
        return await core.assignment_handlers.assignment_requirements(req, deps=core._assignment_handlers_deps())

    @router.get("/assignment/{assignment_id}/requirements")
    async def assignment_requirements_get(assignment_id: str):
        return await core.assignment_handlers.assignment_requirements_get(assignment_id, deps=core._assignment_handlers_deps())

    @router.post("/assignment/upload")
    async def assignment_upload(
        assignment_id: str = Form(...),
        date: Optional[str] = Form(""),
        scope: Optional[str] = Form(""),
        class_name: Optional[str] = Form(""),
        student_ids: Optional[str] = Form(""),
        files: list[UploadFile] = File(...),
        answer_files: Optional[list[UploadFile]] = File(None),
        ocr_mode: Optional[str] = Form("FREE_OCR"),
        language: Optional[str] = Form("zh"),
    ):
        return await core.assignment_upload_handlers.assignment_upload(
            assignment_id=assignment_id,
            date=date,
            scope=scope,
            class_name=class_name,
            student_ids=student_ids,
            files=files,
            answer_files=answer_files,
            ocr_mode=ocr_mode,
            language=language,
            deps=core._assignment_upload_handlers_deps(),
        )

    @router.post("/assignment/upload/start")
    async def assignment_upload_start(
        assignment_id: str = Form(...),
        date: Optional[str] = Form(""),
        due_at: Optional[str] = Form(""),
        scope: Optional[str] = Form(""),
        class_name: Optional[str] = Form(""),
        student_ids: Optional[str] = Form(""),
        files: list[UploadFile] = File(...),
        answer_files: Optional[list[UploadFile]] = File(None),
        ocr_mode: Optional[str] = Form("FREE_OCR"),
        language: Optional[str] = Form("zh"),
    ):
        return await core.assignment_upload_handlers.assignment_upload_start(
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
            deps=core._assignment_upload_handlers_deps(),
        )

    @router.get("/assignment/upload/status")
    async def assignment_upload_status(job_id: str):
        return await core.assignment_upload_handlers.assignment_upload_status(job_id, deps=core._assignment_upload_handlers_deps())

    @router.get("/assignment/upload/draft")
    async def assignment_upload_draft(job_id: str):
        return await core.assignment_upload_handlers.assignment_upload_draft(job_id, deps=core._assignment_upload_handlers_deps())

    @router.post("/assignment/upload/draft/save")
    async def assignment_upload_draft_save(req: UploadDraftSaveRequest):
        return await core.assignment_upload_handlers.assignment_upload_draft_save(req, deps=core._assignment_upload_handlers_deps())

    @router.post("/assignment/upload/confirm")
    async def assignment_upload_confirm(req: UploadConfirmRequest):
        return await core.assignment_upload_handlers.assignment_upload_confirm(req, deps=core._assignment_upload_handlers_deps())

    @router.get("/assignment/{assignment_id}/download")
    async def assignment_download(assignment_id: str, file: str):
        return await core.assignment_io_handlers.assignment_download(
            assignment_id,
            file,
            deps=core._assignment_io_handlers_deps(),
        )

    @router.get("/assignment/today")
    async def assignment_today(
        student_id: str,
        date: Optional[str] = None,
        auto_generate: bool = False,
        generate: bool = True,
        per_kp: int = 5,
    ):
        return await core.assignment_handlers.assignment_today(
            student_id=student_id,
            date=date,
            auto_generate=auto_generate,
            generate=generate,
            per_kp=per_kp,
            deps=core._assignment_handlers_deps(),
        )

    @router.get("/assignment/{assignment_id}")
    async def assignment_detail(assignment_id: str):
        return await core.assignment_handlers.assignment_detail(assignment_id, deps=core._assignment_handlers_deps())

    @router.post("/assignment/generate")
    async def generate_assignment(
        assignment_id: str = Form(...),
        kp: str = Form(""),
        question_ids: Optional[str] = Form(""),
        per_kp: int = Form(5),
        core_examples: Optional[str] = Form(""),
        generate: bool = Form(False),
        mode: Optional[str] = Form(""),
        date: Optional[str] = Form(""),
        due_at: Optional[str] = Form(""),
        class_name: Optional[str] = Form(""),
        student_ids: Optional[str] = Form(""),
        source: Optional[str] = Form(""),
        requirements_json: Optional[str] = Form(""),
    ):
        return await core.assignment_io_handlers.generate_assignment(
            assignment_id=assignment_id,
            kp=kp,
            question_ids=question_ids,
            per_kp=per_kp,
            core_examples=core_examples,
            generate=generate,
            mode=mode,
            date=date,
            due_at=due_at,
            class_name=class_name,
            student_ids=student_ids,
            source=source,
            requirements_json=requirements_json,
            deps=core._assignment_io_handlers_deps(),
        )

    @router.post("/assignment/render")
    async def render_assignment(assignment_id: str = Form(...)):
        return await core.assignment_io_handlers.render_assignment(assignment_id, deps=core._assignment_io_handlers_deps())

    @router.post("/assignment/questions/ocr")
    async def assignment_questions_ocr(
        assignment_id: str = Form(...),
        files: list[UploadFile] = File(...),
        kp_id: Optional[str] = Form("uncategorized"),
        difficulty: Optional[str] = Form("basic"),
        tags: Optional[str] = Form("ocr"),
        ocr_mode: Optional[str] = Form("FREE_OCR"),
        language: Optional[str] = Form("zh"),
    ):
        return await core.assignment_io_handlers.assignment_questions_ocr(
            assignment_id=assignment_id,
            files=files,
            kp_id=kp_id,
            difficulty=difficulty,
            tags=tags,
            ocr_mode=ocr_mode,
            language=language,
            deps=core._assignment_io_handlers_deps(),
        )

    return router
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_assignment_routes.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add services/api/routes/__init__.py services/api/routes/assignment_routes.py tests/test_assignment_routes.py
git commit -m "feat: add assignment routes module"
```

### Task 2: Add exam routes

**Files:**
- Create: `services/api/routes/exam_routes.py`
- Test: `tests/test_exam_routes.py`

**Step 1: Write the failing test**

```python
from services.api.routes import exam_routes


def _has_route(router, method, path):
    return any(
        path == route.path and method in (route.methods or set())
        for route in router.routes
    )


def test_exam_routes_build_router():
    router = exam_routes.build_router(object())
    assert _has_route(router, "GET", "/exams")
    assert _has_route(router, "GET", "/exam/{exam_id}")
    assert _has_route(router, "GET", "/exam/{exam_id}/analysis")
    assert _has_route(router, "GET", "/exam/{exam_id}/students")
    assert _has_route(router, "GET", "/exam/{exam_id}/student/{student_id}")
    assert _has_route(router, "GET", "/exam/{exam_id}/question/{question_id}")
    assert _has_route(router, "POST", "/exam/upload/start")
    assert _has_route(router, "GET", "/exam/upload/status")
    assert _has_route(router, "GET", "/exam/upload/draft")
    assert _has_route(router, "POST", "/exam/upload/draft/save")
    assert _has_route(router, "POST", "/exam/upload/confirm")
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_exam_routes.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'services.api.routes.exam_routes'`.

**Step 3: Write minimal implementation**

Create `services/api/routes/exam_routes.py`:

```python
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..api_models import ExamUploadConfirmRequest, ExamUploadDraftSaveRequest


def build_router(core) -> APIRouter:
    router = APIRouter()

    @router.get("/exams")
    async def exams():
        return core.list_exams()

    @router.get("/exam/{exam_id}")
    async def exam_detail(exam_id: str):
        result = core._get_exam_detail_api_impl(exam_id, deps=core._exam_api_deps())
        if result.get("error") == "exam_not_found":
            raise HTTPException(status_code=404, detail="exam not found")
        if result.get("error"):
            raise HTTPException(status_code=400, detail=result)
        return result

    @router.get("/exam/{exam_id}/analysis")
    async def exam_analysis(exam_id: str):
        result = core.exam_analysis_get(exam_id)
        if result.get("error") == "exam_not_found":
            raise HTTPException(status_code=404, detail="exam not found")
        if result.get("error"):
            raise HTTPException(status_code=400, detail=result)
        return result

    @router.get("/exam/{exam_id}/students")
    async def exam_students(exam_id: str, limit: int = 50):
        result = core.exam_students_list(exam_id, limit=limit)
        if result.get("error") == "exam_not_found":
            raise HTTPException(status_code=404, detail="exam not found")
        if result.get("error"):
            raise HTTPException(status_code=400, detail=result)
        return result

    @router.get("/exam/{exam_id}/student/{student_id}")
    async def exam_student(exam_id: str, student_id: str):
        result = core.exam_student_detail(exam_id, student_id=student_id)
        if result.get("error") == "exam_not_found":
            raise HTTPException(status_code=404, detail="exam not found")
        if result.get("error"):
            raise HTTPException(status_code=400, detail=result)
        return result

    @router.get("/exam/{exam_id}/question/{question_id}")
    async def exam_question(exam_id: str, question_id: str):
        result = core.exam_question_detail(exam_id, question_id=question_id)
        if result.get("error") == "exam_not_found":
            raise HTTPException(status_code=404, detail="exam not found")
        if result.get("error"):
            raise HTTPException(status_code=400, detail=result)
        return result

    @router.post("/exam/upload/start")
    async def exam_upload_start(
        exam_id: Optional[str] = Form(""),
        date: Optional[str] = Form(""),
        class_name: Optional[str] = Form(""),
        paper_files: list[UploadFile] = File(...),
        score_files: list[UploadFile] = File(...),
        answer_files: Optional[list[UploadFile]] = File(None),
        ocr_mode: Optional[str] = Form("FREE_OCR"),
        language: Optional[str] = Form("zh"),
    ):
        return await core.exam_upload_handlers.exam_upload_start(
            exam_id=exam_id,
            date=date,
            class_name=class_name,
            paper_files=paper_files,
            score_files=score_files,
            answer_files=answer_files,
            ocr_mode=ocr_mode,
            language=language,
            deps=core._exam_upload_handlers_deps(),
        )

    @router.get("/exam/upload/status")
    async def exam_upload_status(job_id: str):
        return await core.exam_upload_handlers.exam_upload_status(job_id, deps=core._exam_upload_handlers_deps())

    @router.get("/exam/upload/draft")
    async def exam_upload_draft(job_id: str):
        return await core.exam_upload_handlers.exam_upload_draft(job_id, deps=core._exam_upload_handlers_deps())

    @router.post("/exam/upload/draft/save")
    async def exam_upload_draft_save(req: ExamUploadDraftSaveRequest):
        return await core.exam_upload_handlers.exam_upload_draft_save(req, deps=core._exam_upload_handlers_deps())

    @router.post("/exam/upload/confirm")
    async def exam_upload_confirm(req: ExamUploadConfirmRequest):
        return await core.exam_upload_handlers.exam_upload_confirm(req, deps=core._exam_upload_handlers_deps())

    return router
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_exam_routes.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add services/api/routes/exam_routes.py tests/test_exam_routes.py
git commit -m "feat: add exam routes module"
```

### Task 3: Add chat routes

**Files:**
- Create: `services/api/routes/chat_routes.py`
- Test: `tests/test_chat_routes.py`

**Step 1: Write the failing test**

```python
from services.api.routes import chat_routes


def _has_route(router, method, path):
    return any(
        path == route.path and method in (route.methods or set())
        for route in router.routes
    )


def test_chat_routes_build_router():
    router = chat_routes.build_router(object())
    assert _has_route(router, "POST", "/chat")
    assert _has_route(router, "POST", "/chat/start")
    assert _has_route(router, "GET", "/chat/status")
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_chat_routes.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'services.api.routes.chat_routes'`.

**Step 3: Write minimal implementation**

Create `services/api/routes/chat_routes.py`:

```python
from __future__ import annotations

from fastapi import APIRouter

from ..api_models import ChatRequest, ChatStartRequest


def build_router(core) -> APIRouter:
    router = APIRouter()

    @router.post("/chat")
    async def chat(req: ChatRequest):
        return await core.chat_handlers.chat(req, deps=core._chat_handlers_deps())

    @router.post("/chat/start")
    async def chat_start(req: ChatStartRequest):
        return await core.chat_handlers.chat_start(req, deps=core._chat_handlers_deps())

    @router.get("/chat/status")
    async def chat_status(job_id: str):
        return await core.chat_handlers.chat_status(job_id, deps=core._chat_handlers_deps())

    return router
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_chat_routes.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add services/api/routes/chat_routes.py tests/test_chat_routes.py
git commit -m "feat: add chat routes module"
```

### Task 4: Add student routes

**Files:**
- Create: `services/api/routes/student_routes.py`
- Test: `tests/test_student_routes.py`

**Step 1: Write the failing test**

```python
from services.api.routes import student_routes


def _has_route(router, method, path):
    return any(
        path == route.path and method in (route.methods or set())
        for route in router.routes
    )


def test_student_routes_build_router():
    router = student_routes.build_router(object())
    assert _has_route(router, "GET", "/student/history/sessions")
    assert _has_route(router, "GET", "/student/session/view-state")
    assert _has_route(router, "PUT", "/student/session/view-state")
    assert _has_route(router, "GET", "/student/history/session")
    assert _has_route(router, "GET", "/student/profile/{student_id}")
    assert _has_route(router, "POST", "/student/profile/update")
    assert _has_route(router, "POST", "/student/import")
    assert _has_route(router, "POST", "/student/verify")
    assert _has_route(router, "POST", "/student/submit")
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_student_routes.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'services.api.routes.student_routes'`.

**Step 3: Write minimal implementation**

Create `services/api/routes/student_routes.py`:

```python
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from ..api_models import StudentImportRequest, StudentVerifyRequest


def build_router(core) -> APIRouter:
    router = APIRouter()

    @router.get("/student/history/sessions")
    async def student_history_sessions(student_id: str, limit: int = 20, cursor: int = 0):
        try:
            return core._student_history_sessions_api_impl(
                student_id,
                limit=limit,
                cursor=cursor,
                deps=core._session_history_api_deps(),
            )
        except core.SessionHistoryApiError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)

    @router.get("/student/session/view-state")
    async def student_session_view_state(student_id: str):
        try:
            return core._student_session_view_state_api_impl(student_id, deps=core._session_history_api_deps())
        except core.SessionHistoryApiError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)

    @router.put("/student/session/view-state")
    async def update_student_session_view_state(req: Dict[str, Any]):
        try:
            return core._update_student_session_view_state_api_impl(req, deps=core._session_history_api_deps())
        except core.SessionHistoryApiError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)

    @router.get("/student/history/session")
    async def student_history_session(
        student_id: str,
        session_id: str,
        cursor: int = -1,
        limit: int = 50,
        direction: str = "backward",
    ):
        try:
            return core._student_history_session_api_impl(
                student_id,
                session_id,
                cursor=cursor,
                limit=limit,
                direction=direction,
                deps=core._session_history_api_deps(),
            )
        except core.SessionHistoryApiError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)

    @router.get("/student/profile/{student_id}")
    async def get_profile(student_id: str):
        result = core._get_profile_api_impl(student_id, deps=core._student_profile_api_deps())
        if result.get("error") in {"profile not found", "profile_not_found"}:
            raise HTTPException(status_code=404, detail="profile not found")
        if result.get("error"):
            raise HTTPException(status_code=400, detail=result)
        return result

    @router.post("/student/profile/update")
    async def update_profile(
        student_id: str = Form(...),
        weak_kp: Optional[str] = Form(""),
        strong_kp: Optional[str] = Form(""),
        medium_kp: Optional[str] = Form(""),
        next_focus: Optional[str] = Form(""),
        interaction_note: Optional[str] = Form(""),
    ):
        payload = core._update_profile_api_impl(
            student_id=student_id,
            weak_kp=weak_kp,
            strong_kp=strong_kp,
            medium_kp=medium_kp,
            next_focus=next_focus,
            interaction_note=interaction_note,
            deps=core._student_ops_api_deps(),
        )
        return JSONResponse(payload)

    @router.post("/student/import")
    async def import_students(req: StudentImportRequest):
        result = core.student_import(req.dict())
        if result.get("error"):
            raise HTTPException(status_code=400, detail=result["error"])
        return result

    @router.post("/student/verify")
    async def verify_student(req: StudentVerifyRequest):
        return core._verify_student_api_impl(req.name, req.class_name, deps=core._student_ops_api_deps())

    @router.post("/student/submit")
    async def submit(
        student_id: str = Form(...),
        files: list[UploadFile] = File(...),
        assignment_id: Optional[str] = Form(None),
        auto_assignment: bool = Form(False),
    ):
        return await core._student_submit_impl(
            student_id=student_id,
            files=files,
            assignment_id=assignment_id,
            auto_assignment=auto_assignment,
            deps=core._student_submit_deps(),
        )

    return router
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_student_routes.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add services/api/routes/student_routes.py tests/test_student_routes.py
git commit -m "feat: add student routes module"
```

### Task 5: Add teacher routes

**Files:**
- Create: `services/api/routes/teacher_routes.py`
- Test: `tests/test_teacher_routes.py`

**Step 1: Write the failing test**

```python
from services.api.routes import teacher_routes


def _has_route(router, method, path):
    return any(
        path == route.path and method in (route.methods or set())
        for route in router.routes
    )


def test_teacher_routes_build_router():
    router = teacher_routes.build_router(object())
    assert _has_route(router, "GET", "/teacher/history/sessions")
    assert _has_route(router, "GET", "/teacher/session/view-state")
    assert _has_route(router, "PUT", "/teacher/session/view-state")
    assert _has_route(router, "GET", "/teacher/history/session")
    assert _has_route(router, "GET", "/teacher/memory/proposals")
    assert _has_route(router, "GET", "/teacher/memory/insights")
    assert _has_route(router, "POST", "/teacher/memory/proposals/{proposal_id}/review")
    assert _has_route(router, "GET", "/teacher/llm-routing")
    assert _has_route(router, "POST", "/teacher/llm-routing/simulate")
    assert _has_route(router, "POST", "/teacher/llm-routing/rollback")
    assert _has_route(router, "GET", "/teacher/provider-registry")
    assert _has_route(router, "POST", "/teacher/provider-registry/providers")
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_teacher_routes.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'services.api.routes.teacher_routes'`.

**Step 3: Write minimal implementation**

Create `services/api/routes/teacher_routes.py`:

```python
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException

from ..api_models import (
    RoutingProposalCreateRequest,
    RoutingProposalReviewRequest,
    RoutingRollbackRequest,
    RoutingSimulateRequest,
    TeacherMemoryProposalReviewRequest,
    TeacherProviderRegistryCreateRequest,
    TeacherProviderRegistryDeleteRequest,
    TeacherProviderRegistryProbeRequest,
    TeacherProviderRegistryUpdateRequest,
)


def build_router(core) -> APIRouter:
    router = APIRouter()

    @router.get("/teacher/history/sessions")
    async def teacher_history_sessions(teacher_id: Optional[str] = None, limit: int = 20, cursor: int = 0):
        return core._teacher_history_sessions_api_impl(teacher_id, limit=limit, cursor=cursor, deps=core._session_history_api_deps())

    @router.get("/teacher/session/view-state")
    async def teacher_session_view_state(teacher_id: Optional[str] = None):
        return core._teacher_session_view_state_api_impl(teacher_id, deps=core._session_history_api_deps())

    @router.put("/teacher/session/view-state")
    async def update_teacher_session_view_state(req: dict):
        return core._update_teacher_session_view_state_api_impl(req, deps=core._session_history_api_deps())

    @router.get("/teacher/history/session")
    async def teacher_history_session(
        session_id: str,
        teacher_id: Optional[str] = None,
        cursor: int = -1,
        limit: int = 50,
        direction: str = "backward",
    ):
        try:
            return core._teacher_history_session_api_impl(
                session_id,
                teacher_id,
                cursor=cursor,
                limit=limit,
                direction=direction,
                deps=core._session_history_api_deps(),
            )
        except core.SessionHistoryApiError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)

    @router.get("/teacher/memory/proposals")
    async def teacher_memory_proposals(teacher_id: Optional[str] = None, status: Optional[str] = None, limit: int = 20):
        result = core._list_teacher_memory_proposals_api_impl(
            teacher_id,
            status=status,
            limit=limit,
            deps=core._teacher_memory_api_deps(),
        )
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result.get("error") or "invalid_request")
        return result

    @router.get("/teacher/memory/insights")
    async def teacher_memory_insights_api(teacher_id: Optional[str] = None, days: int = 14):
        teacher_id_final = core.resolve_teacher_id(teacher_id)
        return core.teacher_memory_insights(teacher_id_final, days=days)

    @router.post("/teacher/memory/proposals/{proposal_id}/review")
    async def teacher_memory_proposal_review(proposal_id: str, req: TeacherMemoryProposalReviewRequest):
        result = core._review_teacher_memory_proposal_api_impl(
            proposal_id,
            teacher_id=req.teacher_id,
            approve=bool(req.approve),
            deps=core._teacher_memory_api_deps(),
        )
        if result.get("error"):
            code = 404 if str(result.get("error")) == "proposal not found" else 400
            raise HTTPException(status_code=code, detail=result.get("error"))
        return result

    @router.get("/teacher/llm-routing")
    async def teacher_llm_routing(
        teacher_id: Optional[str] = None,
        history_limit: int = 20,
        proposal_limit: int = 20,
        proposal_status: Optional[str] = None,
    ):
        result = core._get_routing_api_impl(
            {
                "teacher_id": teacher_id,
                "history_limit": history_limit,
                "proposal_limit": proposal_limit,
                "proposal_status": proposal_status,
            },
            deps=core._teacher_routing_api_deps(),
        )
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result)
        return result

    @router.post("/teacher/llm-routing/simulate")
    async def teacher_llm_routing_simulate_api(req: RoutingSimulateRequest):
        result = core.teacher_llm_routing_simulate(core.model_dump_compat(req, exclude_none=True))
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result)
        return result

    @router.post("/teacher/llm-routing/proposals")
    async def teacher_llm_routing_proposals_api(req: RoutingProposalCreateRequest):
        result = core.teacher_llm_routing_propose(core.model_dump_compat(req, exclude_none=True))
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result)
        return result

    @router.get("/teacher/llm-routing/proposals/{proposal_id}")
    async def teacher_llm_routing_proposal_api(proposal_id: str, teacher_id: Optional[str] = None):
        result = core.teacher_llm_routing_proposal_get({"proposal_id": proposal_id, "teacher_id": teacher_id})
        if not result.get("ok"):
            status_code = 404 if str(result.get("error") or "").strip() == "proposal_not_found" else 400
            raise HTTPException(status_code=status_code, detail=result)
        return result

    @router.post("/teacher/llm-routing/proposals/{proposal_id}/review")
    async def teacher_llm_routing_proposal_review_api(proposal_id: str, req: RoutingProposalReviewRequest):
        payload = core.model_dump_compat(req, exclude_none=True)
        payload["proposal_id"] = proposal_id
        result = core.teacher_llm_routing_apply(payload)
        if not result.get("ok"):
            status_code = 404 if str(result.get("error") or "").strip() == "proposal_not_found" else 400
            raise HTTPException(status_code=status_code, detail=result)
        return result

    @router.post("/teacher/llm-routing/rollback")
    async def teacher_llm_routing_rollback_api(req: RoutingRollbackRequest):
        result = core.teacher_llm_routing_rollback(core.model_dump_compat(req, exclude_none=True))
        if not result.get("ok"):
            status_code = 404 if str(result.get("error") or "").strip() in {"history_not_found", "target_version_not_found"} else 400
            raise HTTPException(status_code=status_code, detail=result)
        return result

    @router.get("/teacher/provider-registry")
    async def teacher_provider_registry_api(teacher_id: Optional[str] = None):
        result = core.teacher_provider_registry_get({"teacher_id": teacher_id})
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result)
        return result

    @router.post("/teacher/provider-registry/providers")
    async def teacher_provider_registry_create_api(req: TeacherProviderRegistryCreateRequest):
        result = core.teacher_provider_registry_create(core.model_dump_compat(req, exclude_none=True))
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result)
        return result

    @router.patch("/teacher/provider-registry/providers/{provider_id}")
    async def teacher_provider_registry_update_api(provider_id: str, req: TeacherProviderRegistryUpdateRequest):
        payload = core.model_dump_compat(req, exclude_none=True)
        payload["provider_id"] = provider_id
        result = core.teacher_provider_registry_update(payload)
        if not result.get("ok"):
            status_code = 404 if str(result.get("error") or "").strip() == "provider_not_found" else 400
            raise HTTPException(status_code=status_code, detail=result)
        return result

    @router.delete("/teacher/provider-registry/providers/{provider_id}")
    async def teacher_provider_registry_delete_api(provider_id: str, req: TeacherProviderRegistryDeleteRequest):
        payload = core.model_dump_compat(req, exclude_none=True)
        payload["provider_id"] = provider_id
        result = core.teacher_provider_registry_delete(payload)
        if not result.get("ok"):
            status_code = 404 if str(result.get("error") or "").strip() == "provider_not_found" else 400
            raise HTTPException(status_code=status_code, detail=result)
        return result

    @router.post("/teacher/provider-registry/providers/{provider_id}/probe-models")
    async def teacher_provider_registry_probe_models_api(provider_id: str, req: TeacherProviderRegistryProbeRequest):
        payload = core.model_dump_compat(req, exclude_none=True)
        payload["provider_id"] = provider_id
        result = core.teacher_provider_registry_probe_models(payload)
        if not result.get("ok"):
            status_code = 404 if str(result.get("error") or "").strip() == "provider_not_found" else 400
            raise HTTPException(status_code=status_code, detail=result)
        return result

    return router
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_teacher_routes.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add services/api/routes/teacher_routes.py tests/test_teacher_routes.py
git commit -m "feat: add teacher routes module"
```

### Task 6: Add misc routes

**Files:**
- Create: `services/api/routes/misc_routes.py`
- Test: `tests/test_misc_routes.py`

**Step 1: Write the failing test**

```python
from services.api.routes import misc_routes


def _has_route(router, method, path):
    return any(
        path == route.path and method in (route.methods or set())
        for route in router.routes
    )


def test_misc_routes_build_router():
    router = misc_routes.build_router(object())
    assert _has_route(router, "GET", "/health")
    assert _has_route(router, "POST", "/upload")
    assert _has_route(router, "GET", "/lessons")
    assert _has_route(router, "GET", "/skills")
    assert _has_route(router, "GET", "/charts/{run_id}/{file_name}")
    assert _has_route(router, "GET", "/chart-runs/{run_id}/meta")
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_misc_routes.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'services.api.routes.misc_routes'`.

**Step 3: Write minimal implementation**

Create `services/api/routes/misc_routes.py`:

```python
from __future__ import annotations

import json

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse


def build_router(core) -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    async def health():
        return {"status": "ok"}

    @router.post("/upload")
    async def upload(files: list[UploadFile] = File(...)):
        return await core._upload_files_api_impl(files, deps=core._student_ops_api_deps())

    @router.get("/lessons")
    async def lessons():
        return core.list_lessons()

    @router.get("/skills")
    async def skills():
        return core.list_skills()

    @router.get("/charts/{run_id}/{file_name}")
    async def chart_image_file(run_id: str, file_name: str):
        path = core.resolve_chart_image_path(core.UPLOADS_DIR, run_id, file_name)
        if not path:
            raise HTTPException(status_code=404, detail="chart file not found")
        return FileResponse(path)

    @router.get("/chart-runs/{run_id}/meta")
    async def chart_run_meta(run_id: str):
        path = core.resolve_chart_run_meta_path(core.UPLOADS_DIR, run_id)
        if not path:
            raise HTTPException(status_code=404, detail="chart run not found")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            raise HTTPException(status_code=500, detail="failed to read chart run meta")

    return router
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_misc_routes.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add services/api/routes/misc_routes.py tests/test_misc_routes.py
git commit -m "feat: add misc routes module"
```

### Task 7: Update app_routes to include routers

**Files:**
- Modify: `services/api/app_routes.py`
- Test: `tests/test_app_routes_registration.py`

**Step 1: Write the failing test**

```python
from fastapi import APIRouter, FastAPI

from services.api import app_routes
from services.api.routes import assignment_routes


class DummyCore:
    pass


def test_register_routes_includes_assignment_router():
    app = FastAPI()
    called = {}

    def fake_build(core):
        called["core"] = core
        router = APIRouter()

        @router.get("/__assignment_probe")
        async def probe():
            return {"ok": True}

        return router

    original = assignment_routes.build_router
    assignment_routes.build_router = fake_build
    try:
        app_routes.register_routes(app, DummyCore())
    finally:
        assignment_routes.build_router = original

    assert called.get("core").__class__ is DummyCore
    assert any(route.path == "/__assignment_probe" for route in app.router.routes)
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_app_routes_registration.py -v`
Expected: FAIL because `register_routes` does not include routers yet.

**Step 3: Write minimal implementation**

Update `services/api/app_routes.py` to use `include_router`:

```python
from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from .routes.assignment_routes import build_router as build_assignment_router
from .routes.chat_routes import build_router as build_chat_router
from .routes.exam_routes import build_router as build_exam_router
from .routes.misc_routes import build_router as build_misc_router
from .routes.student_routes import build_router as build_student_router
from .routes.teacher_routes import build_router as build_teacher_router


def register_routes(app: FastAPI, core: Any) -> None:
    if core is None:
        @app.get("/health")
        async def health():
            return {"status": "ok"}

        return

    app.include_router(build_misc_router(core))
    app.include_router(build_chat_router(core))
    app.include_router(build_student_router(core))
    app.include_router(build_teacher_router(core))
    app.include_router(build_exam_router(core))
    app.include_router(build_assignment_router(core))
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_app_routes_registration.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add services/api/app_routes.py tests/test_app_routes_registration.py
git commit -m "refactor: register api routes via routers"
```

### Task 8: Remove route functions from app_core

**Files:**
- Modify: `services/api/app_core.py`

**Step 1: Remove the route functions now living in routes modules**

Remove these function definitions from `services/api/app_core.py` (leave helper and deps builders intact):

- `health`
- `chat`, `chat_start`, `chat_status`
- `student_history_sessions`, `student_session_view_state`, `update_student_session_view_state`, `student_history_session`
- `teacher_history_sessions`, `teacher_session_view_state`, `update_teacher_session_view_state`, `teacher_history_session`
- `teacher_memory_proposals`, `teacher_memory_insights_api`, `teacher_memory_proposal_review`
- `upload`, `get_profile`, `update_profile`, `import_students`, `verify_student`, `submit`
- `exams`, `exam_detail`, `exam_analysis`, `exam_students`, `exam_student`, `exam_question`
- `assignments`, `teacher_assignment_progress`, `teacher_assignments_progress`
- `assignment_requirements`, `assignment_requirements_get`, `assignment_upload`
- `exam_upload_start`, `exam_upload_status`, `exam_upload_draft`, `exam_upload_draft_save`, `exam_upload_confirm`
- `assignment_upload_start`, `assignment_upload_status`, `assignment_upload_draft`, `assignment_upload_draft_save`, `assignment_upload_confirm`
- `assignment_download`, `assignment_today`, `assignment_detail`
- `lessons`, `skills`, `chart_image_file`, `chart_run_meta`
- `teacher_llm_routing`, `teacher_llm_routing_simulate_api`, `teacher_llm_routing_proposals_api`, `teacher_llm_routing_proposal_api`, `teacher_llm_routing_proposal_review_api`, `teacher_llm_routing_rollback_api`
- `teacher_provider_registry_api`, `teacher_provider_registry_create_api`, `teacher_provider_registry_update_api`, `teacher_provider_registry_delete_api`, `teacher_provider_registry_probe_models_api`
- `generate_assignment`, `render_assignment`, `assignment_questions_ocr`

**Step 2: Run a focused regression subset**

Run:
`python3 -m pytest tests/test_chat_route_flow.py tests/test_student_history_flow.py tests/test_upload_draft_flow.py tests/test_llm_routing_endpoints.py -v`

Expected: PASS.

**Step 3: Commit**

```bash
git add services/api/app_core.py
git commit -m "refactor: move http routes out of app_core"
```

### Task 9: Regression sweep

**Step 1: Run route module tests together**

Run:
`python3 -m pytest tests/test_assignment_routes.py tests/test_exam_routes.py tests/test_chat_routes.py tests/test_student_routes.py tests/test_teacher_routes.py tests/test_misc_routes.py tests/test_app_routes_registration.py -v`

Expected: PASS.

**Step 2: Commit (if needed)**

Only if any last adjustments were required:

```bash
git add services/api tests

git commit -m "test: update route modularization coverage"
```
