from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class AssignmentSubmissionAttemptDeps:
    student_submissions_dir: Path
    grade_count_conf_threshold: float


def _resolve_submission_base(
    student_submissions_dir: Path,
    assignment_id: str,
    student_id: str,
) -> Optional[Path]:
    root = student_submissions_dir.resolve()
    aid = str(assignment_id or "").strip()
    sid = str(student_id or "").strip()
    if not aid or not sid:
        return None
    target = (root / aid / sid).resolve()
    if target != root and root not in target.parents:
        return None
    return target


def counted_grade_item(item: Dict[str, Any], *, deps: AssignmentSubmissionAttemptDeps) -> bool:
    try:
        status = str(item.get("status") or "")
    except Exception:  # policy: allowed-broad-except
        _log.warning("operation failed", exc_info=True)
        status = ""
    if status == "ungraded":
        return False
    try:
        conf = float(item.get("confidence") or 0.0)
    except Exception:  # policy: allowed-broad-except
        _log.warning("numeric conversion failed", exc_info=True)
        conf = 0.0
    return conf >= deps.grade_count_conf_threshold


def _load_attempt_report(report_path: Path) -> Optional[Dict[str, Any]]:
    if not report_path.exists():
        return None
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception:  # policy: allowed-broad-except
        _log.warning("corrupt grading_report.json at %s", report_path, exc_info=True)
        return None
    return report if isinstance(report, dict) else None


def _report_items(report: Dict[str, Any]) -> List[Any]:
    items = report.get("items") or []
    return items if isinstance(items, list) else []


def _counted_score_summary(
    items: List[Any],
    *,
    deps: AssignmentSubmissionAttemptDeps,
) -> tuple[float, int]:
    score_earned = 0.0
    counted = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        if not counted_grade_item(item, deps=deps):
            continue
        counted += 1
        try:
            score_earned += float(item.get("score") or 0.0)
        except Exception:  # policy: allowed-broad-except
            _log.warning("numeric conversion failed", exc_info=True)
    return score_earned, counted


def _report_int(report: Dict[str, Any], key: str, default: int) -> int:
    try:
        return int(report.get(key) or 0)
    except Exception:  # policy: allowed-broad-except
        _log.warning("numeric conversion failed", exc_info=True)
        return default


def _submitted_at_from_attempt_name(attempt_name: str) -> str:
    try:
        match = re.match(r"submission_(\d{8})_(\d{6})", attempt_name)
        if not match:
            return ""
        dt = datetime.strptime(match.group(1) + match.group(2), "%Y%m%d%H%M%S")
        return dt.isoformat(timespec="seconds")
    except Exception:  # policy: allowed-broad-except
        _log.warning("operation failed", exc_info=True)
        return ""


def _submitted_at_from_report_mtime(report_path: Path) -> str:
    try:
        return datetime.fromtimestamp(report_path.stat().st_mtime).isoformat(timespec="seconds")
    except Exception:  # policy: allowed-broad-except
        _log.warning("file stat failed", exc_info=True)
        return ""


def _resolve_submitted_at(attempt_dir: Path, report_path: Path) -> str:
    submitted_at = _submitted_at_from_attempt_name(attempt_dir.name)
    if submitted_at:
        return submitted_at
    return _submitted_at_from_report_mtime(report_path)


def compute_submission_attempt(attempt_dir: Path, *, deps: AssignmentSubmissionAttemptDeps) -> Optional[Dict[str, Any]]:
    report_path = attempt_dir / "grading_report.json"
    report = _load_attempt_report(report_path)
    if report is None:
        return None

    items = _report_items(report)
    score_earned, counted = _counted_score_summary(items, deps=deps)
    graded_total = _report_int(report, "graded_total", counted)
    correct = _report_int(report, "correct", 0)
    ungraded = _report_int(report, "ungraded", 0)
    submitted_at = _resolve_submitted_at(attempt_dir, report_path)

    return {
        "attempt_id": attempt_dir.name,
        "submitted_at": submitted_at,
        "graded_total": graded_total,
        "correct": correct,
        "ungraded": ungraded,
        "score_earned": round(score_earned, 3),
        "valid_submission": bool(graded_total and graded_total > 0),
        "report_path": str(report_path),
    }


def list_submission_attempts(
    assignment_id: str,
    student_id: str,
    *,
    deps: AssignmentSubmissionAttemptDeps,
) -> List[Dict[str, Any]]:
    base = _resolve_submission_base(deps.student_submissions_dir, assignment_id, student_id)
    if base is None:
        return []
    if not base.exists():
        return []
    attempts: List[Dict[str, Any]] = []
    for attempt_dir in sorted(base.glob("submission_*")):
        if not attempt_dir.is_dir():
            continue
        info = compute_submission_attempt(attempt_dir, deps=deps)
        if info:
            attempts.append(info)
    return attempts


def best_submission_attempt(attempts: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    valid = [a for a in attempts if a.get("valid_submission")]
    if not valid:
        return None

    def _ts(v: str) -> float:
        try:
            return datetime.fromisoformat(v).timestamp()
        except Exception:  # policy: allowed-broad-except
            _log.warning("operation failed", exc_info=True)
            return 0.0

    valid.sort(
        key=lambda a: (
            float(a.get("score_earned") or 0.0),
            int(a.get("correct") or 0),
            int(a.get("graded_total") or 0),
            _ts(str(a.get("submitted_at") or "")),
        ),
        reverse=True,
    )
    return valid[0]
