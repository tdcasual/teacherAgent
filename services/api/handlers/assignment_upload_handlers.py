from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Callable, Optional

from fastapi import HTTPException, UploadFile

from ..api_models import UploadConfirmRequest, UploadDraftSaveRequest
from ..assignment_upload_confirm_gate_service import AssignmentUploadConfirmGateError
from ..assignment_upload_confirm_service import AssignmentUploadConfirmError
from ..assignment_upload_draft_save_service import AssignmentUploadDraftSaveError
from ..assignment_upload_query_service import AssignmentUploadQueryError
from ..assignment_upload_start_service import AssignmentUploadStartError
from ..auth_service import AuthError, enforce_upload_job_access


@dataclass
class AssignmentUploadHandlerDeps:
    start_assignment_upload: Callable[..., Any]
    assignment_upload_status: Callable[[str], Any]
    assignment_upload_draft: Callable[[str], Any]
    assignment_upload_draft_save: Callable[..., Any]
    load_upload_job: Callable[[str], Any]
    ensure_assignment_upload_confirm_ready: Callable[[Any], Any]
    confirm_assignment_upload: Callable[..., Any]
    upload_job_path: Callable[[str], Any]
    finalize_published_from_folder: Callable[..., Any]
    save_assignment_folder_draft: Callable[..., Any]
    get_assignment_folder_draft: Callable[..., Any]


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def assignment_upload_start(
    *,
    assignment_id: str,
    date: str,
    due_at: str,
    subject_id: str,
    scope: str,
    class_name: str,
    student_ids: str,
    files: list[UploadFile],
    answer_files: Optional[list[UploadFile]],
    ocr_mode: str,
    language: str,
    deps: AssignmentUploadHandlerDeps,
    assignment_kind: str = "",
) -> Any:
    try:
        return await _maybe_await(
            deps.start_assignment_upload(
                assignment_id=assignment_id,
                date=date,
                due_at=due_at,
                subject_id=subject_id,
                scope=scope,
                class_name=class_name,
                student_ids=student_ids,
                files=files,
                answer_files=answer_files,
                ocr_mode=ocr_mode,
                language=language,
                assignment_kind=assignment_kind,
            )
        )
    except AssignmentUploadStartError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


async def assignment_upload_status(job_id: str, *, deps: AssignmentUploadHandlerDeps) -> Any:
    try:
        return await _maybe_await(deps.assignment_upload_status(job_id))
    except AssignmentUploadQueryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


async def assignment_upload_draft(job_id: str, *, deps: AssignmentUploadHandlerDeps) -> Any:
    try:
        return await _maybe_await(deps.assignment_upload_draft(job_id))
    except AssignmentUploadQueryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


def _locator_ids(req: Any) -> tuple[str, str]:
    job_id = str(getattr(req, "job_id", None) or "").strip()
    assignment_id = str(getattr(req, "assignment_id", None) or "").strip()
    return job_id, assignment_id


async def assignment_upload_draft_save(
    req: UploadDraftSaveRequest, *, deps: AssignmentUploadHandlerDeps
) -> Any:
    job_id, assignment_id = _locator_ids(req)
    if not job_id and not assignment_id:
        raise HTTPException(status_code=400, detail="job_or_assignment_required")
    try:
        if assignment_id and not job_id:
            return await _maybe_await(
                deps.save_assignment_folder_draft(
                    assignment_id,
                    req.requirements,
                    req.questions,
                )
            )
        return await _maybe_await(
            deps.assignment_upload_draft_save(
                job_id,
                req.requirements,
                req.questions,
                deps=None,
            )
        )
    except AssignmentUploadDraftSaveError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


async def assignment_folder_draft(assignment_id: str, *, deps: AssignmentUploadHandlerDeps) -> Any:
    try:
        return await _maybe_await(deps.get_assignment_folder_draft(assignment_id))
    except AssignmentUploadQueryError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


async def assignment_upload_confirm(
    req: UploadConfirmRequest, *, deps: AssignmentUploadHandlerDeps
) -> Any:
    job_id, assignment_id = _locator_ids(req)
    if not job_id and not assignment_id:
        raise HTTPException(status_code=400, detail="job_or_assignment_required")
    strict = True if req.strict_requirements is None else bool(req.strict_requirements)
    if assignment_id and not job_id:
        try:
            return await _maybe_await(
                deps.finalize_published_from_folder(
                    assignment_id,
                    requirements_override=req.requirements_override,
                    completion_policy_override=req.completion_policy_override,
                    strict_requirements=strict,
                )
            )
        except AssignmentUploadConfirmError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    try:
        job = deps.load_upload_job(job_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="job not found")
    try:
        enforce_upload_job_access(job)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)

    try:
        ready = deps.ensure_assignment_upload_confirm_ready(job)
    except AssignmentUploadConfirmGateError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    if ready is not None:
        return ready

    job_dir = deps.upload_job_path(job_id)
    try:
        return await _maybe_await(
            deps.confirm_assignment_upload(
                job_id,
                job,
                job_dir,
                requirements_override=req.requirements_override,
                strict_requirements=strict,
                completion_policy_override=req.completion_policy_override,
                deps=None,
            )
        )
    except AssignmentUploadConfirmError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
