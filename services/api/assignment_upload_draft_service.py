from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List

_log = logging.getLogger(__name__)


def assignment_upload_not_ready_detail(job: Dict[str, Any], message: str) -> Dict[str, Any]:
    return {
        "error": "job_not_ready",
        "message": message,
        "status": job.get("status"),
        "step": job.get("step"),
        "progress": job.get("progress"),
    }


def load_assignment_draft_override(job_dir: Path) -> Dict[str, Any]:
    override_path = job_dir / "draft_override.json"
    if not override_path.exists():
        return {}
    try:
        data = json.loads(override_path.read_text(encoding="utf-8"))
    except Exception:
        _log.warning("corrupt draft_override.json in %s", job_dir, exc_info=True)
        return {}
    return data if isinstance(data, dict) else {}


def save_assignment_draft_override(
    job_dir: Path,
    current_override: Dict[str, Any],
    *,
    requirements: Any = None,
    questions: Any = None,
    requirements_missing: Any = None,
    now_iso: Callable[[], str],
) -> Dict[str, Any]:
    override = dict(current_override or {})
    if requirements is not None:
        override["requirements"] = requirements
    if questions is not None:
        override["questions"] = questions
    if requirements_missing is not None:
        override["requirements_missing"] = requirements_missing
    override["saved_at"] = now_iso()
    override_path = job_dir / "draft_override.json"
    override_path.write_text(json.dumps(override, ensure_ascii=False, indent=2), encoding="utf-8")
    return override


def clean_assignment_draft_questions(questions: Any) -> List[Dict[str, Any]]:
    if not isinstance(questions, list):
        return []
    cleaned: List[Dict[str, Any]] = []
    for question in questions:
        if not isinstance(question, dict):
            continue
        stem = str(question.get("stem") or "").strip()
        cleaned.append({**question, "stem": stem})
    return cleaned


def build_assignment_upload_draft(
    job_id: str,
    job: Dict[str, Any],
    parsed: Dict[str, Any],
    override: Dict[str, Any],
    *,
    merge_requirements: Callable[[Dict[str, Any], Dict[str, Any], bool], Dict[str, Any]],
    compute_requirements_missing: Callable[[Dict[str, Any]], List[str]],
    parse_list_value: Callable[[Any], List[str]],
) -> Dict[str, Any]:
    base_questions = parsed.get("questions") or []
    base_requirements = parsed.get("requirements") or {}
    warnings = parsed.get("warnings") or []

    questions = base_questions
    if isinstance(override.get("questions"), list) and override.get("questions"):
        questions = override.get("questions") or base_questions

    requirements = base_requirements
    if isinstance(override.get("requirements"), dict) and override.get("requirements"):
        requirements = merge_requirements(base_requirements, override.get("requirements") or {}, True)

    missing = compute_requirements_missing(requirements)
    if override.get("requirements_missing"):
        try:
            missing = sorted(set(missing + parse_list_value(override.get("requirements_missing"))))
        except Exception:
            _log.warning("requirements_missing merge failed for job %s", job_id, exc_info=True)

    return {
        "job_id": job_id,
        "assignment_id": job.get("assignment_id"),
        "date": job.get("date"),
        "due_at": job.get("due_at") or "",
        "scope": job.get("scope"),
        "class_name": job.get("class_name"),
        "student_ids": job.get("student_ids") or [],
        "delivery_mode": parsed.get("delivery_mode") or job.get("delivery_mode") or "image",
        "source_files": job.get("source_files") or [],
        "answer_files": job.get("answer_files") or [],
        "question_count": len(questions) if isinstance(questions, list) else 0,
        "requirements": requirements,
        "requirements_missing": missing,
        "warnings": warnings,
        "questions": questions,
        "autofilled": parsed.get("autofilled") or False,
        "draft_saved": bool(override),
        "draft_version": int(job.get("draft_version") or 1),
    }
