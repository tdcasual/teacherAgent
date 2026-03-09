from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .assignment_learning_evidence_service import build_assignment_progress_evidence


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


_DEFAULT_COMPLETION_POLICY: Dict[str, Any] = {
    "requires_discussion": True,
    "requires_submission": True,
    "min_graded_total": 1,
    "best_attempt": "score_earned_then_correct_then_graded_total",
    "version": 1,
}


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


def _attempt_meets_min_graded_total(attempt: Dict[str, Any], min_graded_total: int) -> bool:
    if not isinstance(attempt, dict):
        return False
    minimum = max(0, int(min_graded_total or 0))
    if minimum <= 0:
        return True
    if "graded_total" in attempt:
        try:
            graded_total = int(attempt.get("graded_total") or 0)
        except Exception:  # policy: allowed-broad-except
            _log.debug("numeric conversion failed", exc_info=True)
            graded_total = 0
        return graded_total >= minimum
    if attempt.get("valid_submission") is False:
        return False
    try:
        score_earned_raw = attempt.get("score_earned")
        if score_earned_raw is not None and float(str(score_earned_raw)) > 0:
            return True
    except Exception:  # policy: allowed-broad-except
        pass  # policy: allowed-broad-except
    try:
        score_raw = attempt.get("score")
        if score_raw is not None and float(str(score_raw)) > 0:
            return True
    except Exception:  # policy: allowed-broad-except
        pass  # policy: allowed-broad-except
    try:
        if int(attempt.get("correct") or 0) > 0:
            return True
    except Exception:  # policy: allowed-broad-except
        pass  # policy: allowed-broad-except
    items = attempt.get("items")
    return isinstance(items, list) and len(items) >= minimum


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


def _student_progress(
    assignment_id: str,
    student_id: str,
    profile: Dict[str, Any],
    *,
    deps: AssignmentProgressDeps,
    completion_policy: Dict[str, Any],
    due_ts: Optional[float],
    now_ts: float,
    include_student_payload: bool,
) -> Dict[str, Any]:
    discussion = deps.session_discussion_pass(student_id, assignment_id)
    discussion_pass = bool(discussion.get("pass"))
    attempts = deps.list_submission_attempts(assignment_id, student_id)
    best = _best_attempt_for_policy(attempts, policy=completion_policy, deps=deps)
    submitted = bool(best)
    requires_discussion = bool(completion_policy.get("requires_discussion", True))
    requires_submission = bool(completion_policy.get("requires_submission", True))
    completed = (discussion_pass or not requires_discussion) and (submitted or not requires_submission)
    overdue = bool(due_ts and now_ts > due_ts and not completed)
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
    )
    payload: Optional[Dict[str, Any]] = None
    if include_student_payload:
        payload = {
            "student_id": student_id,
            "student_name": profile.get("student_name") or "",
            "class_name": profile.get("class_name") or "",
            "discussion": discussion,
            "submission": {"attempts": len(attempts), "best": best},
            "completion": {"policy": completion_policy, "checks": completion_checks},
            "evidence": evidence,
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
    completion_policy = _normalize_completion_policy(meta)
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
            completion_policy=completion_policy,
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
    except Exception:  # policy: allowed-broad-except
        _log.warning("failed to write progress.json for assignment %s", assignment_id, exc_info=True)

    return result
