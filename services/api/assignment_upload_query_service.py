from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List

from .auth_service import AuthError, enforce_upload_job_access


class AssignmentUploadQueryError(Exception):
    def __init__(self, status_code: int, detail: Any):
        super().__init__(str(detail))
        self.status_code = int(status_code)
        self.detail = detail


@dataclass(frozen=True)
class AssignmentUploadQueryDeps:
    load_upload_job: Callable[[str], Dict[str, Any]]
    upload_job_path: Callable[[str], Path]
    assignment_upload_not_ready_detail: Callable[[Dict[str, Any], str], Dict[str, Any]]
    load_assignment_draft_override: Callable[[Path], Dict[str, Any]]
    build_assignment_upload_draft: Callable[..., Dict[str, Any]]
    merge_requirements: Callable[[Dict[str, Any], Dict[str, Any], bool], Dict[str, Any]]
    compute_requirements_missing: Callable[[Dict[str, Any]], List[str]]
    parse_list_value: Callable[[Any], List[str]]


def get_assignment_upload_status(job_id: str, *, deps: AssignmentUploadQueryDeps) -> Dict[str, Any]:
    try:
        job = deps.load_upload_job(job_id)
    except FileNotFoundError:
        raise AssignmentUploadQueryError(404, "job not found")
    try:
        enforce_upload_job_access(job)
    except AuthError as exc:
        raise AssignmentUploadQueryError(exc.status_code, exc.detail)
    return job


def get_assignment_upload_draft(job_id: str, *, deps: AssignmentUploadQueryDeps) -> Dict[str, Any]:
    try:
        job = deps.load_upload_job(job_id)
    except FileNotFoundError:
        raise AssignmentUploadQueryError(404, "job not found")
    try:
        enforce_upload_job_access(job)
    except AuthError as exc:
        raise AssignmentUploadQueryError(exc.status_code, exc.detail)

    if job.get("status") not in {"done", "confirmed"}:
        raise AssignmentUploadQueryError(
            400,
            deps.assignment_upload_not_ready_detail(job, "解析尚未完成，暂无法打开草稿。"),
        )

    job_dir = deps.upload_job_path(job_id)
    parsed_path = job_dir / "parsed.json"
    if not parsed_path.exists():
        raise AssignmentUploadQueryError(400, "parsed result missing")
    parsed = json.loads(parsed_path.read_text(encoding="utf-8"))

    override = deps.load_assignment_draft_override(job_dir)
    draft = deps.build_assignment_upload_draft(
        job_id,
        job,
        parsed,
        override,
        merge_requirements=deps.merge_requirements,
        compute_requirements_missing=deps.compute_requirements_missing,
        parse_list_value=deps.parse_list_value,
    )
    return {"ok": True, "draft": draft}
