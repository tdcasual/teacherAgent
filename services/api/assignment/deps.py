from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Optional

from ..api_models import AssignmentRequirementsRequest, UploadConfirmRequest, UploadDraftSaveRequest
from ..wiring.assignment_wiring import (
    _assignment_handlers_deps,
    _assignment_io_handlers_deps,
    _assignment_upload_handlers_deps,
)


def _student_enrolled_for_core(
    core: Any, student_id: str, teacher_id: str, subject_id: str, class_name: str = ""
) -> bool:
    from ..assignment_student_list_service import student_currently_enrolled

    data_dir = getattr(core, "DATA_DIR", None)
    return student_currently_enrolled(
        student_id, teacher_id, subject_id, data_dir=data_dir, class_name=class_name
    )


def _sql_visibility_for_core(core: Any, assignment_id: str) -> str:
    from .store import assignment_sql_visibility

    data_dir = getattr(core, "DATA_DIR", None)
    if data_dir is None:
        return ""
    return assignment_sql_visibility(Path(data_dir), assignment_id)


@dataclass(frozen=True, kw_only=True)
class AssignmentAccessDeps:
    resolve_assignment_dir: Callable[[str], Path]
    load_assignment_meta: Callable[[Path], Dict[str, Any]]
    resolve_student_profile_path: Callable[[str], Path]
    load_profile_file: Callable[[Path], Dict[str, Any]]
    assignment_specificity: Callable[[Dict[str, Any], Optional[str], Optional[str]], int]
    student_enrolled: Callable[..., bool]
    sql_visibility: Optional[Callable[[str], str]] = None


@dataclass(frozen=True, kw_only=True)
class AssignmentApplicationDeps(AssignmentAccessDeps):
    list_assignments: Callable[..., Awaitable[Dict[str, Any]]]
    teacher_assignment_progress: Callable[[str, bool], Awaitable[Dict[str, Any]]]
    teacher_assignments_progress: Callable[..., Awaitable[Dict[str, Any]]]
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
    def _teacher_assignments_progress(
        date: Optional[str] = None, owner_teacher_id: Optional[str] = None
    ) -> Awaitable[Dict[str, Any]]:
        return core.assignment_handlers.teacher_assignments_progress(
            date=date,
            owner_teacher_id=owner_teacher_id,
            deps=_assignment_handlers_deps(),
        )

    return AssignmentApplicationDeps(
        resolve_assignment_dir=lambda assignment_id: core.resolve_assignment_dir(assignment_id),
        load_assignment_meta=lambda folder: core.load_assignment_meta(folder),
        resolve_student_profile_path=lambda student_id: core.resolve_student_profile_path(
            student_id
        ),
        load_profile_file=lambda path: core.load_profile_file(path),
        assignment_specificity=lambda meta, student_id, class_name: core.assignment_specificity(
            meta, student_id, class_name
        ),
        student_enrolled=lambda student_id, teacher_id, subject_id, class_name="": (
            _student_enrolled_for_core(core, student_id, teacher_id, subject_id, class_name)
        ),
        sql_visibility=lambda assignment_id: _sql_visibility_for_core(core, assignment_id),
        list_assignments=lambda limit, cursor, owner_teacher_id=None: (
            core.assignment_handlers.assignments(
                limit=limit,
                cursor=cursor,
                owner_teacher_id=owner_teacher_id,
                deps=_assignment_handlers_deps(),
            )
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
