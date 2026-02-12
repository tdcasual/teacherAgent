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


async def _call_exam_api(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    try:
        return await _maybe_await(fn(*args, **kwargs))
    except ExamUploadApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


async def exam_upload_start(
    *,
    exam_id: str,
    date: str,
    class_name: str,
    paper_files: Any,
    score_files: Any,
    answer_files: Any,
    ocr_mode: str,
    language: str,
    deps: ExamUploadHandlerDeps,
) -> Any:
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
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


async def exam_upload_status(job_id: str, *, deps: ExamUploadHandlerDeps) -> Any:
    return await _call_exam_api(deps.exam_upload_status, job_id)


async def exam_upload_draft(job_id: str, *, deps: ExamUploadHandlerDeps) -> Any:
    return await _call_exam_api(deps.exam_upload_draft, job_id)


async def exam_upload_draft_save(req: ExamUploadDraftSaveRequest, *, deps: ExamUploadHandlerDeps) -> Any:
    return await _call_exam_api(
        deps.exam_upload_draft_save,
        job_id=req.job_id,
        meta=req.meta,
        questions=req.questions,
        score_schema=req.score_schema,
        answer_key_text=req.answer_key_text,
        reparse=bool(req.reparse),
    )


async def exam_upload_confirm(req: ExamUploadConfirmRequest, *, deps: ExamUploadHandlerDeps) -> Any:
    return await _call_exam_api(deps.exam_upload_confirm, req.job_id)
