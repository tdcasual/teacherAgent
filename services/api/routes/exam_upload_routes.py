from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..api_models import ExamUploadConfirmRequest, ExamUploadDraftSaveRequest
from ..auth_service import AuthError, require_principal


def _require_teacher_or_admin() -> None:
    try:
        require_principal(roles=("teacher", "admin"))
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


def register_exam_upload_routes(router: APIRouter, *, app_deps: Any, exam_app: Any) -> None:
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
    ) -> Any:
        _require_teacher_or_admin()
        return await exam_app.start_exam_upload(
            exam_id=exam_id,
            date=date,
            class_name=class_name,
            paper_files=paper_files,
            score_files=score_files,
            answer_files=answer_files,
            ocr_mode=ocr_mode,
            language=language,
            deps=app_deps,
        )

    @router.get("/exam/upload/status")
    async def exam_upload_status(job_id: str) -> Any:
        _require_teacher_or_admin()
        return await exam_app.get_exam_upload_status(job_id, deps=app_deps)

    @router.get("/exam/upload/draft")
    async def exam_upload_draft(job_id: str) -> Any:
        _require_teacher_or_admin()
        return await exam_app.get_exam_upload_draft(job_id, deps=app_deps)

    @router.post("/exam/upload/draft/save")
    async def exam_upload_draft_save(req: ExamUploadDraftSaveRequest) -> Any:
        _require_teacher_or_admin()
        return await exam_app.save_exam_upload_draft(req, deps=app_deps)

    @router.post("/exam/upload/confirm")
    async def exam_upload_confirm(req: ExamUploadConfirmRequest) -> Any:
        _require_teacher_or_admin()
        return await exam_app.confirm_exam_upload(req, deps=app_deps)
