from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
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


def compute_assignment_progress(
    assignment_id: str,
    *,
    deps: AssignmentProgressDeps,
    include_students: bool = True,
) -> Dict[str, Any]:
    folder = deps.data_dir / "assignments" / assignment_id
    if not folder.exists():
        return {"ok": False, "error": "assignment_not_found", "assignment_id": assignment_id}
    meta = deps.load_assignment_meta(folder)
    if not meta:
        meta = {"assignment_id": assignment_id}

    deps.postprocess_assignment_meta(assignment_id)
    meta = deps.load_assignment_meta(folder) or meta

    expected_raw = meta.get("expected_students")
    expected_students: List[str] = []
    if isinstance(expected_raw, list):
        expected_students = [str(s).strip() for s in expected_raw if str(s).strip()]

    due_at = deps.normalize_due_at(meta.get("due_at"))
    due_ts = None
    if due_at:
        try:
            due_ts = datetime.fromisoformat(due_at.replace("Z", "+00:00")).timestamp()
        except Exception:
            due_ts = None

    now_ts = deps.time_time()
    profiles = {p.get("student_id"): p for p in deps.list_all_student_profiles() if p.get("student_id")}

    students_out: List[Dict[str, Any]] = []
    discussion_pass_count = 0
    submission_count = 0
    completed_count = 0
    overdue_count = 0

    for sid in expected_students:
        p = profiles.get(sid) or {}
        discussion = deps.session_discussion_pass(sid, assignment_id)
        discussion_pass = bool(discussion.get("pass"))
        if discussion_pass:
            discussion_pass_count += 1

        attempts = deps.list_submission_attempts(assignment_id, sid)
        best = deps.best_submission_attempt(attempts)
        submitted = bool(best)
        if submitted:
            submission_count += 1

        complete = discussion_pass and submitted
        if complete:
            completed_count += 1

        overdue = bool(due_ts and now_ts > due_ts and not complete)
        if overdue:
            overdue_count += 1

        if include_students:
            students_out.append(
                {
                    "student_id": sid,
                    "student_name": p.get("student_name") or "",
                    "class_name": p.get("class_name") or "",
                    "discussion": discussion,
                    "submission": {
                        "attempts": len(attempts),
                        "best": best,
                    },
                    "complete": complete,
                    "overdue": overdue,
                }
            )

    if include_students:
        students_out.sort(
            key=lambda x: (
                str(x.get("class_name") or ""),
                str(x.get("student_name") or ""),
                str(x.get("student_id") or ""),
            )
        )

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
        pass

    return result
