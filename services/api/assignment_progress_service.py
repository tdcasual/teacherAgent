from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


@dataclass(frozen=True)
class AssignmentProgressDeps:
    data_dir: Any
    load_assignment_meta: Callable[[Any], Dict[str, Any]]
    postprocess_assignment_meta: Callable[[str], None]
    normalize_due_at: Callable[[Any], str]
    list_all_student_profiles: Callable[[], List[Dict[str, Any]]]
    session_discussion_pass: Callable[[str, str], Dict[str, Any]]
    list_submission_attempts: Callable[[str, str], List[Dict[str, Any]]]
    best_submission_attempt: Callable[[List[Dict[str, Any]]], Optional[Dict[str, Any]]]
    resolve_assignment_date: Callable[[Dict[str, Any], Any], Optional[str]]
    atomic_write_json: Callable[[Any, Any], None]
    time_time: Callable[[], float]
    now_iso: Callable[[], str]


_log = logging.getLogger(__name__)


def _resolve_assignment_dir(data_dir: Path, assignment_id: str) -> Optional[Path]:
    root = (data_dir / "assignments").resolve()
    aid = str(assignment_id or "").strip()
    if not aid:
        return None
    target = (root / aid).resolve()
    if target != root and root not in target.parents:
        return None
    return target


def _assignment_not_found(assignment_id: str) -> Dict[str, Any]:
    return {"ok": False, "error": "assignment_not_found", "assignment_id": assignment_id}


def _load_expected_students(meta: Dict[str, Any]) -> List[str]:
    expected_raw = meta.get("expected_students")
    if not isinstance(expected_raw, list):
        return []
    return [str(student).strip() for student in expected_raw if str(student).strip()]


def _parse_due_timestamp(due_at: str) -> Optional[float]:
    if not due_at:
        return None
    try:
        return datetime.fromisoformat(due_at.replace("Z", "+00:00")).timestamp()
    except ValueError:
        _log.debug("operation failed", exc_info=True)
        return None


def _profile_map(profiles: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {
        str(profile.get("student_id")): profile
        for profile in profiles
        if profile.get("student_id")
    }


def _student_progress(
    assignment_id: str,
    student_id: str,
    profile: Dict[str, Any],
    *,
    deps: AssignmentProgressDeps,
    due_ts: Optional[float],
    now_ts: float,
    include_student_payload: bool,
) -> Dict[str, Any]:
    discussion = deps.session_discussion_pass(student_id, assignment_id)
    discussion_pass = bool(discussion.get("pass"))
    attempts = deps.list_submission_attempts(assignment_id, student_id)
    best = deps.best_submission_attempt(attempts)
    submitted = bool(best)
    completed = discussion_pass and submitted
    overdue = bool(due_ts and now_ts > due_ts and not completed)
    payload: Optional[Dict[str, Any]] = None
    if include_student_payload:
        payload = {
            "student_id": student_id,
            "student_name": profile.get("student_name") or "",
            "class_name": profile.get("class_name") or "",
            "discussion": discussion,
            "submission": {"attempts": len(attempts), "best": best},
            "complete": completed,
            "overdue": overdue,
        }
    return {
        "discussion_pass": discussion_pass,
        "submitted": submitted,
        "completed": completed,
        "overdue": overdue,
        "payload": payload,
    }


def _student_sort_key(item: Dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(item.get("class_name") or ""),
        str(item.get("student_name") or ""),
        str(item.get("student_id") or ""),
    )


def compute_assignment_progress(
    assignment_id: str,
    *,
    deps: AssignmentProgressDeps,
    include_students: bool = True,
) -> Dict[str, Any]:
    folder = _resolve_assignment_dir(deps.data_dir, assignment_id)
    if folder is None:
        return _assignment_not_found(assignment_id)
    if not folder.exists():
        return _assignment_not_found(assignment_id)
    meta = deps.load_assignment_meta(folder)
    if not meta:
        meta = {"assignment_id": assignment_id}

    deps.postprocess_assignment_meta(assignment_id)
    meta = deps.load_assignment_meta(folder) or meta

    expected_students = _load_expected_students(meta)
    due_at = deps.normalize_due_at(meta.get("due_at"))
    due_ts = _parse_due_timestamp(due_at)
    now_ts = deps.time_time()
    profiles = _profile_map(deps.list_all_student_profiles())

    students_out: List[Dict[str, Any]] = []
    discussion_pass_count = 0
    submission_count = 0
    completed_count = 0
    overdue_count = 0

    for sid in expected_students:
        student = _student_progress(
            assignment_id,
            sid,
            profiles.get(sid) or {},
            deps=deps,
            due_ts=due_ts,
            now_ts=now_ts,
            include_student_payload=include_students,
        )
        discussion_pass_count += int(bool(student["discussion_pass"]))
        submission_count += int(bool(student["submitted"]))
        completed_count += int(bool(student["completed"]))
        overdue_count += int(bool(student["overdue"]))
        payload = student.get("payload")
        if include_students and isinstance(payload, dict):
            students_out.append(payload)

    if include_students:
        students_out.sort(key=_student_sort_key)

    result = {
        "ok": True,
        "assignment_id": assignment_id,
        "date": deps.resolve_assignment_date(meta, folder),
        "scope": meta.get("scope") or "",
        "class_name": meta.get("class_name") or "",
        "due_at": due_at or "",
        "expected_count": len(expected_students),
        "counts": {
            "expected": len(expected_students),
            "discussion_pass": discussion_pass_count,
            "submitted": submission_count,
            "completed": completed_count,
            "overdue": overdue_count,
        },
        "students": students_out if include_students else [],
        "updated_at": deps.now_iso(),
    }

    try:
        deps.atomic_write_json(folder / "progress.json", result)
    except Exception:
        _log.warning("failed to write progress.json for assignment %s", assignment_id, exc_info=True)

    return result
