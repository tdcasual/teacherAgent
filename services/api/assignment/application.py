from __future__ import annotations

from typing import Optional

from fastapi import UploadFile

from ..api_models import AssignmentRequirementsRequest, UploadConfirmRequest, UploadDraftSaveRequest
from .deps import AssignmentApplicationDeps


async def list_assignments(*, deps: AssignmentApplicationDeps):
    return await deps.list_assignments()


async def get_teacher_assignment_progress(
    assignment_id: str,
    *,
    include_students: bool,
    deps: AssignmentApplicationDeps,
):
    return await deps.teacher_assignment_progress(assignment_id, include_students)


async def get_teacher_assignments_progress(*, date: Optional[str], deps: AssignmentApplicationDeps):
    return await deps.teacher_assignments_progress(date)


async def post_assignment_requirements(
    req: AssignmentRequirementsRequest, *, deps: AssignmentApplicationDeps
):
    return await deps.assignment_requirements(req)


async def get_assignment_requirements(assignment_id: str, *, deps: AssignmentApplicationDeps):
    return await deps.assignment_requirements_get(assignment_id)


async def upload_assignment_legacy(
    *,
    assignment_id: str,
    date: Optional[str],
    scope: Optional[str],
    class_name: Optional[str],
    student_ids: Optional[str],
    files: list[UploadFile],
    answer_files: Optional[list[UploadFile]],
    ocr_mode: Optional[str],
    language: Optional[str],
    deps: AssignmentApplicationDeps,
):
    return await deps.assignment_upload_legacy(
        assignment_id=assignment_id,
        date=date,
        scope=scope,
        class_name=class_name,
        student_ids=student_ids,
        files=files,
        answer_files=answer_files,
        ocr_mode=ocr_mode,
        language=language,
    )


async def upload_assignment_start(
    *,
    assignment_id: str,
    date: Optional[str],
    due_at: Optional[str],
    scope: Optional[str],
    class_name: Optional[str],
    student_ids: Optional[str],
    files: list[UploadFile],
    answer_files: Optional[list[UploadFile]],
    ocr_mode: Optional[str],
    language: Optional[str],
    deps: AssignmentApplicationDeps,
):
    return await deps.assignment_upload_start(
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
    )


async def get_assignment_upload_status(job_id: str, *, deps: AssignmentApplicationDeps):
    return await deps.assignment_upload_status(job_id)


async def get_assignment_upload_draft(job_id: str, *, deps: AssignmentApplicationDeps):
    return await deps.assignment_upload_draft(job_id)


async def save_assignment_upload_draft(
    req: UploadDraftSaveRequest, *, deps: AssignmentApplicationDeps
):
    return await deps.assignment_upload_draft_save(req)


async def confirm_assignment_upload(req: UploadConfirmRequest, *, deps: AssignmentApplicationDeps):
    return await deps.assignment_upload_confirm(req)


async def download_assignment_file(
    assignment_id: str,
    file: str,
    *,
    deps: AssignmentApplicationDeps,
):
    return await deps.assignment_download(assignment_id, file)


async def get_assignment_today(
    *,
    student_id: str,
    date: Optional[str],
    auto_generate: bool,
    generate: bool,
    per_kp: int,
    deps: AssignmentApplicationDeps,
):
    return await deps.assignment_today(
        student_id=student_id,
        date=date,
        auto_generate=auto_generate,
        generate=generate,
        per_kp=per_kp,
    )


async def get_assignment_detail(assignment_id: str, *, deps: AssignmentApplicationDeps):
    return await deps.assignment_detail(assignment_id)


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
    class_name: Optional[str],
    student_ids: Optional[str],
    source: Optional[str],
    requirements_json: Optional[str],
    deps: AssignmentApplicationDeps,
):
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
        class_name=class_name,
        student_ids=student_ids,
        source=source,
        requirements_json=requirements_json,
    )


async def post_render_assignment(assignment_id: str, *, deps: AssignmentApplicationDeps):
    return await deps.render_assignment(assignment_id)


async def post_assignment_questions_ocr(
    *,
    assignment_id: str,
    files: list[UploadFile],
    kp_id: Optional[str],
    difficulty: Optional[str],
    tags: Optional[str],
    ocr_mode: Optional[str],
    language: Optional[str],
    deps: AssignmentApplicationDeps,
):
    return await deps.assignment_questions_ocr(
        assignment_id=assignment_id,
        files=files,
        kp_id=kp_id,
        difficulty=difficulty,
        tags=tags,
        ocr_mode=ocr_mode,
        language=language,
    )
