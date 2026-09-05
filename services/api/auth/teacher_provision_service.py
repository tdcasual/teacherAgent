from __future__ import annotations

import hashlib
import re
import sqlite3
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from ..core_utils import normalize

_TEACHER_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
_RESERVED_TEACHER_IDS = {"teacher"}


def _fail(error: str) -> Dict[str, Any]:
    return {"ok": False, "error": error}


def allocate_teacher_id(*, teacher_name: str, email: str, teacher_id: Optional[str]) -> tuple[str, Optional[str]]:
    raw = str(teacher_id or "").strip()
    if raw:
        if not _TEACHER_ID_RE.fullmatch(raw) or raw in _RESERVED_TEACHER_IDS:
            return raw, "invalid_teacher_id"
        return raw, None
    seed = f"{normalize(teacher_name)}|{normalize(email)}"
    generated = "t_" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]
    return generated, None


def _existing_teacher_conflict(conn: sqlite3.Connection, *, teacher_id: str, email_norm: str) -> Optional[str]:
    taken = conn.execute(
        "SELECT teacher_id FROM teacher_auth WHERE teacher_id = ?",
        (teacher_id,),
    ).fetchone()
    if taken is not None:
        return "teacher_id_taken"
    if not email_norm:
        return None
    email_row = conn.execute(
        "SELECT teacher_id FROM teacher_auth WHERE email_norm = ?",
        (email_norm,),
    ).fetchone()
    if email_row is not None:
        return "email_taken"
    return None


def handle_create_teacher(
    store: Any,
    *,
    teacher_name: str,
    email: Optional[str] = None,
    teacher_id: Optional[str] = None,
    actor_id: str,
    actor_role: str,
    generate_bootstrap_password: Callable[[], str],
    validate_password_strength: Callable[[str], Optional[str]],
    hash_password: Callable[[str], str],
    generate_token: Callable[[], str],
    hash_token: Callable[[str], str],
    token_hint: Callable[[str], str],
    utc_now: Callable[[], datetime],
    iso: Callable[[datetime], str],
) -> Dict[str, Any]:
    name = str(teacher_name or "").strip()
    if not name:
        return _fail("missing_teacher_name")
    email_text = str(email or "").strip()
    tid, id_error = allocate_teacher_id(teacher_name=name, email=email_text, teacher_id=teacher_id)
    if id_error:
        return _fail(id_error)

    temp_password = generate_bootstrap_password()
    password_error = validate_password_strength(temp_password)
    if password_error:
        return _fail(password_error)

    token_plain = generate_token()
    now = utc_now()
    now_iso = iso(now)
    email_norm = normalize(email_text)
    with store._connect() as conn:
        conflict = _existing_teacher_conflict(conn, teacher_id=tid, email_norm=email_norm)
        if conflict:
            return _fail(conflict)
        try:
            conn.execute(
                (
                    "INSERT INTO teacher_auth(teacher_id, teacher_name, email, name_norm, email_norm, token_hash, "
                    "token_hint, password_hash, password_algo, password_set_at, token_version, token_rotated_at, "
                    "failed_count, locked_until, is_disabled, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, 0, NULL, 0, ?)"
                ),
                (
                    tid,
                    name,
                    email_text,
                    normalize(name),
                    email_norm,
                    hash_token(token_plain),
                    token_hint(token_plain),
                    hash_password(temp_password),
                    "pbkdf2_sha256",
                    now_iso,
                    now_iso,
                    now_iso,
                ),
            )
        except sqlite3.IntegrityError:
            return _fail("teacher_id_taken")
        store._append_audit(
            conn,
            actor_id=actor_id,
            actor_role=actor_role,
            action="create_teacher",
            target_id=tid,
            target_role="teacher",
            detail={"teacher_name": name, "email": email_text},
        )
    return {
        "ok": True,
        "teacher_id": tid,
        "temp_password": temp_password,
        "teacher": {
            "teacher_id": tid,
            "teacher_name": name,
            "email": email_text,
        },
    }
