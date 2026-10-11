from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .assignment.visibility import effective_visibility_status
from .assignment_catalog_service import effective_assignment_kind
from .auth_service import AuthError, enforce_upload_job_access, get_current_principal
from .paths import APP_ROOT, require_safe_assignment_id
from .question_bank_select_service import (
    ensure_questions_csv_header,
    resolve_bank_ref,
    write_questions_csv,
)


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
    compute_requirements_missing: Callable[..., List[str]]
    write_upload_job: Callable[[str, Dict[str, Any]], Dict[str, Any]]
    now_iso: Callable[[], str]
    data_dir: Optional[Path] = None
    app_root: Optional[Path] = None


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

    if job.get("status") not in {"done", "confirmed"}:
        raise AssignmentUploadDraftSaveError(
            400,
            deps.assignment_upload_not_ready_detail(job, "解析尚未完成，暂无法保存草稿。"),
        )

    job_dir = deps.upload_job_path(job_id)
    parsed_path = job_dir / "parsed.json"
    if not parsed_path.exists():
        raise AssignmentUploadDraftSaveError(400, "parsed result missing")
    parsed = json.loads(parsed_path.read_text(encoding="utf-8"))

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
    kind = effective_assignment_kind({"assignment_kind": job.get("assignment_kind")})
    missing = deps.compute_requirements_missing(merged_requirements, assignment_kind=kind)

    deps.save_assignment_draft_override(
        job_dir,
        {},
        requirements=override.get("requirements"),
        questions=override.get("questions"),
        requirements_missing=missing,
        now_iso=deps.now_iso,
    )

    deps.write_upload_job(
        job_id,
        {
            "requirements": merged_requirements,
            "requirements_missing": missing,
            "question_count": len(override.get("questions") or parsed.get("questions") or []),
            "draft_saved": True,
        },
    )

    return {
        "ok": True,
        "job_id": job_id,
        "requirements_missing": missing,
        "message": "草稿已保存，将用于创建作业。",
    }


def _resolve_draft_assignment_dir(data_dir: Path, assignment_id: str) -> Path:
    root = (data_dir / "assignments").resolve()
    aid = str(assignment_id or "").strip()
    if not aid:
        raise AssignmentUploadDraftSaveError(400, "assignment_id is required")
    try:
        aid = require_safe_assignment_id(aid)
    except ValueError as exc:
        raise AssignmentUploadDraftSaveError(400, "invalid assignment_id") from exc
    target = (root / aid).resolve()
    if target == root or root not in target.parents:
        raise AssignmentUploadDraftSaveError(400, "invalid assignment_id")
    return target


def _reject_out_of_jail_question_refs(
    rows: List[Dict[str, Any]], *, data_dir: Path, app_root: Path
) -> None:
    for row in rows:
        for field in ("stem_ref", "answer_ref"):
            raw = str(row.get(field) or "").strip()
            if not raw:
                continue
            if resolve_bank_ref(raw, data_dir=data_dir, app_root=app_root) is None:
                raise AssignmentUploadDraftSaveError(400, "invalid_bank_ref")


def _read_json_dict(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def save_assignment_folder_draft(
    assignment_id: str,
    requirements: Any,
    questions: Any,
    *,
    deps: AssignmentUploadDraftSaveDeps,
) -> Dict[str, Any]:
    data_dir = deps.data_dir
    if data_dir is None:
        raise AssignmentUploadDraftSaveError(500, "data_dir_required")
    out_dir = _resolve_draft_assignment_dir(data_dir, assignment_id)
    if not out_dir.exists():
        raise AssignmentUploadDraftSaveError(404, "assignment not found")
    meta = _read_json_dict(out_dir / "meta.json")
    actor = str(getattr(get_current_principal(), "actor_id", "") or "").strip()
    owner = str(meta.get("teacher_id") or "").strip()
    if not actor or owner != actor:
        raise AssignmentUploadDraftSaveError(403, "forbidden")
    if effective_visibility_status(meta) != "draft":
        raise AssignmentUploadDraftSaveError(409, "invalid_visibility_status")
    current_requirements = _read_json_dict(out_dir / "requirements.json")
    if requirements is not None:
        if not isinstance(requirements, dict):
            raise AssignmentUploadDraftSaveError(400, "requirements must be an object")
        current_requirements = deps.merge_requirements(current_requirements, requirements, True)
        (out_dir / "requirements.json").write_text(
            json.dumps(
                {
                    "assignment_id": assignment_id,
                    "created_at": deps.now_iso(),
                    **current_requirements,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        brief = str(current_requirements.get("brief") or "").strip()
        if brief:
            (out_dir / "brief.md").write_text(brief + "\n", encoding="utf-8")
    if questions is not None:
        if not isinstance(questions, list):
            raise AssignmentUploadDraftSaveError(400, "questions must be an array")
        cleaned = deps.clean_assignment_draft_questions(questions)
        if cleaned:
            _reject_out_of_jail_question_refs(
                cleaned, data_dir=data_dir, app_root=deps.app_root or APP_ROOT
            )
            write_questions_csv(out_dir / "questions.csv", cleaned)
        else:
            ensure_questions_csv_header(out_dir / "questions.csv")
    kind = effective_assignment_kind(meta)
    missing = deps.compute_requirements_missing(current_requirements, assignment_kind=kind)
    return {
        "ok": True,
        "assignment_id": assignment_id,
        "requirements_missing": missing,
        "message": "草稿已保存，将用于创建作业。",
    }
