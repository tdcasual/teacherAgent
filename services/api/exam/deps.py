from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict

from ..api_models import ExamUploadConfirmRequest, ExamUploadDraftSaveRequest


@dataclass(frozen=True)
class ExamApplicationDeps:
    list_exams: Callable[[int, int], Dict[str, Any]]
    get_exam_detail_api: Callable[[str], Dict[str, Any]]
    exam_analysis_get: Callable[[str], Dict[str, Any]]
    exam_students_list: Callable[[str, int], Dict[str, Any]]
    exam_student_detail: Callable[[str, str], Dict[str, Any]]
    exam_question_detail: Callable[[str, str], Dict[str, Any]]
    exam_upload_start: Callable[..., Awaitable[Dict[str, Any]]]
    exam_upload_status: Callable[[str], Awaitable[Dict[str, Any]]]
    exam_upload_draft: Callable[[str], Awaitable[Dict[str, Any]]]
    exam_upload_draft_save: Callable[[ExamUploadDraftSaveRequest], Awaitable[Dict[str, Any]]]
    exam_upload_confirm: Callable[[ExamUploadConfirmRequest], Awaitable[Dict[str, Any]]]


def build_exam_application_deps(core: Any) -> ExamApplicationDeps:
    def _exam_students_list(exam_id: str, limit: int = 50) -> Dict[str, Any]:
        return core.exam_students_list(exam_id, limit=limit)

    return ExamApplicationDeps(
        list_exams=lambda limit, cursor: core.list_exams(limit=limit, cursor=cursor),
        get_exam_detail_api=lambda exam_id: core._get_exam_detail_api_impl(
            exam_id, deps=core._exam_api_deps()
        ),
        exam_analysis_get=lambda exam_id: core.exam_analysis_get(exam_id),
        exam_students_list=_exam_students_list,
        exam_student_detail=lambda exam_id, student_id: core.exam_student_detail(
            exam_id, student_id=student_id
        ),
        exam_question_detail=lambda exam_id, question_id: core.exam_question_detail(
            exam_id, question_id=question_id
        ),
        exam_upload_start=lambda **kwargs: core.exam_upload_handlers.exam_upload_start(
            deps=core._exam_upload_handlers_deps(),
            **kwargs,
        ),
        exam_upload_status=lambda job_id: core.exam_upload_handlers.exam_upload_status(
            job_id,
            deps=core._exam_upload_handlers_deps(),
        ),
        exam_upload_draft=lambda job_id: core.exam_upload_handlers.exam_upload_draft(
            job_id,
            deps=core._exam_upload_handlers_deps(),
        ),
        exam_upload_draft_save=lambda req: core.exam_upload_handlers.exam_upload_draft_save(
            req,
            deps=core._exam_upload_handlers_deps(),
        ),
        exam_upload_confirm=lambda req: core.exam_upload_handlers.exam_upload_confirm(
            req,
            deps=core._exam_upload_handlers_deps(),
        ),
    )
