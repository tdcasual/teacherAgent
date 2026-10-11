from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .assignment.visibility import effective_visibility_status
from .assignment_catalog_service import effective_assignment_kind, effective_content_source
from .auth_service import AuthError, enforce_upload_job_access, get_current_principal
from .paths import require_safe_assignment_id
from .question_bank_select_service import count_question_data_rows


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
    compute_requirements_missing: Callable[..., List[str]]
    parse_list_value: Callable[[Any], List[str]]
    data_dir: Optional[Path] = None


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
    kind = effective_assignment_kind({"assignment_kind": job.get("assignment_kind")})

    def _missing(requirements: Dict[str, Any], assignment_kind: str = kind) -> List[str]:
        return deps.compute_requirements_missing(requirements, assignment_kind=assignment_kind)

    draft = deps.build_assignment_upload_draft(
        job_id,
        job,
        parsed,
        override,
        merge_requirements=deps.merge_requirements,
        compute_requirements_missing=_missing,
        parse_list_value=deps.parse_list_value,
    )
    return {"ok": True, "draft": draft}


def _resolve_query_assignment_dir(data_dir: Path, assignment_id: str) -> Path:
    root = (data_dir / "assignments").resolve()
    aid = str(assignment_id or "").strip()
    if not aid:
        raise AssignmentUploadQueryError(400, "assignment_id is required")
    try:
        aid = require_safe_assignment_id(aid)
    except ValueError as exc:
        raise AssignmentUploadQueryError(400, "invalid assignment_id") from exc
    target = (root / aid).resolve()
    if target == root or root not in target.parents:
        raise AssignmentUploadQueryError(400, "invalid assignment_id")
    return target


def get_assignment_folder_draft(assignment_id: str, *, deps: AssignmentUploadQueryDeps) -> Dict[str, Any]:
    data_dir = deps.data_dir
    if data_dir is None:
        raise AssignmentUploadQueryError(500, "data_dir_required")
    folder = _resolve_query_assignment_dir(data_dir, assignment_id)
    if not folder.exists():
        raise AssignmentUploadQueryError(404, "assignment not found")
    meta_path = folder / "meta.json"
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    except (OSError, json.JSONDecodeError):
        meta = {}
    if not isinstance(meta, dict):
        meta = {}
    actor = str(getattr(get_current_principal(), "actor_id", "") or "").strip()
    owner = str(meta.get("teacher_id") or "").strip()
    if not actor or owner != actor:
        raise AssignmentUploadQueryError(403, "forbidden")
    if effective_visibility_status(meta) != "draft":
        raise AssignmentUploadQueryError(409, "invalid_visibility_status")
    req_path = folder / "requirements.json"
    try:
        requirements = json.loads(req_path.read_text(encoding="utf-8")) if req_path.exists() else {}
    except (OSError, json.JSONDecodeError):
        requirements = {}
    if not isinstance(requirements, dict):
        requirements = {}
    questions: List[Dict[str, Any]] = []
    questions_path = folder / "questions.csv"
    if questions_path.exists():
        with questions_path.open(encoding="utf-8") as handle:
            questions = [dict(row) for row in csv.DictReader(handle)]
    kind = effective_assignment_kind(meta)
    source = effective_content_source(meta, folder=folder)
    missing = deps.compute_requirements_missing(requirements, assignment_kind=kind)
    draft = {
        "assignment_id": assignment_id,
        "date": meta.get("date"),
        "due_at": meta.get("due_at") or "",
        "scope": meta.get("scope"),
        "class_name": meta.get("class_name"),
        "student_ids": meta.get("student_ids") or [],
        "question_count": count_question_data_rows(questions_path),
        "requirements": requirements,
        "requirements_missing": missing,
        "warnings": [],
        "questions": questions,
        "assignment_kind": kind,
        "content_source": source,
        "draft_saved": True,
    }
    return {"ok": True, "draft": draft}
