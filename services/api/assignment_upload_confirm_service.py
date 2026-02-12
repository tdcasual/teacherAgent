from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

_log = logging.getLogger(__name__)


class AssignmentUploadConfirmError(Exception):
    def __init__(self, status_code: int, detail: Any):
        super().__init__(str(detail))
        self.status_code = int(status_code)
        self.detail = detail


def _resolve_assignment_dir(data_dir: Path, assignment_id: str) -> Path:
    root = (data_dir / "assignments").resolve()
    aid = str(assignment_id or "").strip()
    if not aid:
        raise AssignmentUploadConfirmError(400, "assignment_id is required")
    target = (root / aid).resolve()
    if target != root and root not in target.parents:
        raise AssignmentUploadConfirmError(400, "invalid assignment_id")
    return target


@dataclass(frozen=True)
class AssignmentUploadConfirmDeps:
    data_dir: Path
    now_iso: Callable[[], str]
    discussion_complete_marker: str
    write_upload_job: Callable[[str, Dict[str, Any]], Dict[str, Any]]
    merge_requirements: Callable[[Dict[str, Any], Dict[str, Any], bool], Dict[str, Any]]
    compute_requirements_missing: Callable[[Dict[str, Any]], List[str]]
    write_uploaded_questions: Callable[[Path, str, List[Dict[str, Any]]], List[Dict[str, Any]]]
    parse_date_str: Callable[[Any], str]
    save_assignment_requirements: Callable[..., Any]
    parse_ids_value: Callable[[Any], List[str]]
    resolve_scope: Callable[[str, List[str], str], str]
    normalize_due_at: Callable[[Any], str]
    compute_expected_students: Callable[[str, str, List[str]], List[str]]
    atomic_write_json: Callable[[Path, Dict[str, Any]], None]
    copy2: Callable[[Path, Path], Any]


def _load_draft_override(job_dir: Path) -> Dict[str, Any]:
    override_path = job_dir / "draft_override.json"
    if not override_path.exists():
        return {}
    try:
        payload = json.loads(override_path.read_text(encoding="utf-8"))
    except Exception:
        _log.warning("failed to parse draft_override.json in %s", override_path, exc_info=True)
        return {}
    return payload if isinstance(payload, dict) else {}


def _copy_if_exists(src: Path, dst: Path, copy2: Callable[[Path, Path], Any]) -> None:
    if src.exists():
        copy2(src, dst)


def confirm_assignment_upload(
    job_id: str,
    job: Dict[str, Any],
    job_dir: Path,
    *,
    requirements_override: Optional[Dict[str, Any]],
    strict_requirements: bool,
    deps: AssignmentUploadConfirmDeps,
) -> Dict[str, Any]:
    deps.write_upload_job(
        job_id,
        {
            "status": "confirming",
            "step": "start",
            "progress": 5,
            "confirm_started_at": deps.now_iso(),
        },
    )

    parsed_path = job_dir / "parsed.json"
    if not parsed_path.exists():
        deps.write_upload_job(job_id, {"status": "failed", "error": "parsed result missing", "step": "failed"})
        raise AssignmentUploadConfirmError(400, "parsed result missing")
    parsed = json.loads(parsed_path.read_text(encoding="utf-8"))

    override = _load_draft_override(job_dir)
    questions = parsed.get("questions") or []
    if isinstance(override.get("questions"), list) and override.get("questions"):
        questions = override.get("questions") or questions

    requirements = parsed.get("requirements") or {}
    if isinstance(override.get("requirements"), dict) and override.get("requirements"):
        requirements = deps.merge_requirements(requirements, override.get("requirements") or {}, True)
    missing = parsed.get("missing") or []
    warnings = parsed.get("warnings") or []
    delivery_mode = parsed.get("delivery_mode") or job.get("delivery_mode") or "image"
    autofilled = parsed.get("autofilled") or False

    if requirements_override:
        requirements = deps.merge_requirements(requirements, requirements_override, True)
        missing = deps.compute_requirements_missing(requirements)
    else:
        missing = deps.compute_requirements_missing(requirements)

    if strict_requirements and missing:
        deps.write_upload_job(
            job_id,
            {
                "status": "done",
                "step": "await_requirements",
                "progress": 100,
                "requirements_missing": missing,
            },
        )
        raise AssignmentUploadConfirmError(
            400,
            {"error": "requirements_missing", "missing": missing, "message": "作业要求未补全，无法创建作业。"},
        )

    assignment_id = str(job.get("assignment_id") or "").strip()
    if not assignment_id:
        deps.write_upload_job(job_id, {"status": "failed", "error": "assignment_id missing", "step": "failed"})
        raise AssignmentUploadConfirmError(400, "assignment_id missing")
    try:
        out_dir = _resolve_assignment_dir(deps.data_dir, assignment_id)
    except AssignmentUploadConfirmError as exc:
        deps.write_upload_job(job_id, {"status": "failed", "error": str(exc.detail), "step": "failed"})
        raise
    meta_path = out_dir / "meta.json"
    if meta_path.exists():
        deps.write_upload_job(job_id, {"status": "confirmed", "step": "confirmed", "progress": 100})
        raise AssignmentUploadConfirmError(409, "assignment already exists")
    out_dir.mkdir(parents=True, exist_ok=True)

    deps.write_upload_job(job_id, {"step": "copy_files", "progress": 20})
    source_dir = out_dir / "source"
    answer_dir = out_dir / "answer_source"
    source_dir.mkdir(parents=True, exist_ok=True)
    answer_dir.mkdir(parents=True, exist_ok=True)
    for fname in job.get("source_files") or []:
        _copy_if_exists(job_dir / "source" / str(fname), source_dir / str(fname), deps.copy2)
    for fname in job.get("answer_files") or []:
        _copy_if_exists(job_dir / "answer_source" / str(fname), answer_dir / str(fname), deps.copy2)

    deps.write_upload_job(job_id, {"step": "write_questions", "progress": 55})
    rows = deps.write_uploaded_questions(out_dir, assignment_id, questions)
    date_str = deps.parse_date_str(job.get("date"))
    deps.write_upload_job(job_id, {"step": "save_requirements", "progress": 70})
    deps.save_assignment_requirements(
        assignment_id,
        requirements,
        date_str,
        created_by="teacher_upload",
        validate=False,
    )

    student_ids_list = deps.parse_ids_value(job.get("student_ids") or [])
    scope_val = deps.resolve_scope(job.get("scope") or "", student_ids_list, job.get("class_name") or "")
    if scope_val == "student" and not student_ids_list:
        raise AssignmentUploadConfirmError(400, "student scope requires student_ids")

    meta = {
        "assignment_id": assignment_id,
        "date": date_str,
        "due_at": deps.normalize_due_at(job.get("due_at")) or "",
        "mode": "upload",
        "target_kp": requirements.get("core_concepts") or [],
        "question_ids": [row.get("question_id") for row in rows if row.get("question_id")],
        "class_name": job.get("class_name") or "",
        "student_ids": student_ids_list,
        "scope": scope_val,
        "expected_students": deps.compute_expected_students(scope_val, job.get("class_name") or "", student_ids_list),
        "expected_students_generated_at": deps.now_iso(),
        "completion_policy": {
            "requires_discussion": True,
            "discussion_marker": deps.discussion_complete_marker,
            "requires_submission": True,
            "min_graded_total": 1,
            "best_attempt": "score_earned_then_correct_then_graded_total",
            "version": 1,
        },
        "source": "teacher",
        "delivery_mode": delivery_mode,
        "source_files": job.get("source_files") or [],
        "answer_files": job.get("answer_files") or [],
        "requirements_missing": missing,
        "requirements_autofilled": autofilled,
        "generated_at": deps.now_iso(),
        "job_id": job_id,
    }
    deps.atomic_write_json(meta_path, meta)

    deps.write_upload_job(
        job_id,
        {
            "status": "confirmed",
            "step": "confirmed",
            "progress": 100,
            "confirmed_at": deps.now_iso(),
        },
    )

    return {
        "ok": True,
        "assignment_id": assignment_id,
        "question_count": len(rows),
        "requirements_missing": missing,
        "warnings": warnings,
        "status": "confirmed",
    }
