from __future__ import annotations

from typing import Any, Optional

from ..api_models import AssignmentRequirementsRequest, UploadConfirmRequest, UploadDraftSaveRequest
from ..auth_service import AuthError, auth_required, require_principal
from .deps import AssignmentAccessDeps, AssignmentApplicationDeps
from .visibility import student_can_read_assignment


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


def _load_assignment_meta(assignment_id: str, *, deps: AssignmentAccessDeps):
    try:
        folder = deps.resolve_assignment_dir(assignment_id)
    except ValueError as exc:
        raise AssignmentAccessError(400, str(exc)) from exc
    if not folder.exists():
        raise AssignmentAccessError(404, "assignment not found")
    meta = deps.load_assignment_meta(folder)
    return meta if isinstance(meta, dict) else {}


def _require_teacher_owner(actor_id: str, meta: dict) -> None:
    owner = str(meta.get("teacher_id") or "").strip()
    if not owner or owner != actor_id:
        raise AssignmentAccessError(403, "forbidden_assignment_owner")


def _require_student_assignment_access(
    assignment_id: str, principal: Any, meta: dict, *, deps: AssignmentAccessDeps
) -> None:
    if not student_can_read_assignment(meta, assignment_id=assignment_id):
        raise AssignmentAccessError(403, "forbidden_assignment_scope")
    class_name = ""
    try:
        profile_path = deps.resolve_student_profile_path(principal.actor_id)
        profile = deps.load_profile_file(profile_path)
        class_name = str(profile.get("class_name") or "").strip()
    except Exception:  # policy: allowed-broad-except
        class_name = ""
    if int(deps.assignment_specificity(meta, principal.actor_id, class_name)) <= 0:
        raise AssignmentAccessError(403, "forbidden_assignment_scope")


def require_assignment_access(assignment_id: str, *, deps: AssignmentAccessDeps) -> None:
    if not auth_required():
        return
    try:
        principal = require_principal(roles=("teacher", "student", "admin", "service"))
    except AuthError as exc:
        raise AssignmentAccessError(exc.status_code, exc.detail) from exc
    if principal is None:
        return
    if principal.role in {"admin", "service"}:
        return
    meta = _load_assignment_meta(assignment_id, deps=deps)
    if principal.role == "teacher":
        actor = str(principal.actor_id or "").strip()
        if not actor:
            raise AssignmentAccessError(400, "teacher_id_required")
        _require_teacher_owner(actor, meta)
        return
    _require_student_assignment_access(assignment_id, principal, meta, deps=deps)


async def list_assignments(
    *, limit: int = 50, cursor: int = 0, deps: AssignmentApplicationDeps
) -> Any:
    return await deps.list_assignments(int(limit), int(cursor))


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
    return await deps.teacher_assignments_progress(date)


async def post_assignment_requirements(
    req: AssignmentRequirementsRequest, *, deps: AssignmentApplicationDeps
) -> Any:
    return await deps.assignment_requirements(req)


async def get_assignment_requirements(
    assignment_id: str, *, deps: AssignmentApplicationDeps
) -> Any:
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
    return await deps.assignment_questions_ocr(
        assignment_id=assignment_id,
        files=files,
        kp_id=kp_id,
        difficulty=difficulty,
        tags=tags,
        ocr_mode=ocr_mode,
        language=language,
    )
