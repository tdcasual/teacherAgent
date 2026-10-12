from __future__ import annotations

import logging
from typing import Any

from ..auth_service import AuthError, AuthPrincipal, require_principal

_log = logging.getLogger(__name__)


def resolve_profile_read_scope(student_id: str) -> str:
    raw = str(student_id or "").strip()
    principal = require_principal(roles=("student", "teacher", "admin"))
    if principal is None:
        raise AuthError(400, "principal_required")
    if not raw:
        raise AuthError(400, "student_id is required")
    if principal.role == "admin":
        return raw
    if principal.role == "student":
        if raw != principal.actor_id:
            _deny(principal, raw)
            raise AuthError(403, "forbidden_student_scope")
        return principal.actor_id
    if teacher_can_read_student_profile(teacher_id=principal.actor_id, student_id=raw):
        return raw
    _deny(principal, raw)
    raise AuthError(403, "forbidden_student_scope")


def teacher_can_read_student_profile(*, teacher_id: str, student_id: str) -> bool:
    tid = str(teacher_id or "").strip()
    sid = str(student_id or "").strip()
    if not tid or not sid:
        return False
    if _enrolled_with_teacher(tid, sid):
        return True
    return _owns_published_or_archived_snapshot(tid, sid)


def _enrolled_with_teacher(teacher_id: str, student_id: str) -> bool:
    try:
        from ..auth_registry_service import build_auth_registry_store
        from .identity_graph_service import student_enrolled

        store = build_auth_registry_store()
        return bool(
            student_enrolled(
                store,
                student_id=student_id,
                teacher_id=teacher_id,
                subject_id="",
            )
        )
    except Exception:  # policy: allowed-broad-except
        _log.warning("enrollment lookup failed", exc_info=True)
        return False


def _owns_published_or_archived_snapshot(teacher_id: str, student_id: str) -> bool:
    try:
        from ..assignment.store import connect, teacher_owns_student_snapshot
        from ..auth_registry_service import build_auth_registry_store

        data_dir = build_auth_registry_store().data_dir
        conn = connect(data_dir)
        try:
            return bool(teacher_owns_student_snapshot(conn, teacher_id, student_id))
        finally:
            conn.close()
    except Exception:  # policy: allowed-broad-except
        _log.warning("snapshot lookup failed", exc_info=True)
        return False


def _deny(principal: AuthPrincipal, student_id: str) -> None:
    payload: dict[str, Any] = {
        "actor_id": principal.actor_id,
        "role": principal.role,
        "student_id": student_id,
    }
    try:
        from ..app_core import diag_log

        diag_log("student.profile.scope_denied", payload)
    except Exception:  # policy: allowed-broad-except
        _log.info("student.profile.scope_denied %s", payload)
