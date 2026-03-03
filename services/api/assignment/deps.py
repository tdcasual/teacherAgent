from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Optional

from ..api_models import AssignmentRequirementsRequest, UploadConfirmRequest, UploadDraftSaveRequest
from ..wiring.assignment_wiring import (
    _assignment_handlers_deps,
    _assignment_io_handlers_deps,
    _assignment_upload_handlers_deps,
)


@dataclass(frozen=True)
class AssignmentApplicationDeps:
    list_assignments: Callable[[int, int], Awaitable[Dict[str, Any]]]
    teacher_assignment_progress: Callable[[str, bool], Awaitable[Dict[str, Any]]]
    teacher_assignments_progress: Callable[[Optional[str]], Awaitable[Dict[str, Any]]]
    assignment_requirements: Callable[[AssignmentRequirementsRequest], Awaitable[Dict[str, Any]]]
    assignment_requirements_get: Callable[[str], Awaitable[Dict[str, Any]]]
    assignment_upload_start: Callable[..., Awaitable[Dict[str, Any]]]
    assignment_upload_status: Callable[[str], Awaitable[Dict[str, Any]]]
    assignment_upload_draft: Callable[[str], Awaitable[Dict[str, Any]]]
    assignment_upload_draft_save: Callable[[UploadDraftSaveRequest], Awaitable[Dict[str, Any]]]
    assignment_upload_confirm: Callable[[UploadConfirmRequest], Awaitable[Dict[str, Any]]]
    assignment_download: Callable[[str, str], Awaitable[Dict[str, Any]]]
    assignment_today: Callable[..., Awaitable[Dict[str, Any]]]
    assignment_detail: Callable[[str], Awaitable[Dict[str, Any]]]
    generate_assignment: Callable[..., Awaitable[Dict[str, Any]]]
    render_assignment: Callable[[str], Awaitable[Dict[str, Any]]]
    assignment_questions_ocr: Callable[..., Awaitable[Dict[str, Any]]]


def build_assignment_application_deps(core: Any) -> AssignmentApplicationDeps:
    def _teacher_assignments_progress(date: Optional[str] = None) -> Awaitable[Dict[str, Any]]:
        return core.assignment_handlers.teacher_assignments_progress(
            date=date,
            deps=_assignment_handlers_deps(),
        )

    return AssignmentApplicationDeps(
        list_assignments=lambda limit, cursor: core.assignment_handlers.assignments(
            limit=limit,
            cursor=cursor,
            deps=_assignment_handlers_deps()
        ),
        teacher_assignment_progress=lambda assignment_id, include_students: core.assignment_handlers.teacher_assignment_progress(
            assignment_id,
            include_students=include_students,
            deps=_assignment_handlers_deps(),
        ),
        teacher_assignments_progress=_teacher_assignments_progress,
        assignment_requirements=lambda req: core.assignment_handlers.assignment_requirements(
            req,
            deps=_assignment_handlers_deps(),
        ),
        assignment_requirements_get=lambda assignment_id: core.assignment_handlers.assignment_requirements_get(
            assignment_id,
            deps=_assignment_handlers_deps(),
        ),
        assignment_upload_start=lambda **kwargs: core.assignment_upload_handlers.assignment_upload_start(
            deps=_assignment_upload_handlers_deps(),
            **kwargs,
        ),
        assignment_upload_status=lambda job_id: core.assignment_upload_handlers.assignment_upload_status(
            job_id,
            deps=_assignment_upload_handlers_deps(),
        ),
        assignment_upload_draft=lambda job_id: core.assignment_upload_handlers.assignment_upload_draft(
            job_id,
            deps=_assignment_upload_handlers_deps(),
        ),
        assignment_upload_draft_save=lambda req: core.assignment_upload_handlers.assignment_upload_draft_save(
            req,
            deps=_assignment_upload_handlers_deps(),
        ),
        assignment_upload_confirm=lambda req: core.assignment_upload_handlers.assignment_upload_confirm(
            req,
            deps=_assignment_upload_handlers_deps(),
        ),
        assignment_download=lambda assignment_id, file: core.assignment_io_handlers.assignment_download(
            assignment_id,
            file,
            deps=_assignment_io_handlers_deps(),
        ),
        assignment_today=lambda **kwargs: core.assignment_handlers.assignment_today(
            deps=_assignment_handlers_deps(),
            **kwargs,
        ),
        assignment_detail=lambda assignment_id: core.assignment_handlers.assignment_detail(
            assignment_id,
            deps=_assignment_handlers_deps(),
        ),
        generate_assignment=lambda **kwargs: core.assignment_io_handlers.generate_assignment(
            deps=_assignment_io_handlers_deps(),
            **kwargs,
        ),
        render_assignment=lambda assignment_id: core.assignment_io_handlers.render_assignment(
            assignment_id,
            deps=_assignment_io_handlers_deps(),
        ),
        assignment_questions_ocr=lambda **kwargs: core.assignment_io_handlers.assignment_questions_ocr(
            deps=_assignment_io_handlers_deps(),
            **kwargs,
        ),
    )
