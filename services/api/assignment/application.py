from __future__ import annotations

from typing import Any, Optional

from ..api_models import AssignmentRequirementsRequest, UploadConfirmRequest, UploadDraftSaveRequest
from ..auth_service import AuthError, auth_required, require_principal
from .deps import AssignmentAccessDeps, AssignmentApplicationDeps
from .visibility import (
    assignment_owner_id,
    effective_visibility_status,
    snapshot_student_ids,
    student_can_read_assignment,
)


class AssignmentAccessError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = int(status_code)
        self.detail = str(detail or "assignment_access_error")


def listing_owner_teacher_id() -> Optional[str]:
    try:
        principal = require_principal(roles=("teacher", "admin", "service"))
    except AuthError as exc:
        raise AssignmentAccessError(exc.status_code, exc.detail) from exc
    if principal is None:
        return None
    if principal.role in {"admin", "service"}:
        return None
    actor = str(principal.actor_id or "").strip()
    if not actor:
        raise AssignmentAccessError(400, "teacher_id_required")
    return actor


def _require_teacher_owner(actor_id: str, meta: dict) -> None:
    owner = str(meta.get("teacher_id") or "").strip()
    if not owner or owner != actor_id:
        raise AssignmentAccessError(403, "forbidden_assignment_owner")


def _require_student_assignment_access(
    principal: Any, meta: dict, *, deps: AssignmentAccessDeps
) -> None:
    if not student_can_read_assignment(meta):
        raise AssignmentAccessError(403, "forbidden_assignment_scope")
    sid = str(getattr(principal, "actor_id", "") or "").strip()
    if sid not in snapshot_student_ids(meta):
        raise AssignmentAccessError(403, "forbidden_assignment_scope")
    vis = effective_visibility_status(meta)
    if vis == "archived":
        return
    teacher_id = assignment_owner_id(meta)
    subject_id = str(meta.get("subject_id") or "").strip()
    if not teacher_id or not subject_id:
        raise AssignmentAccessError(403, "forbidden_assignment_scope")
    if not deps.student_enrolled(sid, teacher_id, subject_id):
        raise AssignmentAccessError(403, "forbidden_assignment_scope")


def _assignment_principal():
    try:
        return require_principal(roles=("teacher", "student", "admin", "service"))
    except AuthError as exc:
        raise AssignmentAccessError(exc.status_code, exc.detail) from exc


def _missing_folder_access(principal: Any, *, allow_missing: bool) -> None:
    if allow_missing:
        if principal.role == "teacher" and not str(principal.actor_id or "").strip():
            raise AssignmentAccessError(400, "teacher_id_required")
        return
    raise AssignmentAccessError(404, "assignment not found")


def require_assignment_access(
    assignment_id: str, *, deps: AssignmentAccessDeps, allow_missing: bool = False
) -> None:
    if not auth_required():
        return
    principal = _assignment_principal()
    if principal is None or principal.role in {"admin", "service"}:
        return
    try:
        folder = deps.resolve_assignment_dir(assignment_id)
    except ValueError as exc:
        raise AssignmentAccessError(400, str(exc)) from exc
    if not folder.exists():
        _missing_folder_access(principal, allow_missing=allow_missing)
        return
    meta = deps.load_assignment_meta(folder)
    if not isinstance(meta, dict):
        meta = {}
    if principal.role == "teacher":
        actor = str(principal.actor_id or "").strip()
        if not actor:
            raise AssignmentAccessError(400, "teacher_id_required")
        _require_teacher_owner(actor, meta)
        return
    _require_student_assignment_access(principal, meta, deps=deps)


async def list_assignments(
    *, limit: int = 50, cursor: int = 0, deps: AssignmentApplicationDeps
) -> Any:
    owner = listing_owner_teacher_id()
    return await deps.list_assignments(int(limit), int(cursor), owner)


async def get_teacher_assignment_progress(
    assignment_id: str,
    *,
    include_students: bool,
    deps: AssignmentApplicationDeps,
) -> Any:
    require_assignment_access(assignment_id, deps=deps)
    return await deps.teacher_assignment_progress(assignment_id, include_students)


async def get_teacher_assignments_progress(
    *, date: Optional[str], deps: AssignmentApplicationDeps
) -> Any:
    owner = listing_owner_teacher_id()
    return await deps.teacher_assignments_progress(date, owner)


async def post_assignment_requirements(
    req: AssignmentRequirementsRequest, *, deps: AssignmentApplicationDeps
) -> Any:
    require_assignment_access(req.assignment_id, deps=deps, allow_missing=True)
    return await deps.assignment_requirements(req)


async def get_assignment_requirements(
    assignment_id: str, *, deps: AssignmentApplicationDeps
) -> Any:
    require_assignment_access(assignment_id, deps=deps)
    return await deps.assignment_requirements_get(assignment_id)


async def get_assignment_detail(assignment_id: str, *, deps: AssignmentApplicationDeps) -> Any:
    require_assignment_access(assignment_id, deps=deps)
    return await deps.assignment_detail(assignment_id)


async def upload_assignment_start(
    *,
    assignment_id: str,
    date: Optional[str],
    due_at: Optional[str],
    subject_id: Optional[str] = None,
    scope: Optional[str],
    class_name: Optional[str],
    student_ids: Optional[str],
    files: list[Any],
    answer_files: Optional[list[Any]],
    ocr_mode: Optional[str],
    language: Optional[str],
    deps: AssignmentApplicationDeps,
) -> Any:
    require_assignment_access(assignment_id, deps=deps, allow_missing=True)
    return await deps.assignment_upload_start(
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
    )


async def get_assignment_upload_status(job_id: str, *, deps: AssignmentApplicationDeps) -> Any:
    return await deps.assignment_upload_status(job_id)


async def get_assignment_upload_draft(job_id: str, *, deps: AssignmentApplicationDeps) -> Any:
    return await deps.assignment_upload_draft(job_id)


async def save_assignment_upload_draft(
    req: UploadDraftSaveRequest, *, deps: AssignmentApplicationDeps
) -> Any:
    return await deps.assignment_upload_draft_save(req)


async def confirm_assignment_upload(
    req: UploadConfirmRequest, *, deps: AssignmentApplicationDeps
) -> Any:
    return await deps.assignment_upload_confirm(req)


async def download_assignment_file(
    assignment_id: str,
    file: str,
    *,
    deps: AssignmentApplicationDeps,
) -> Any:
    require_assignment_access(assignment_id, deps=deps)
    return await deps.assignment_download(assignment_id, file)


async def get_assignment_today(
    *,
    student_id: str,
    date: Optional[str],
    auto_generate: bool,
    generate: bool,
    per_kp: int,
    deps: AssignmentApplicationDeps,
) -> Any:
    return await deps.assignment_today(
        student_id=student_id,
        date=date,
        auto_generate=auto_generate,
        generate=generate,
        per_kp=per_kp,
    )


async def post_generate_assignment(
    *,
    assignment_id: str,
    kp: str,
    question_ids: Optional[str],
    per_kp: int,
    core_examples: Optional[str],
    generate: bool,
    mode: Optional[str],
    date: Optional[str],
    due_at: Optional[str],
    subject_id: Optional[str] = None,
    class_name: Optional[str],
    student_ids: Optional[str],
    source: Optional[str],
    requirements_json: Optional[str],
    deps: AssignmentApplicationDeps,
) -> Any:
    require_assignment_access(assignment_id, deps=deps, allow_missing=True)
    return await deps.generate_assignment(
        assignment_id=assignment_id,
        kp=kp,
        question_ids=question_ids,
        per_kp=per_kp,
        core_examples=core_examples,
        generate=generate,
        mode=mode,
        date=date,
        due_at=due_at,
        subject_id=subject_id,
        class_name=class_name,
        student_ids=student_ids,
        source=source,
        requirements_json=requirements_json,
    )


async def post_render_assignment(assignment_id: str, *, deps: AssignmentApplicationDeps) -> Any:
    require_assignment_access(assignment_id, deps=deps)
    return await deps.render_assignment(assignment_id)


async def post_assignment_questions_ocr(
    *,
    assignment_id: str,
    files: list[Any],
    kp_id: Optional[str],
    difficulty: Optional[str],
    tags: Optional[str],
    ocr_mode: Optional[str],
    language: Optional[str],
    deps: AssignmentApplicationDeps,
) -> Any:
    require_assignment_access(assignment_id, deps=deps)
    return await deps.assignment_questions_ocr(
        assignment_id=assignment_id,
        files=files,
        kp_id=kp_id,
        difficulty=difficulty,
        tags=tags,
        ocr_mode=ocr_mode,
        language=language,
    )
