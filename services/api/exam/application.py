from __future__ import annotations

from typing import Any, Optional

from fastapi import UploadFile

from ..api_models import ExamUploadConfirmRequest, ExamUploadDraftSaveRequest
from .deps import ExamApplicationDeps


def list_exams(*, deps: ExamApplicationDeps) -> Any:
    return deps.list_exams()


def get_exam_detail(exam_id: str, *, deps: ExamApplicationDeps) -> Any:
    return deps.get_exam_detail_api(exam_id)


def get_exam_analysis(exam_id: str, *, deps: ExamApplicationDeps) -> Any:
    return deps.exam_analysis_get(exam_id)


def list_exam_students(exam_id: str, *, limit: int, deps: ExamApplicationDeps) -> Any:
    return deps.exam_students_list(exam_id, int(limit))


def get_exam_student_detail(exam_id: str, *, student_id: str, deps: ExamApplicationDeps) -> Any:
    return deps.exam_student_detail(exam_id, student_id)


def get_exam_question_detail(exam_id: str, *, question_id: str, deps: ExamApplicationDeps) -> Any:
    return deps.exam_question_detail(exam_id, question_id)


async def start_exam_upload(
    *,
    exam_id: Optional[str],
    date: Optional[str],
    class_name: Optional[str],
    paper_files: list[UploadFile],
    score_files: list[UploadFile],
    answer_files: Optional[list[UploadFile]],
    ocr_mode: Optional[str],
    language: Optional[str],
    deps: ExamApplicationDeps,
) -> Any:
    return await deps.exam_upload_start(
        exam_id=exam_id,
        date=date,
        class_name=class_name,
        paper_files=paper_files,
        score_files=score_files,
        answer_files=answer_files,
        ocr_mode=ocr_mode,
        language=language,
    )


async def get_exam_upload_status(job_id: str, *, deps: ExamApplicationDeps) -> Any:
    return await deps.exam_upload_status(job_id)


async def get_exam_upload_draft(job_id: str, *, deps: ExamApplicationDeps) -> Any:
    return await deps.exam_upload_draft(job_id)


async def save_exam_upload_draft(req: ExamUploadDraftSaveRequest, *, deps: ExamApplicationDeps) -> Any:
    return await deps.exam_upload_draft_save(req)


async def confirm_exam_upload(req: ExamUploadConfirmRequest, *, deps: ExamApplicationDeps) -> Any:
    return await deps.exam_upload_confirm(req)
