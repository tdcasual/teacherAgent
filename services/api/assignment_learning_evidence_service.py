from __future__ import annotations

from typing import Any, Dict, List, Optional


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def build_assignment_progress_evidence(
    *,
    assignment_id: str,
    student_id: str,
    discussion: Dict[str, Any],
    attempts: List[Dict[str, Any]],
    best_attempt: Optional[Dict[str, Any]],
    completion_policy: Dict[str, Any],
    completed: bool,
) -> Dict[str, Any]:
    signals: Dict[str, Any] = {
        "discussion_pass": bool(discussion.get("pass")),
        "discussion_message_count": _safe_int(discussion.get("message_count"), 0),
        "submission_attempts": len(attempts),
        "submitted": bool(best_attempt),
        "best_attempt_id": str((best_attempt or {}).get("attempt_id") or ""),
        "best_score_earned": _safe_float((best_attempt or {}).get("score_earned"), 0.0),
        "best_graded_total": _safe_int((best_attempt or {}).get("graded_total"), 0),
        "completed": bool(completed),
        "completion_policy_version": _safe_int(completion_policy.get("version"), 1),
        "requires_discussion": bool(completion_policy.get("requires_discussion", True)),
        "requires_submission": bool(completion_policy.get("requires_submission", True)),
        "min_graded_total": _safe_int(completion_policy.get("min_graded_total"), 1),
        "best_attempt_strategy": str(
            completion_policy.get("best_attempt") or "score_earned_then_correct_then_graded_total"
        ),
    }
    return {
        "schema": "assignment_progress_evidence/v1",
        "source": "assignment_progress",
        "assignment_id": str(assignment_id or "").strip(),
        "student_id": str(student_id or "").strip(),
        "signals": signals,
    }
