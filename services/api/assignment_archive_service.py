from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .assignment.visibility import assignment_owner_id, effective_visibility_status
from .auth_service import AuthPrincipal
from .fs_atomic import atomic_write_json
from .paths import DATA_DIR
from .paths import today_iso as _today_iso
from .settings import env_int

_log = logging.getLogger(__name__)


class AssignmentArchiveError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = int(status_code)
        self.detail = str(detail or "assignment_archive_failed")


def _resolve_data_dir(data_dir: Optional[Path]) -> Path:
    if data_dir is not None:
        return Path(data_dir)
    env_data_dir = str(os.getenv("DATA_DIR", "") or "").strip()
    return Path(env_data_dir) if env_data_dir else Path(DATA_DIR)


def _resolve_assignment_folder(assignment_id: str, data_dir: Path) -> Path:
    aid = str(assignment_id or "").strip()
    if not aid:
        raise AssignmentArchiveError(400, "assignment_id is required")
    root = (data_dir / "assignments").resolve()
    folder = (root / aid).resolve()
    if folder != root and root not in folder.parents:
        raise AssignmentArchiveError(400, "invalid assignment_id")
    return folder


def _load_meta(folder: Path) -> Dict[str, Any]:
    meta_path = folder / "meta.json"
    if not meta_path.exists():
        raise AssignmentArchiveError(404, "assignment not found")
    try:
        payload = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AssignmentArchiveError(400, "invalid_assignment_meta") from exc
    return payload if isinstance(payload, dict) else {}


def _require_owner(meta: Dict[str, Any], principal: Optional[AuthPrincipal]) -> None:
    if principal is None:
        raise AssignmentArchiveError(401, "missing_authorization")
    if principal.role == "admin":
        return
    owner = assignment_owner_id(meta)
    actor = str(principal.actor_id or "").strip()
    if not actor:
        raise AssignmentArchiveError(400, "teacher_id_required")
    if not owner or owner != actor:
        raise AssignmentArchiveError(403, "forbidden_assignment_owner")


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def archive_assignment(
    assignment_id: str,
    *,
    principal: Optional[AuthPrincipal],
    data_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    resolved = _resolve_data_dir(data_dir)
    folder = _resolve_assignment_folder(assignment_id, resolved)
    if not folder.exists():
        raise AssignmentArchiveError(404, "assignment not found")
    meta = _load_meta(folder)
    _require_owner(meta, principal)
    vis = effective_visibility_status(meta)
    if vis not in {"published", "archived"}:
        raise AssignmentArchiveError(409, "invalid_visibility_status")
    meta["visibility_status"] = "archived"
    meta["archived_at"] = _now_iso()
    meta.pop("auto_archive_exempt", None)
    meta.pop("auto_archive_exempt_until", None)
    atomic_write_json(folder / "meta.json", meta)
    return {
        "ok": True,
        "assignment_id": str(meta.get("assignment_id") or assignment_id),
        "visibility_status": "archived",
        "archived_at": meta["archived_at"],
    }


def unarchive_assignment(
    assignment_id: str,
    *,
    principal: Optional[AuthPrincipal],
    data_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    resolved = _resolve_data_dir(data_dir)
    folder = _resolve_assignment_folder(assignment_id, resolved)
    if not folder.exists():
        raise AssignmentArchiveError(404, "assignment not found")
    meta = _load_meta(folder)
    _require_owner(meta, principal)
    if effective_visibility_status(meta) != "archived":
        raise AssignmentArchiveError(409, "invalid_visibility_status")
    meta["visibility_status"] = "published"
    meta["archived_at"] = None
    today = date.fromisoformat(_today_iso())
    meta["auto_archive_exempt_until"] = (today + timedelta(days=1)).isoformat()
    meta.pop("auto_archive_exempt", None)
    atomic_write_json(folder / "meta.json", meta)
    return {
        "ok": True,
        "assignment_id": str(meta.get("assignment_id") or assignment_id),
        "visibility_status": "published",
        "archived_at": None,
        "auto_archive_exempt_until": meta["auto_archive_exempt_until"],
    }


def _parse_date_value(value: Any) -> Optional[date]:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _qualifying_attempts(attempts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [item for item in attempts if isinstance(item, dict) and item.get("valid_submission")]


def _qualifying_submitted(attempts: List[Dict[str, Any]]) -> bool:
    return bool(_qualifying_attempts(attempts))


def _latest_submitted_date(attempts: List[Dict[str, Any]]) -> Optional[date]:
    dates = [_parse_date_value(item.get("submitted_at")) for item in _qualifying_attempts(attempts)]
    present = [item for item in dates if item is not None]
    return max(present) if present else None


def _is_auto_archive_exempt(meta: Dict[str, Any], today: date) -> bool:
    until = _parse_date_value(meta.get("auto_archive_exempt_until"))
    return until is not None and today <= until


def _maybe_auto_archive_inner(
    assignment_id: str,
    *,
    data_dir: Path,
    today: date,
    auto_archive_days: int,
    list_submission_attempts: Callable[[str, str], List[Dict[str, Any]]],
    owner_teacher_id: Optional[str] = None,
) -> bool:
    folder = _resolve_assignment_folder(assignment_id, data_dir)
    if not folder.exists():
        return False
    meta = _load_meta(folder)
    requested_owner = str(owner_teacher_id or "").strip()
    if requested_owner and assignment_owner_id(meta) != requested_owner:
        return False
    if effective_visibility_status(meta) != "published":
        return False
    if _is_auto_archive_exempt(meta, today):
        return False
    expected = meta.get("expected_students")
    if not isinstance(expected, list) or not expected:
        return False
    student_ids = [str(item).strip() for item in expected if str(item).strip()]
    if not student_ids:
        return False
    due_date = _parse_date_value(meta.get("due_at"))
    if due_date is not None and not (today > due_date):
        return False
    latest: Optional[date] = None
    for sid in student_ids:
        attempts = list_submission_attempts(assignment_id, sid)
        if not _qualifying_submitted(attempts):
            return False
        submitted_date = _latest_submitted_date(attempts)
        if submitted_date is not None and (latest is None or submitted_date > latest):
            latest = submitted_date
    if latest is None:
        return False
    if (today - latest).days < int(auto_archive_days):
        return False
    meta["visibility_status"] = "archived"
    meta["archived_at"] = _now_iso()
    meta.pop("auto_archive_exempt", None)
    meta.pop("auto_archive_exempt_until", None)
    atomic_write_json(folder / "meta.json", meta)
    return True


def maybe_auto_archive(
    assignment_id: str,
    *,
    data_dir: Optional[Path] = None,
    today_iso: Optional[str] = None,
    auto_archive_days: Optional[int] = None,
    list_submission_attempts: Optional[Callable[[str, str], List[Dict[str, Any]]]] = None,
    owner_teacher_id: Optional[str] = None,
) -> bool:
    try:
        resolved = _resolve_data_dir(data_dir)
        if list_submission_attempts is None:
            from .core_services_application import list_submission_attempts as _list_attempts

            list_fn = _list_attempts
        else:
            list_fn = list_submission_attempts
        days = int(auto_archive_days) if auto_archive_days is not None else max(0, env_int("ASSIGNMENT_AUTO_ARCHIVE_DAYS", 7))
        today = date.fromisoformat(str(today_iso or _today_iso()))
        return _maybe_auto_archive_inner(
            assignment_id,
            data_dir=resolved,
            today=today,
            auto_archive_days=days,
            list_submission_attempts=list_fn,
            owner_teacher_id=owner_teacher_id,
        )
    except Exception:  # policy: allowed-broad-except
        _log.warning("assignment.auto_archive.error assignment_id=%s", assignment_id, exc_info=True)
        return False


def maybe_auto_archive_owner_assignments(
    owner_teacher_id: Optional[str],
    *,
    data_dir: Optional[Path] = None,
    today_iso: Optional[str] = None,
    list_submission_attempts: Optional[Callable[[str, str], List[Dict[str, Any]]]] = None,
) -> None:
    resolved = _resolve_data_dir(data_dir)
    assignments_dir = resolved / "assignments"
    if not assignments_dir.exists():
        return
    owner = str(owner_teacher_id or "").strip()
    for folder in assignments_dir.iterdir():
        if not folder.is_dir():
            continue
        try:
            meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
        except Exception:  # policy: allowed-broad-except
            _log.debug("skip unreadable assignment during auto-archive scan", exc_info=True)
            continue
        if not isinstance(meta, dict):
            continue
        if owner and assignment_owner_id(meta) != owner:
            continue
        maybe_auto_archive(
            str(meta.get("assignment_id") or folder.name),
            data_dir=resolved,
            today_iso=today_iso,
            list_submission_attempts=list_submission_attempts,
            owner_teacher_id=owner or None,
        )
