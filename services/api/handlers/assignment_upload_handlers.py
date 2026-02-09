from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Callable

from fastapi import HTTPException

from ..api_models import UploadConfirmRequest, UploadDraftSaveRequest
from ..assignment_upload_confirm_gate_service import AssignmentUploadConfirmGateError
from ..assignment_upload_confirm_service import AssignmentUploadConfirmError
from ..assignment_upload_draft_save_service import AssignmentUploadDraftSaveError
from ..assignment_upload_legacy_service import AssignmentUploadLegacyError
from ..assignment_upload_query_service import AssignmentUploadQueryError
from ..assignment_upload_start_service import AssignmentUploadStartError


@dataclass
class AssignmentUploadHandlerDeps:
    assignment_upload_legacy: Callable[..., Any]
    start_assignment_upload: Callable[..., Any]
    assignment_upload_status: Callable[[str], Any]
    assignment_upload_draft: Callable[[str], Any]
    assignment_upload_draft_save: Callable[..., Any]
    load_upload_job: Callable[[str], Any]
    ensure_assignment_upload_confirm_ready: Callable[[Any], Any]
    confirm_assignment_upload: Callable[..., Any]
    upload_job_path: Callable[[str], Any]


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def assignment_upload(**kwargs):
    deps: AssignmentUploadHandlerDeps = kwargs.pop("deps")
    try:
        return await _maybe_await(deps.assignment_upload_legacy(**kwargs))
    except AssignmentUploadLegacyError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


async def assignment_upload_start(
    *,
    assignment_id: str,
    date: str,
    due_at: str,
    scope: str,
    class_name: str,
    student_ids: str,
    files,
    answer_files,
    ocr_mode: str,
    language: str,
    deps: AssignmentUploadHandlerDeps,
):
    try:
        return await _maybe_await(
            deps.start_assignment_upload(
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
                deps=None,
            )
        )
    except AssignmentUploadStartError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


async def assignment_upload_status(job_id: str, *, deps: AssignmentUploadHandlerDeps):
    try:
        return await _maybe_await(deps.assignment_upload_status(job_id))
    except AssignmentUploadQueryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


async def assignment_upload_draft(job_id: str, *, deps: AssignmentUploadHandlerDeps):
    try:
        return await _maybe_await(deps.assignment_upload_draft(job_id))
    except AssignmentUploadQueryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


async def assignment_upload_draft_save(req: UploadDraftSaveRequest, *, deps: AssignmentUploadHandlerDeps):
    try:
        return await _maybe_await(
            deps.assignment_upload_draft_save(
                req.job_id,
                req.requirements,
                req.questions,
                deps=None,
            )
        )
    except AssignmentUploadDraftSaveError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


async def assignment_upload_confirm(req: UploadConfirmRequest, *, deps: AssignmentUploadHandlerDeps):
    try:
        job = deps.load_upload_job(req.job_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="job not found")

    try:
        ready = deps.ensure_assignment_upload_confirm_ready(job)
    except AssignmentUploadConfirmGateError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    if ready is not None:
        return ready

    strict = True if req.strict_requirements is None else bool(req.strict_requirements)
    job_dir = deps.upload_job_path(req.job_id)
    try:
        return await _maybe_await(
            deps.confirm_assignment_upload(
                req.job_id,
                job,
                job_dir,
                requirements_override=req.requirements_override,
                strict_requirements=strict,
                deps=None,
            )
        )
    except AssignmentUploadConfirmError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
