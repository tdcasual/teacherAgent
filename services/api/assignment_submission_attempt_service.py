from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


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
    except Exception:
        status = ""
    if status == "ungraded":
        return False
    try:
        conf = float(item.get("confidence") or 0.0)
    except Exception:
        conf = 0.0
    return conf >= deps.grade_count_conf_threshold


def compute_submission_attempt(attempt_dir: Path, *, deps: AssignmentSubmissionAttemptDeps) -> Optional[Dict[str, Any]]:
    report_path = attempt_dir / "grading_report.json"
    if not report_path.exists():
        return None
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(report, dict):
        return None

    items = report.get("items") or []
    if not isinstance(items, list):
        items = []

    score_earned = 0.0
    counted = 0
    for it in items:
        if not isinstance(it, dict):
            continue
        if counted_grade_item(it, deps=deps):
            counted += 1
            try:
                score_earned += float(it.get("score") or 0.0)
            except Exception:
                pass

    try:
        graded_total = int(report.get("graded_total") or 0)
    except Exception:
        graded_total = counted
    try:
        correct = int(report.get("correct") or 0)
    except Exception:
        correct = 0
    try:
        ungraded = int(report.get("ungraded") or 0)
    except Exception:
        ungraded = 0

    submitted_at = ""
    try:
        m = re.match(r"submission_(\d{8})_(\d{6})", attempt_dir.name)
        if m:
            dt = datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")
            submitted_at = dt.isoformat(timespec="seconds")
    except Exception:
        submitted_at = ""
    if not submitted_at:
        try:
            submitted_at = datetime.fromtimestamp(report_path.stat().st_mtime).isoformat(timespec="seconds")
        except Exception:
            submitted_at = ""

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
        except Exception:
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
