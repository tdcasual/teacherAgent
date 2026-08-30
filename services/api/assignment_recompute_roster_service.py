from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from .auth_registry_service import build_auth_registry_store
from .auth_service import AuthPrincipal
from .core_utils import parse_ids_value, resolve_scope
from .fs_atomic import atomic_write_json
from .paths import DATA_DIR


class AssignmentRecomputeRosterError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = int(status_code)
        self.detail = str(detail or "recompute_roster_failed")


def _load_meta(folder: Path) -> Dict[str, Any]:
    meta_path = folder / "meta.json"
    if not meta_path.exists():
        raise AssignmentRecomputeRosterError(404, "assignment not found")
    try:
        payload = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AssignmentRecomputeRosterError(400, "invalid_assignment_meta") from exc
    return payload if isinstance(payload, dict) else {}


def _require_owner(meta: Dict[str, Any], principal: Optional[AuthPrincipal]) -> None:
    if principal is None:
        raise AssignmentRecomputeRosterError(401, "missing_authorization")
    if principal.role == "admin":
        return
    owner = str(meta.get("teacher_id") or "").strip()
    actor = str(principal.actor_id or "").strip()
    if owner and owner != actor:
        raise AssignmentRecomputeRosterError(403, "forbidden_assignment_scope")


def _resolve_data_dir(data_dir: Optional[Path]) -> Path:
    if data_dir is not None:
        return Path(data_dir)
    env_data_dir = str(os.getenv("DATA_DIR", "") or "").strip()
    return Path(env_data_dir) if env_data_dir else Path(DATA_DIR)


def _resolve_assignment_folder(assignment_id: str, data_dir: Path) -> Path:
    aid = str(assignment_id or "").strip()
    if not aid:
        raise AssignmentRecomputeRosterError(400, "assignment_id is required")
    root = (data_dir / "assignments").resolve()
    folder = (root / aid).resolve()
    if folder != root and root not in folder.parents:
        raise AssignmentRecomputeRosterError(400, "invalid assignment_id")
    return folder


def recompute_assignment_roster(
    assignment_id: str,
    *,
    principal: Optional[AuthPrincipal],
    data_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    resolved_data_dir = _resolve_data_dir(data_dir)
    folder = _resolve_assignment_folder(assignment_id, resolved_data_dir)
    if not folder.exists():
        raise AssignmentRecomputeRosterError(404, "assignment not found")

    meta = _load_meta(folder)
    _require_owner(meta, principal)

    teacher_id = str(meta.get("teacher_id") or "").strip()
    subject_id = str(meta.get("subject_id") or "").strip()
    if not teacher_id or not subject_id:
        raise AssignmentRecomputeRosterError(400, "roster_required")

    student_ids = parse_ids_value(meta.get("student_ids") or [])
    class_name = str(meta.get("class_name") or "")
    scope_val = resolve_scope(str(meta.get("scope") or ""), student_ids, class_name)

    store = build_auth_registry_store(data_dir=resolved_data_dir)
    result = store.resolve_expected_students(
        scope=scope_val,
        class_name=class_name,
        student_ids=student_ids,
        teacher_id=teacher_id,
        subject_id=subject_id,
    )
    if not result.get("ok"):
        error = str(result.get("error") or "roster_required")
        raise AssignmentRecomputeRosterError(400, error)

    items = list(result.get("items") or [])
    meta["expected_students"] = items
    meta["expected_students_generated_at"] = datetime.now(tz=timezone.utc).isoformat(
        timespec="seconds"
    )
    atomic_write_json(folder / "meta.json", meta)

    with store._connect() as conn:
        store._append_audit(
            conn,
            actor_id=str(getattr(principal, "actor_id", "") or ""),
            actor_role=str(getattr(principal, "role", "") or ""),
            action="recompute_roster",
            target_id=str(assignment_id),
            target_role="assignment",
            detail={"count": len(items), "scope": scope_val},
        )
    return {"ok": True, "assignment_id": assignment_id, "expected_students": items, "count": len(items)}
