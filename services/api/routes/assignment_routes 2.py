from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, File, Form, UploadFile

from ..api_models import AssignmentRequirementsRequest, UploadConfirmRequest, UploadDraftSaveRequest
from ..assignment import application as assignment_application
from ..assignment import deps as assignment_deps


def build_router(core) -> APIRouter:
    router = APIRouter()
    app_deps = assignment_deps.build_assignment_application_deps(core)

    @router.get("/assignments")
    async def assignments():
        return await assignment_application.list_assignments(deps=app_deps)

    @router.get("/teacher/assignment/progress")
    async def teacher_assignment_progress(assignment_id: str, include_students: bool = True):
        return await assignment_application.get_teacher_assignment_progress(
            assignment_id,
            include_students=include_students,
            deps=app_deps,
        )

    @router.get("/teacher/assignments/progress")
    async def teacher_assignments_progress(date: Optional[str] = None):
        return await assignment_application.get_teacher_assignments_progress(
            date=date,
            deps=app_deps,
        )

    @router.post("/assignment/requirements")
    async def assignment_requirements(req: AssignmentRequirementsRequest):
        return await assignment_application.post_assignment_requirements(req, deps=app_deps)

    @router.get("/assignment/{assignment_id}/requirements")
    async def assignment_requirements_get(assignment_id: str):
        return await assignment_application.get_assignment_requirements(
            assignment_id, deps=app_deps
        )

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
        return await assignment_application.upload_assignment_legacy(
            assignment_id=assignment_id,
            date=date,
            scope=scope,
            class_name=class_name,
            student_ids=student_ids,
            files=files,
            answer_files=answer_files,
            ocr_mode=ocr_mode,
            language=language,
            deps=app_deps,
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
        return await assignment_application.upload_assignment_start(
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
            deps=app_deps,
        )

    @router.get("/assignment/upload/status")
    async def assignment_upload_status(job_id: str):
        return await assignment_application.get_assignment_upload_status(job_id, deps=app_deps)

    @router.get("/assignment/upload/draft")
    async def assignment_upload_draft(job_id: str):
        return await assignment_application.get_assignment_upload_draft(job_id, deps=app_deps)

    @router.post("/assignment/upload/draft/save")
    async def assignment_upload_draft_save(req: UploadDraftSaveRequest):
        return await assignment_application.save_assignment_upload_draft(req, deps=app_deps)

    @router.post("/assignment/upload/confirm")
    async def assignment_upload_confirm(req: UploadConfirmRequest):
        return await assignment_application.confirm_assignment_upload(req, deps=app_deps)

    @router.get("/assignment/{assignment_id}/download")
    async def assignment_download(assignment_id: str, file: str):
        return await assignment_application.download_assignment_file(
            assignment_id,
            file,
            deps=app_deps,
        )

    @router.get("/assignment/today")
    async def assignment_today(
        student_id: str,
        date: Optional[str] = None,
        auto_generate: bool = False,
        generate: bool = True,
        per_kp: int = 5,
    ):
        return await assignment_application.get_assignment_today(
            student_id=student_id,
            date=date,
            auto_generate=auto_generate,
            generate=generate,
            per_kp=per_kp,
            deps=app_deps,
        )

    @router.get("/assignment/{assignment_id}")
    async def assignment_detail(assignment_id: str):
        return await assignment_application.get_assignment_detail(assignment_id, deps=app_deps)

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
        return await assignment_application.post_generate_assignment(
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
            deps=app_deps,
        )

    @router.post("/assignment/render")
    async def render_assignment(assignment_id: str = Form(...)):
        return await assignment_application.post_render_assignment(assignment_id, deps=app_deps)

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
        return await assignment_application.post_assignment_questions_ocr(
            assignment_id=assignment_id,
            files=files,
            kp_id=kp_id,
            difficulty=difficulty,
            tags=tags,
            ocr_mode=ocr_mode,
            language=language,
            deps=app_deps,
        )

    return router
