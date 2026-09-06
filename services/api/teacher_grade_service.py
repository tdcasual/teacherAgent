from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .assignment.visibility import assignment_owner_id
from .auth_service import AuthPrincipal, auth_required
from .fs_atomic import atomic_write_json
from .paths import DATA_DIR

_log = logging.getLogger(__name__)
_TEACHER_GRADE_SCHEMA = "teacher_grade/v1"


class TeacherGradeError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = int(status_code)
        self.detail = str(detail or "teacher_grade_failed")


def _resolve_data_dir(data_dir: Optional[Path]) -> Path:
    if data_dir is not None:
        return Path(data_dir)
    env_data_dir = str(os.getenv("DATA_DIR", "") or "").strip()
    return Path(env_data_dir) if env_data_dir else Path(DATA_DIR)


def _is_safe_id_token(token: str) -> bool:
    value = str(token or "").strip()
    if not value or value in {".", ".."}:
        return False
    if "/" in value or "\\" in value:
        return False
    return True


def _safe_child(root: Path, *parts: str) -> Optional[Path]:
    resolved_root = root.resolve()
    tokens = [str(part or "").strip() for part in parts]
    if not tokens or any(not _is_safe_id_token(token) for token in tokens):
        return None
    target = resolved_root.joinpath(*tokens).resolve()
    if resolved_root not in target.parents:
        return None
    if len(tokens) >= 2:
        assignment_root = (resolved_root / tokens[0]).resolve()
        if assignment_root not in target.parents:
            return None
    return target


def _student_grade_dir(data_dir: Path, assignment_id: str, student_id: str) -> Optional[Path]:
    if not _is_safe_id_token(assignment_id) or not _is_safe_id_token(student_id):
        return None
    return _safe_child(data_dir / "student_submissions", assignment_id, student_id)


def _assignment_folder(data_dir: Path, assignment_id: str) -> Path:
    aid = str(assignment_id or "").strip()
    if not aid:
        raise TeacherGradeError(400, "assignment_id is required")
    folder = _safe_child(data_dir / "assignments", aid)
    if folder is None:
        raise TeacherGradeError(400, "invalid assignment_id")
    return folder


def _require_student_id(student_id: str) -> str:
    sid = str(student_id or "").strip()
    if not sid:
        raise TeacherGradeError(400, "student_id is required")
    if not _is_safe_id_token(sid):
        raise TeacherGradeError(400, "invalid_student_id")
    return sid


def _load_meta(folder: Path) -> Dict[str, Any]:
    meta_path = folder / "meta.json"
    if not meta_path.exists():
        raise TeacherGradeError(404, "assignment not found")
    try:
        payload = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TeacherGradeError(400, "invalid_assignment_meta") from exc
    return payload if isinstance(payload, dict) else {}


def _require_owner(meta: Dict[str, Any], principal: Optional[AuthPrincipal]) -> None:
    if principal is None:
        if not auth_required():
            return
        raise TeacherGradeError(401, "missing_authorization")
    if principal.role == "admin":
        return
    owner = assignment_owner_id(meta)
    actor = str(principal.actor_id or "").strip()
    if not actor:
        raise TeacherGradeError(400, "teacher_id_required")
    if not owner or owner != actor:
        raise TeacherGradeError(403, "forbidden_assignment_owner")


def _optional_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise TeacherGradeError(400, "invalid_override_score") from exc
    if number != number or number in {float("inf"), float("-inf")}:
        raise TeacherGradeError(400, "invalid_override_score")
    return number


def _normalize_excerpts(raw: Any) -> List[Dict[str, str]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise TeacherGradeError(400, "invalid_adopted_coach_excerpts")
    excerpts: List[Dict[str, str]] = []
    for item in raw:
        if isinstance(item, str):
            text = item.strip()
            if text:
                excerpts.append({"session_id": "", "turn_ref": "", "text": text})
            continue
        if not isinstance(item, dict):
            raise TeacherGradeError(400, "invalid_adopted_coach_excerpts")
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        excerpts.append(
            {
                "session_id": str(item.get("session_id") or "").strip(),
                "turn_ref": str(item.get("turn_ref") or "").strip(),
                "text": text,
            }
        )
    return excerpts


def _empty_grade(assignment_id: str, student_id: str) -> Dict[str, Any]:
    return {
        "schema": _TEACHER_GRADE_SCHEMA,
        "assignment_id": assignment_id,
        "student_id": student_id,
        "attempt_id": "",
        "teacher_id": "",
        "override_score_earned": None,
        "comment": "",
        "adopted_coach_excerpts": [],
        "updated_at": "",
    }


def load_teacher_grade(
    data_dir: Path,
    assignment_id: str,
    student_id: str,
) -> Optional[Dict[str, Any]]:
    folder = _student_grade_dir(Path(data_dir), assignment_id, student_id)
    if folder is None:
        return None
    path = folder / "teacher_grade.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        _log.warning("corrupt teacher_grade.json at %s", path, exc_info=True)
        return None
    return payload if isinstance(payload, dict) else None


def official_score_from(
    *,
    auto_score: Any,
    teacher_grade: Optional[Dict[str, Any]],
) -> Optional[float]:
    if isinstance(teacher_grade, dict) and teacher_grade.get("override_score_earned") is not None:
        try:
            return float(teacher_grade.get("override_score_earned"))
        except (TypeError, ValueError):
            _log.debug("invalid override_score_earned", exc_info=True)
    if auto_score is None or auto_score == "":
        return None
    try:
        return float(auto_score)
    except (TypeError, ValueError):
        return None


def updates_from_grade_request(req: Any) -> Dict[str, Any]:
    fields = set(getattr(req, "model_fields_set", set()) or [])
    updates: Dict[str, Any] = {}
    if "override_score" in fields:
        updates["override_score"] = getattr(req, "override_score", None)
    elif "override_score_earned" in fields:
        updates["override_score_earned"] = getattr(req, "override_score_earned", None)
    if "comment" in fields:
        updates["comment"] = getattr(req, "comment", None)
    if "adopted_coach_excerpts" in fields:
        updates["adopted_coach_excerpts"] = getattr(req, "adopted_coach_excerpts", None)
    if "attempt_id" in fields:
        updates["attempt_id"] = getattr(req, "attempt_id", None)
    return updates


def _apply_updates(existing: Dict[str, Any], updates: Dict[str, Any]) -> None:
    if "override_score" in updates:
        existing["override_score_earned"] = _optional_float(updates.get("override_score"))
    elif "override_score_earned" in updates:
        existing["override_score_earned"] = _optional_float(updates.get("override_score_earned"))
    if "comment" in updates:
        existing["comment"] = str(updates.get("comment") or "")
    if "adopted_coach_excerpts" in updates:
        existing["adopted_coach_excerpts"] = _normalize_excerpts(updates.get("adopted_coach_excerpts"))
    if "attempt_id" in updates:
        existing["attempt_id"] = str(updates.get("attempt_id") or "").strip()


def save_teacher_grade(
    assignment_id: str,
    student_id: str,
    *,
    principal: Optional[AuthPrincipal],
    data_dir: Optional[Path] = None,
    updates: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    resolved = _resolve_data_dir(data_dir)
    folder = _assignment_folder(resolved, assignment_id)
    if not folder.exists():
        raise TeacherGradeError(404, "assignment not found")
    sid = _require_student_id(student_id)
    grade_dir = _student_grade_dir(resolved, str(assignment_id).strip(), sid)
    if grade_dir is None:
        raise TeacherGradeError(400, "invalid_student_id")
    meta = _load_meta(folder)
    _require_owner(meta, principal)
    existing = load_teacher_grade(resolved, str(assignment_id).strip(), sid) or _empty_grade(
        str(meta.get("assignment_id") or assignment_id),
        sid,
    )
    existing["schema"] = _TEACHER_GRADE_SCHEMA
    existing["assignment_id"] = str(meta.get("assignment_id") or assignment_id)
    existing["student_id"] = sid
    _apply_updates(existing, updates or {})
    actor = str(getattr(principal, "actor_id", "") or "").strip()
    if actor:
        existing["teacher_id"] = actor
    elif not str(existing.get("teacher_id") or "").strip():
        existing["teacher_id"] = assignment_owner_id(meta)
    existing["updated_at"] = datetime.now().isoformat(timespec="seconds")
    atomic_write_json(grade_dir / "teacher_grade.json", existing)
    return {
        "ok": True,
        "assignment_id": existing["assignment_id"],
        "student_id": sid,
        "teacher_grade": existing,
    }


def save_teacher_grade_from_request(
    assignment_id: str,
    student_id: str,
    *,
    principal: Optional[AuthPrincipal],
    data_dir: Optional[Path] = None,
    request: Any,
) -> Dict[str, Any]:
    return save_teacher_grade(
        assignment_id,
        student_id,
        principal=principal,
        data_dir=data_dir,
        updates=updates_from_grade_request(request),
    )
