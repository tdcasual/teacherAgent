from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from .assignment.visibility import assignment_owner_id, effective_visibility_status
from .auth.identity_graph_service import student_enrolled as _student_enrolled
from .auth_registry_service import build_auth_registry_store
from .settings import env_int

_log = logging.getLogger(__name__)
_DEFAULT_LIST_LIMIT = 50
_MAX_LIST_LIMIT = 100
_PROCESS_STATUSES = frozenset({"none", "pending", "frozen", "partial"})


@dataclass(frozen=True)
class StudentAssignmentListDeps:
    data_dir: Path
    load_assignment_meta: Callable[[Path], Dict[str, Any]]
    student_enrolled: Callable[[str, str, str], bool]
    list_submission_attempts: Callable[[str, str], List[Dict[str, Any]]]
    lookback_days: int = 14


def today_lookback_days() -> int:
    return max(0, env_int("ASSIGNMENT_TODAY_LOOKBACK_DAYS", 14))


def auto_archive_days() -> int:
    return max(0, env_int("ASSIGNMENT_AUTO_ARCHIVE_DAYS", 7))


def student_currently_enrolled(
    student_id: str,
    teacher_id: str,
    subject_id: str,
    *,
    data_dir: Optional[Path] = None,
) -> bool:
    try:
        store = build_auth_registry_store(data_dir=data_dir)
        return _student_enrolled(
            store,
            student_id=student_id,
            teacher_id=teacher_id,
            subject_id=subject_id,
        )
    except Exception:  # policy: allowed-broad-except
        _log.warning("enrollment lookup failed", exc_info=True)
        return False


def assigned_date_of(meta: Dict[str, Any]) -> Optional[date]:
    raw_date = str(meta.get("date") or "").strip()
    parsed = _parse_date_value(raw_date)
    if parsed is not None:
        return parsed
    generated = str(meta.get("generated_at") or "").strip()
    return _parse_date_value(generated)


def local_overdue(today: date, due_at: Any, *, submitted: bool) -> bool:
    due_date = _parse_date_value(due_at)
    if due_date is None or submitted:
        return False
    return today > due_date


def snapshot_student_ids(meta: Dict[str, Any]) -> List[str]:
    raw = meta.get("expected_students")
    if not isinstance(raw, list):
        return []
    return [str(item).strip() for item in raw if str(item).strip()]


def student_on_snapshot(meta: Dict[str, Any], student_id: str) -> bool:
    sid = str(student_id or "").strip()
    return bool(sid) and sid in snapshot_student_ids(meta)


def _parse_date_value(value: Any) -> Optional[date]:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _qualifying_attempt(attempts: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    valid = [item for item in attempts if isinstance(item, dict) and item.get("valid_submission")]
    if not valid:
        return None
    return max(valid, key=lambda item: str(item.get("submitted_at") or ""))


def _official_score(attempt: Optional[Dict[str, Any]]) -> Any:
    if not attempt:
        return None
    try:
        return float(attempt.get("score_earned"))
    except (TypeError, ValueError):
        return None


def _process_archive_status(folder: Path, student_id: str) -> str:
    path = folder / "process_archives" / f"{student_id}.json"
    if not path.exists():
        return "none"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "none"
    if not isinstance(payload, dict):
        return "none"
    status = str(payload.get("status") or "none").strip().lower()
    return status if status in _PROCESS_STATUSES else "none"


def _iter_assignment_folders(data_dir: Path) -> Iterable[Path]:
    assignments_dir = data_dir / "assignments"
    if not assignments_dir.exists():
        return
    for folder in assignments_dir.iterdir():
        if folder.is_dir():
            yield folder


def _owner_and_subject(meta: Dict[str, Any]) -> Tuple[str, str]:
    return assignment_owner_id(meta), str(meta.get("subject_id") or "").strip()


def _on_live_roster(meta: Dict[str, Any], student_id: str, deps: StudentAssignmentListDeps) -> bool:
    teacher_id, subject_id = _owner_and_subject(meta)
    if not teacher_id or not subject_id:
        return False
    return bool(deps.student_enrolled(student_id, teacher_id, subject_id))


def _today_visible(
    *,
    assigned_date: Optional[date],
    overdue: bool,
    submitted: bool,
    today: date,
    lookback_days: int,
) -> bool:
    if assigned_date is not None and assigned_date > today:
        return False
    if submitted:
        return False
    if overdue:
        return True
    if assigned_date is None:
        return False
    return (today - assigned_date).days <= lookback_days


def _due_sort_value(due_at: str) -> str:
    return due_at or "9999-12-31T23:59:59"


def _today_sort_key(item: Dict[str, Any]) -> tuple:
    overdue = 0 if item.get("progress", {}).get("overdue") else 1
    return (
        overdue,
        str(item.get("subject_id") or ""),
        str(item.get("teacher_id") or ""),
        _due_sort_value(str(item.get("due_at") or "")),
    )


def _today_item(
    folder: Path,
    meta: Dict[str, Any],
    *,
    student_id: str,
    today: date,
    deps: StudentAssignmentListDeps,
) -> Optional[Dict[str, Any]]:
    vis = effective_visibility_status(meta)
    teacher_id, subject_id = _owner_and_subject(meta)
    if vis != "published" or not teacher_id or not subject_id:
        return None
    if not student_on_snapshot(meta, student_id):
        return None
    if not _on_live_roster(meta, student_id, deps):
        return None
    attempts = deps.list_submission_attempts(str(meta.get("assignment_id") or folder.name), student_id)
    best = _qualifying_attempt(attempts)
    submitted = bool(best)
    due_at = str(meta.get("due_at") or "").strip()
    overdue = local_overdue(today, due_at, submitted=submitted)
    assigned_date = assigned_date_of(meta)
    if not _today_visible(
        assigned_date=assigned_date,
        overdue=overdue,
        submitted=submitted,
        today=today,
        lookback_days=int(deps.lookback_days),
    ):
        return None
    assignment_id = str(meta.get("assignment_id") or folder.name)
    return {
        "assignment_id": assignment_id,
        "teacher_id": teacher_id,
        "subject_id": subject_id,
        "title": str(meta.get("title") or assignment_id),
        "due_at": due_at,
        "progress": {
            "submitted": submitted,
            "overdue": overdue,
            "official_score": _official_score(best),
            "process_archive_status": _process_archive_status(folder, student_id),
        },
    }


def list_assignments_for_student(
    *,
    student_id: str,
    date_str: str,
    deps: StudentAssignmentListDeps,
) -> List[Dict[str, Any]]:
    today = date.fromisoformat(str(date_str))
    items: List[Dict[str, Any]] = []
    sid = str(student_id or "").strip()
    if not sid:
        return []
    for folder in _iter_assignment_folders(deps.data_dir):
        try:
            meta = deps.load_assignment_meta(folder)
        except Exception:  # policy: allowed-broad-except
            _log.debug("skip unreadable assignment meta", exc_info=True)
            continue
        if not isinstance(meta, dict):
            continue
        item = _today_item(folder, meta, student_id=sid, today=today, deps=deps)
        if item is not None:
            items.append(item)
    items.sort(key=_today_sort_key)
    return items


def _normalize_paging(limit: Any, cursor: Any) -> tuple[int, int]:
    try:
        limit_int = int(limit)
    except (TypeError, ValueError):
        limit_int = _DEFAULT_LIST_LIMIT
    try:
        cursor_int = int(cursor)
    except (TypeError, ValueError):
        cursor_int = 0
    if limit_int <= 0:
        limit_int = _DEFAULT_LIST_LIMIT
    return min(limit_int, _MAX_LIST_LIMIT), max(0, cursor_int)


def _history_item(
    folder: Path,
    meta: Dict[str, Any],
    *,
    student_id: str,
    deps: StudentAssignmentListDeps,
) -> Optional[Dict[str, Any]]:
    vis = effective_visibility_status(meta)
    teacher_id, subject_id = _owner_and_subject(meta)
    if vis not in {"published", "archived"} or not teacher_id or not subject_id:
        return None
    if not student_on_snapshot(meta, student_id):
        return None
    if vis == "published" and not _on_live_roster(meta, student_id, deps):
        return None
    assignment_id = str(meta.get("assignment_id") or folder.name)
    attempts = deps.list_submission_attempts(assignment_id, student_id)
    best = _qualifying_attempt(attempts)
    return {
        "assignment_id": assignment_id,
        "teacher_id": teacher_id,
        "subject_id": subject_id,
        "title": str(meta.get("title") or assignment_id),
        "due_at": str(meta.get("due_at") or "").strip(),
        "visibility_status": vis,
        "submitted": bool(best),
        "official_score": _official_score(best),
        "archived_at": meta.get("archived_at"),
    }


def _history_sort_key(item: Dict[str, Any]) -> tuple:
    return (
        str(item.get("archived_at") or item.get("due_at") or ""),
        str(item.get("assignment_id") or ""),
    )


def list_student_assignment_history(
    *,
    student_id: str,
    limit: Any = _DEFAULT_LIST_LIMIT,
    cursor: Any = 0,
    deps: StudentAssignmentListDeps,
) -> Dict[str, Any]:
    limit_int, cursor_int = _normalize_paging(limit, cursor)
    sid = str(student_id or "").strip()
    items: List[Dict[str, Any]] = []
    if sid:
        for folder in _iter_assignment_folders(deps.data_dir):
            try:
                meta = deps.load_assignment_meta(folder)
            except Exception:  # policy: allowed-broad-except
                _log.debug("skip unreadable assignment meta", exc_info=True)
                continue
            if not isinstance(meta, dict):
                continue
            item = _history_item(folder, meta, student_id=sid, deps=deps)
            if item is not None:
                items.append(item)
    items.sort(key=_history_sort_key, reverse=True)
    total = len(items)
    page = items[cursor_int : cursor_int + limit_int]
    next_cursor = cursor_int + len(page)
    return {
        "assignments": page,
        "total": total,
        "limit": limit_int,
        "cursor": cursor_int,
        "next_cursor": next_cursor if next_cursor < total else None,
        "has_more": next_cursor < total,
    }
