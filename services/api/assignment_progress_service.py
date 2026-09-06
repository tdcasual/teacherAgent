from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .assignment_learning_evidence_service import build_assignment_progress_evidence
from .assignment_process_archive_service import read_process_archive_summary
from .teacher_grade_service import load_teacher_grade, official_score_from


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
    today_iso: Callable[[], str]
    now_iso: Callable[[], str]


_log = logging.getLogger(__name__)


_DEFAULT_COMPLETION_POLICY: Dict[str, Any] = {
    "requires_discussion": False,
    "requires_submission": True,
    "min_graded_total": 1,
    "best_attempt": "score_earned_then_correct_then_graded_total",
    "version": 2,
}
_PROCESS_STATUSES = frozenset({"none", "pending", "frozen", "partial"})


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


def _parse_due_date(due_at: str) -> Optional[date]:
    if not due_at:
        return None
    try:
        return datetime.fromisoformat(due_at.replace("Z", "+00:00")).date()
    except ValueError:
        _log.debug("operation failed", exc_info=True)
        return None


def _today_date(deps: AssignmentProgressDeps) -> Optional[date]:
    raw = str(deps.today_iso() or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        _log.debug("invalid today_iso", exc_info=True)
        return None


def _is_overdue(*, today: Optional[date], due_date: Optional[date], submitted: bool) -> bool:
    return bool(due_date and today and today > due_date and not submitted)


def _is_completed(submitted: bool, requires_submission: bool) -> bool:
    return submitted if requires_submission else True


def _process_column(folder: Path, student_id: str) -> Dict[str, Any]:
    empty: Dict[str, Any] = {"status": "none", "stuck_points": [], "has_memory_proposal": False}
    token = str(student_id or "").strip()
    if not token or "/" in token or "\\" in token:
        return empty
    path = folder / "process_archives" / f"{token}.json"
    if not path.exists():
        return empty
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty
    if not isinstance(payload, dict):
        return empty
    status = str(payload.get("status") or "none").strip().lower()
    stuck = payload.get("stuck_points")
    return {
        "status": status if status in _PROCESS_STATUSES else "none",
        "stuck_points": stuck if isinstance(stuck, list) else [],
        "has_memory_proposal": False,
    }


def _profile_map(profiles: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {
        str(profile.get("student_id")): profile
        for profile in profiles
        if profile.get("student_id")
    }


def _as_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value or "").strip().lower()
    if not text:
        return bool(default)
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return bool(default)


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:  # policy: allowed-broad-except
        return int(default)


def _normalize_completion_policy(meta: Dict[str, Any]) -> Dict[str, Any]:
    raw = meta.get("completion_policy")
    policy_raw = raw if isinstance(raw, dict) else {}
    min_graded_total = max(
        0,
        _as_int(
            policy_raw.get("min_graded_total", _DEFAULT_COMPLETION_POLICY["min_graded_total"]),
            int(_DEFAULT_COMPLETION_POLICY["min_graded_total"]),
        ),
    )
    best_attempt = str(
        policy_raw.get("best_attempt", _DEFAULT_COMPLETION_POLICY["best_attempt"])
        or _DEFAULT_COMPLETION_POLICY["best_attempt"]
    ).strip() or str(_DEFAULT_COMPLETION_POLICY["best_attempt"])
    version = max(1, _as_int(policy_raw.get("version", _DEFAULT_COMPLETION_POLICY["version"]), 1))
    return {
        "requires_discussion": _as_bool(
            policy_raw.get("requires_discussion", _DEFAULT_COMPLETION_POLICY["requires_discussion"]),
            bool(_DEFAULT_COMPLETION_POLICY["requires_discussion"]),
        ),
        "requires_submission": _as_bool(
            policy_raw.get("requires_submission", _DEFAULT_COMPLETION_POLICY["requires_submission"]),
            bool(_DEFAULT_COMPLETION_POLICY["requires_submission"]),
        ),
        "min_graded_total": min_graded_total,
        "best_attempt": best_attempt,
        "version": version,
        "discussion_marker": str(policy_raw.get("discussion_marker") or ""),
    }


def _attempt_int_value(attempt: Dict[str, Any], key: str) -> int:
    try:
        return int(attempt.get(key) or 0)
    except Exception:  # policy: allowed-broad-except
        _log.debug("numeric conversion failed", exc_info=True)
        return 0


def _attempt_has_positive_float(attempt: Dict[str, Any], key: str) -> bool:
    try:
        raw_value = attempt.get(key)
        return raw_value is not None and float(str(raw_value)) > 0
    except Exception:  # policy: allowed-broad-except
        return False


def _attempt_items_meet_minimum(attempt: Dict[str, Any], minimum: int) -> bool:
    items = attempt.get("items")
    return isinstance(items, list) and len(items) >= minimum


def _attempt_meets_min_graded_total(attempt: Dict[str, Any], min_graded_total: int) -> bool:
    if not isinstance(attempt, dict):
        return False
    minimum = max(0, int(min_graded_total or 0))
    if minimum <= 0:
        return True
    if "graded_total" in attempt:
        return _attempt_int_value(attempt, "graded_total") >= minimum
    if attempt.get("valid_submission") is False:
        return False
    if _attempt_has_positive_float(attempt, "score_earned"):
        return True
    if _attempt_has_positive_float(attempt, "score"):
        return True
    if _attempt_int_value(attempt, "correct") > 0:
        return True
    return _attempt_items_meet_minimum(attempt, minimum)


def _attempt_ts(value: Any) -> float:
    try:
        text = str(value or "").strip()
        if not text:
            return 0.0
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except Exception:  # policy: allowed-broad-except
        _log.debug("operation failed", exc_info=True)
        return 0.0


def _best_attempt_for_policy(
    attempts: List[Dict[str, Any]],
    *,
    policy: Dict[str, Any],
    deps: AssignmentProgressDeps,
) -> Optional[Dict[str, Any]]:
    min_graded_total = max(0, int(policy.get("min_graded_total") or 0))
    eligible = [item for item in attempts if _attempt_meets_min_graded_total(item, min_graded_total)]
    if not eligible:
        return None
    strategy = str(policy.get("best_attempt") or "").strip().lower()
    if strategy == "latest_submission":
        return max(eligible, key=lambda item: _attempt_ts(item.get("submitted_at")))
    if strategy == "highest_graded_total":
        return max(
            eligible,
            key=lambda item: (
                int(item.get("graded_total") or 0),
                _attempt_ts(item.get("submitted_at")),
            ),
        )
    return deps.best_submission_attempt(eligible)


def _student_payload(
    *,
    student_id: str,
    profile: Dict[str, Any],
    discussion: Dict[str, Any],
    attempts: List[Dict[str, Any]],
    best: Optional[Dict[str, Any]],
    completion_policy: Dict[str, Any],
    completion_checks: Dict[str, Any],
    evidence: Dict[str, Any],
    completed: bool,
    overdue: bool,
    submitted: bool,
    official_score: Optional[float],
    process: Dict[str, Any],
    teacher_grade: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "student_id": student_id,
        "student_name": profile.get("student_name") or "",
        "class_name": profile.get("class_name") or "",
        "discussion": discussion,
        "submission": {"attempts": len(attempts), "best": best},
        "completion": {"policy": completion_policy, "checks": completion_checks},
        "evidence": evidence,
        "complete": completed,
        "submitted": submitted,
        "overdue": overdue,
        "official_score": official_score,
        "result": {
            "attempts": len(attempts),
            "official_score": official_score,
            "overdue": overdue,
            "submitted": submitted,
        },
        "process": process,
        "teacher_grade": teacher_grade,
    }


def _student_progress(
    assignment_id: str,
    student_id: str,
    profile: Dict[str, Any],
    *,
    deps: AssignmentProgressDeps,
    completion_policy: Dict[str, Any],
    due_date: Optional[date],
    today: Optional[date],
    folder: Path,
    include_student_payload: bool,
) -> Dict[str, Any]:
    discussion = deps.session_discussion_pass(student_id, assignment_id)
    discussion_pass = bool(discussion.get("pass"))
    attempts = deps.list_submission_attempts(assignment_id, student_id)
    best = _best_attempt_for_policy(attempts, policy=completion_policy, deps=deps)
    submitted = bool(best)
    requires_discussion = bool(completion_policy.get("requires_discussion", False))
    requires_submission = bool(completion_policy.get("requires_submission", True))
    completed = _is_completed(submitted, requires_submission)
    overdue = _is_overdue(today=today, due_date=due_date, submitted=submitted)
    teacher_grade = load_teacher_grade(deps.data_dir, assignment_id, student_id)
    official_score = official_score_from(
        auto_score=(best or {}).get("score_earned") if best else None,
        teacher_grade=teacher_grade,
    )
    process = _process_column(folder, student_id)
    completion_checks: Dict[str, Any] = {
        "discussion_required": requires_discussion,
        "discussion_pass": discussion_pass,
        "submitted": submitted,
        "submission_required": requires_submission,
        "min_graded_total": int(completion_policy.get("min_graded_total") or 0),
        "completed": completed,
    }
    evidence = build_assignment_progress_evidence(
        assignment_id=assignment_id,
        student_id=student_id,
        discussion=discussion,
        attempts=attempts,
        best_attempt=best,
        completion_policy=completion_policy,
        completed=completed,
        official_score=official_score,
    )
    payload: Optional[Dict[str, Any]] = None
    if include_student_payload:
        archive = read_process_archive_summary(Path(deps.data_dir), assignment_id, student_id)
        merged_process = dict(process or {})
        merged_process["status"] = str(archive.get("status") or merged_process.get("status") or "none")
        if archive.get("stuck_points"):
            merged_process["stuck_points"] = archive.get("stuck_points")
        payload = _student_payload(
            student_id=student_id,
            profile=profile,
            discussion=discussion,
            attempts=attempts,
            best=best,
            completion_policy=completion_policy,
            completion_checks=completion_checks,
            evidence=evidence,
            completed=completed,
            overdue=overdue,
            submitted=submitted,
            official_score=official_score,
            process=merged_process,
            teacher_grade=teacher_grade,
        )
        payload["process_archive_status"] = str(archive.get("status") or "none")
        payload["process_archive"] = archive
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
    completion_policy = _normalize_completion_policy(meta)
    due_at = deps.normalize_due_at(meta.get("due_at"))
    due_date = _parse_due_date(due_at)
    today = _today_date(deps)
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
            completion_policy=completion_policy,
            due_date=due_date,
            today=today,
            folder=folder,
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
        "visibility_status": str(meta.get("visibility_status") or "").strip().lower(),
        "archived_at": meta.get("archived_at"),
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
    except Exception:  # policy: allowed-broad-except
        _log.warning("failed to write progress.json for assignment %s", assignment_id, exc_info=True)

    return result
