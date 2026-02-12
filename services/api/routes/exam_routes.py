from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..api_models import ExamUploadConfirmRequest, ExamUploadDraftSaveRequest
from ..exam import application as exam_application
from ..exam import deps as exam_deps


def build_router(core) -> APIRouter:
    router = APIRouter()
    app_deps = exam_deps.build_exam_application_deps(core)

    @router.get("/exams")
    async def exams():
        return exam_application.list_exams(deps=app_deps)

    @router.get("/exam/{exam_id}")
    async def exam_detail(exam_id: str):
        result = exam_application.get_exam_detail(exam_id, deps=app_deps)
        if result.get("error") == "exam_not_found":
            raise HTTPException(status_code=404, detail="exam not found")
        if result.get("error"):
            raise HTTPException(status_code=400, detail=result)
        return result

    @router.get("/exam/{exam_id}/analysis")
    async def exam_analysis(exam_id: str):
        result = exam_application.get_exam_analysis(exam_id, deps=app_deps)
        if result.get("error") == "exam_not_found":
            raise HTTPException(status_code=404, detail="exam not found")
        if result.get("error"):
            raise HTTPException(status_code=400, detail=result)
        return result

    @router.get("/exam/{exam_id}/students")
    async def exam_students(exam_id: str, limit: int = 50):
        result = exam_application.list_exam_students(exam_id, limit=limit, deps=app_deps)
        if result.get("error") == "exam_not_found":
            raise HTTPException(status_code=404, detail="exam not found")
        if result.get("error"):
            raise HTTPException(status_code=400, detail=result)
        return result

    @router.get("/exam/{exam_id}/student/{student_id}")
    async def exam_student(exam_id: str, student_id: str):
        result = exam_application.get_exam_student_detail(
            exam_id, student_id=student_id, deps=app_deps
        )
        if result.get("error") == "exam_not_found":
            raise HTTPException(status_code=404, detail="exam not found")
        if result.get("error"):
            raise HTTPException(status_code=400, detail=result)
        return result

    @router.get("/exam/{exam_id}/question/{question_id}")
    async def exam_question(exam_id: str, question_id: str):
        result = exam_application.get_exam_question_detail(
            exam_id, question_id=question_id, deps=app_deps
        )
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
        return await exam_application.start_exam_upload(
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
    async def exam_upload_status(job_id: str):
        return await exam_application.get_exam_upload_status(job_id, deps=app_deps)

    @router.get("/exam/upload/draft")
    async def exam_upload_draft(job_id: str):
        return await exam_application.get_exam_upload_draft(job_id, deps=app_deps)

    @router.post("/exam/upload/draft/save")
    async def exam_upload_draft_save(req: ExamUploadDraftSaveRequest):
        return await exam_application.save_exam_upload_draft(req, deps=app_deps)

    @router.post("/exam/upload/confirm")
    async def exam_upload_confirm(req: ExamUploadConfirmRequest):
        return await exam_application.confirm_exam_upload(req, deps=app_deps)

    return router
