from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..api_models import UploadConfirmRequest, UploadDraftSaveRequest
from ..auth_service import AuthError, require_principal


def _require_teacher_or_admin() -> None:
    try:
        require_principal(roles=("teacher", "admin"))
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


def register_assignment_upload_routes(
    router: APIRouter, *, app_deps: Any, assignment_app: Any
) -> None:
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
    ) -> Any:
        _require_teacher_or_admin()
        return await assignment_app.upload_assignment_legacy(
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
    ) -> Any:
        _require_teacher_or_admin()
        return await assignment_app.upload_assignment_start(
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
    async def assignment_upload_status(job_id: str) -> Any:
        _require_teacher_or_admin()
        return await assignment_app.get_assignment_upload_status(job_id, deps=app_deps)

    @router.get("/assignment/upload/draft")
    async def assignment_upload_draft(job_id: str) -> Any:
        _require_teacher_or_admin()
        return await assignment_app.get_assignment_upload_draft(job_id, deps=app_deps)

    @router.post("/assignment/upload/draft/save")
    async def assignment_upload_draft_save(req: UploadDraftSaveRequest) -> Any:
        _require_teacher_or_admin()
        return await assignment_app.save_assignment_upload_draft(req, deps=app_deps)

    @router.post("/assignment/upload/confirm")
    async def assignment_upload_confirm(req: UploadConfirmRequest) -> Any:
        _require_teacher_or_admin()
        return await assignment_app.confirm_assignment_upload(req, deps=app_deps)
