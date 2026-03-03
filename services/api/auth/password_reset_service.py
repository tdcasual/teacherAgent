from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

_WEAK_PASSWORD_MESSAGE = "密码至少 8 位，且需同时包含字母与数字。"


def handle_reset_teacher_password(
    store: Any,
    *,
    target_id: str,
    new_password: Optional[str],
    actor_id: str,
    actor_role: str,
    generate_bootstrap_password: Callable[[], str],
    validate_password_strength: Callable[[str], Optional[str]],
    hash_password: Callable[[str], str],
    utc_now: Callable[[], datetime],
    iso: Callable[[datetime], str],
) -> Dict[str, Any]:
    identity = store._get_teacher_identity(target_id)
    if identity is None:
        return {"ok": False, "error": "not_found"}

    tid = str(identity.get("teacher_id") or "").strip()
    ensured = store._ensure_teacher_auth(
        teacher_id=tid,
        teacher_name=str(identity.get("teacher_name") or "").strip() or tid,
        email=str(identity.get("email") or "").strip() or None,
        regenerate_token=False,
    )
    if not ensured:
        return {"ok": False, "error": "not_found"}

    generated_password = False
    password_value = str(new_password or "").strip()
    if not password_value:
        password_value = generate_bootstrap_password()
        generated_password = True

    password_error = validate_password_strength(password_value)
    if password_error:
        return {
            "ok": False,
            "error": password_error,
            "message": _WEAK_PASSWORD_MESSAGE,
        }

    now = utc_now()
    with store._connect() as conn:
        conn.execute(
            (
                "UPDATE teacher_auth SET password_hash = ?, password_algo = ?, password_set_at = ?, "
                "token_version = token_version + 1, failed_count = 0, locked_until = NULL, "
                "updated_at = ? WHERE teacher_id = ?"
            ),
            (
                hash_password(password_value),
                "pbkdf2_sha256",
                iso(now),
                iso(now),
                tid,
            ),
        )
        store._append_audit(
            conn,
            actor_id=actor_id,
            actor_role=actor_role,
            action="reset_password",
            target_id=tid,
            target_role="teacher",
            detail={"generated": generated_password},
        )
        row = conn.execute(
            (
                "SELECT teacher_id, teacher_name, email, token_version "
                "FROM teacher_auth WHERE teacher_id = ?"
            ),
            (tid,),
        ).fetchone()
    if row is None:
        return {"ok": False, "error": "not_found"}

    payload: Dict[str, Any] = {
        "ok": True,
        "role": "teacher",
        "target_id": tid,
        "generated_password": generated_password,
        "token_version": int(row["token_version"] or 1),
        "teacher": {
            "teacher_id": str(row["teacher_id"] or ""),
            "teacher_name": str(row["teacher_name"] or ""),
            "email": str(row["email"] or ""),
        },
    }
    if generated_password:
        payload["temp_password"] = password_value
    return payload


def handle_reset_student_passwords(
    store: Any,
    *,
    scope: str,
    student_id: Optional[str],
    class_name: Optional[str],
    new_password: Optional[str],
    actor_id: str,
    actor_role: str,
    generate_bootstrap_password: Callable[[], str],
    validate_password_strength: Callable[[str], Optional[str]],
    hash_password: Callable[[str], str],
    utc_now: Callable[[], datetime],
    iso: Callable[[datetime], str],
) -> Dict[str, Any]:
    scope_norm = str(scope or "").strip().lower() or "student"
    targets_result = store._resolve_student_password_targets(
        scope=scope_norm,
        student_id=student_id,
        class_name=class_name,
    )
    if not targets_result.get("ok"):
        return targets_result

    targets = targets_result.get("items") or []
    if not targets:
        return {"ok": False, "error": "not_found"}

    requested_password = str(new_password or "").strip()
    if requested_password:
        password_error = validate_password_strength(requested_password)
        if password_error:
            return {
                "ok": False,
                "error": password_error,
                "message": _WEAK_PASSWORD_MESSAGE,
            }

    ensured_targets: List[Dict[str, str]] = []
    for target in targets:
        sid = str(target.get("student_id") or "").strip()
        if not sid:
            continue
        row = store._ensure_student_auth(
            student_id=sid,
            student_name=str(target.get("student_name") or "").strip(),
            class_name=str(target.get("class_name") or "").strip(),
            regenerate_token=False,
        )
        if not row:
            continue
        ensured_targets.append(
            {
                "student_id": sid,
                "student_name": str(row.get("student_name") or "").strip(),
                "class_name": str(row.get("class_name") or "").strip(),
            }
        )

    if not ensured_targets:
        return {"ok": False, "error": "not_found"}

    now = utc_now()
    generated_password = not bool(requested_password)
    items: List[Dict[str, Any]] = []
    with store._connect() as conn:
        for target in ensured_targets:
            sid = str(target.get("student_id") or "").strip()
            if not sid:
                continue
            password_value = requested_password or generate_bootstrap_password()
            conn.execute(
                (
                    "UPDATE student_auth SET password_hash = ?, password_algo = ?, "
                    "password_set_at = ?, token_version = token_version + 1, failed_count = 0, "
                    "locked_until = NULL, updated_at = ? WHERE student_id = ?"
                ),
                (
                    hash_password(password_value),
                    "pbkdf2_sha256",
                    iso(now),
                    iso(now),
                    sid,
                ),
            )
            row = conn.execute(
                (
                    "SELECT student_id, student_name, class_name, token_version "
                    "FROM student_auth WHERE student_id = ?"
                ),
                (sid,),
            ).fetchone()
            if row is None:
                continue
            store._append_audit(
                conn,
                actor_id=actor_id,
                actor_role=actor_role,
                action="reset_password",
                target_id=sid,
                target_role="student",
                detail={"scope": scope_norm, "generated": generated_password},
            )
            items.append(
                {
                    "student_id": str(row["student_id"] or ""),
                    "student_name": str(row["student_name"] or ""),
                    "class_name": str(row["class_name"] or ""),
                    "token_version": int(row["token_version"] or 1),
                    "generated_password": generated_password,
                    "temp_password": password_value,
                }
            )

    return {
        "ok": True,
        "scope": scope_norm,
        "count": len(items),
        "generated_password": generated_password,
        "items": items,
    }

