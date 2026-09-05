from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List

from .assignment_upload_draft_service import load_or_materialize_assignment_parsed
from .auth_service import AuthError, enforce_upload_job_access

_DRAFT_SAVE_READY_STATUSES = {"done", "confirmed", "failed"}


class AssignmentUploadDraftSaveError(Exception):
    def __init__(self, status_code: int, detail: Any):
        super().__init__(str(detail))
        self.status_code = int(status_code)
        self.detail = detail


@dataclass(frozen=True)
class AssignmentUploadDraftSaveDeps:
    load_upload_job: Callable[[str], Dict[str, Any]]
    upload_job_path: Callable[[str], Path]
    assignment_upload_not_ready_detail: Callable[[Dict[str, Any], str], Dict[str, Any]]
    clean_assignment_draft_questions: Callable[[Any], List[Dict[str, Any]]]
    save_assignment_draft_override: Callable[..., Dict[str, Any]]
    merge_requirements: Callable[[Dict[str, Any], Dict[str, Any], bool], Dict[str, Any]]
    compute_requirements_missing: Callable[[Dict[str, Any]], List[str]]
    write_upload_job: Callable[[str, Dict[str, Any]], Dict[str, Any]]
    now_iso: Callable[[], str]


def save_assignment_upload_draft(
    job_id: str,
    requirements: Any,
    questions: Any,
    *,
    deps: AssignmentUploadDraftSaveDeps,
) -> Dict[str, Any]:
    try:
        job = deps.load_upload_job(job_id)
    except FileNotFoundError:
        raise AssignmentUploadDraftSaveError(404, "job not found")
    try:
        enforce_upload_job_access(job)
    except AuthError as exc:
        raise AssignmentUploadDraftSaveError(exc.status_code, exc.detail)

    if job.get("status") not in _DRAFT_SAVE_READY_STATUSES:
        raise AssignmentUploadDraftSaveError(
            400,
            deps.assignment_upload_not_ready_detail(job, "解析尚未完成，暂无法保存草稿。"),
        )

    job_dir = deps.upload_job_path(job_id)
    parsed = load_or_materialize_assignment_parsed(
        job_dir,
        delivery_mode=str(job.get("delivery_mode") or "image"),
        now_iso=deps.now_iso,
    )

    override: Dict[str, Any] = {}
    if requirements is not None:
        if not isinstance(requirements, dict):
            raise AssignmentUploadDraftSaveError(400, "requirements must be an object")
        override["requirements"] = requirements
    if questions is not None:
        if not isinstance(questions, list):
            raise AssignmentUploadDraftSaveError(400, "questions must be an array")
        override["questions"] = deps.clean_assignment_draft_questions(questions)

    base_requirements = parsed.get("requirements") or {}
    merged_requirements = deps.merge_requirements(base_requirements, override.get("requirements") or {}, True)
    missing = deps.compute_requirements_missing(merged_requirements)

    deps.save_assignment_draft_override(
        job_dir,
        {},
        requirements=override.get("requirements"),
        questions=override.get("questions"),
        requirements_missing=missing,
        now_iso=deps.now_iso,
    )

    job_updates: Dict[str, Any] = {
        "requirements": merged_requirements,
        "requirements_missing": missing,
        "question_count": len(override.get("questions") or parsed.get("questions") or []),
        "draft_saved": True,
    }
    if job.get("status") == "failed":
        job_updates["recovered_from_parse_failure"] = True
    deps.write_upload_job(job_id, job_updates)

    return {
        "ok": True,
        "job_id": job_id,
        "requirements_missing": missing,
        "message": "草稿已保存，将用于创建作业。",
    }
