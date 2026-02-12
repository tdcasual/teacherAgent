from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..api_models import ExamUploadConfirmRequest, ExamUploadDraftSaveRequest


def build_router(core) -> APIRouter:
    router = APIRouter()

    @router.get("/exams")
    def exams():
        return core.list_exams()

    @router.get("/exam/{exam_id}")
    def exam_detail(exam_id: str):
        result = core._get_exam_detail_api_impl(exam_id, deps=core._exam_api_deps())
        if result.get("error") == "exam_not_found":
            raise HTTPException(status_code=404, detail="exam not found")
        if result.get("error"):
            raise HTTPException(status_code=400, detail=result)
        return result

    @router.get("/exam/{exam_id}/analysis")
    def exam_analysis(exam_id: str):
        result = core.exam_analysis_get(exam_id)
        if result.get("error") == "exam_not_found":
            raise HTTPException(status_code=404, detail="exam not found")
        if result.get("error"):
            raise HTTPException(status_code=400, detail=result)
        return result

    @router.get("/exam/{exam_id}/students")
    def exam_students(exam_id: str, limit: int = 50):
        result = core.exam_students_list(exam_id, limit=limit)
        if result.get("error") == "exam_not_found":
            raise HTTPException(status_code=404, detail="exam not found")
        if result.get("error"):
            raise HTTPException(status_code=400, detail=result)
        return result

    @router.get("/exam/{exam_id}/student/{student_id}")
    def exam_student(exam_id: str, student_id: str):
        result = core.exam_student_detail(exam_id, student_id=student_id)
        if result.get("error") == "exam_not_found":
            raise HTTPException(status_code=404, detail="exam not found")
        if result.get("error"):
            raise HTTPException(status_code=400, detail=result)
        return result

    @router.get("/exam/{exam_id}/question/{question_id}")
    def exam_question(exam_id: str, question_id: str):
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
