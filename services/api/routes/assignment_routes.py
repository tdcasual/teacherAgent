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
