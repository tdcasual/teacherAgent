from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Dict, Optional


def handle_login(
    store: Any,
    *,
    role: str,
    candidate_id: str,
    credential_type: str,
    credential: str,
    normalize_role: Callable[[Any], str],
    table_for_role: Callable[[str], tuple[str, str]],
    max_subject_id_len: Callable[[], int],
    max_credential_len: Callable[[], int],
    utc_now: Callable[[], datetime],
    parse_ts: Callable[[str], Optional[datetime]],
    consume_dummy_password_verify: Callable[[str], None],
    consume_dummy_token_verify: Callable[[str], None],
    constant_time_eq: Callable[[str, str], bool],
    hash_token: Callable[[str], str],
    verify_password: Callable[[str, str], bool],
    iso: Callable[[datetime], str],
) -> Dict[str, Any]:
    role_norm = normalize_role(role)
    if role_norm not in {"student", "teacher"}:
        return {"ok": False, "error": "invalid_role"}

    table, id_field = table_for_role(role_norm)
    sid = str(candidate_id or "").strip()
    cred_type = str(credential_type or "").strip().lower()
    cred = str(credential or "")
    if not sid:
        return {"ok": False, "error": "missing_candidate_id"}
    if cred_type not in {"token", "password"}:
        return {"ok": False, "error": "invalid_credential_type"}
    if not cred:
        return {"ok": False, "error": "missing_credential"}

    subject_id_max_len = max_subject_id_len()
    if len(sid) > subject_id_max_len:
        with store._connect() as conn:
            store._append_login_attempt(
                conn,
                role=role_norm,
                candidate_id=sid,
                credential_type=cred_type,
                result="candidate_id_too_long",
                detail={"max_len": subject_id_max_len, "input_len": len(sid)},
            )
        return {"ok": False, "error": "invalid_credential"}

    credential_max_len = max_credential_len()
    if len(cred) > credential_max_len:
        with store._connect() as conn:
            store._append_login_attempt(
                conn,
                role=role_norm,
                candidate_id=sid,
                credential_type=cred_type,
                result="credential_too_long",
                detail={"max_len": credential_max_len, "input_len": len(cred)},
            )
        return {"ok": False, "error": "invalid_credential"}

    now = utc_now()
    with store._connect() as conn:
        row = conn.execute(
            f"SELECT * FROM {table} WHERE {id_field} = ?",
            (sid,),
        ).fetchone()
        if row is None:
            if cred_type == "password":
                consume_dummy_password_verify(cred)
            elif cred_type == "token":
                consume_dummy_token_verify(cred)
            store._append_login_attempt(
                conn,
                role=role_norm,
                candidate_id=sid,
                credential_type=cred_type,
                result="not_found",
            )
            return {"ok": False, "error": "not_found"}

        if int(row["is_disabled"] or 0) == 1:
            if cred_type == "password":
                consume_dummy_password_verify(cred)
            elif cred_type == "token":
                consume_dummy_token_verify(cred)
            store._append_login_attempt(
                conn,
                role=role_norm,
                candidate_id=sid,
                credential_type=cred_type,
                result="disabled",
            )
            return {"ok": False, "error": "disabled"}

        lock_until = parse_ts(str(row["locked_until"] or ""))
        if lock_until is not None and lock_until > now:
            retry_after = int((lock_until - now).total_seconds())
            if cred_type == "password":
                consume_dummy_password_verify(cred)
            elif cred_type == "token":
                consume_dummy_token_verify(cred)
            store._append_login_attempt(
                conn,
                role=role_norm,
                candidate_id=sid,
                credential_type=cred_type,
                result="locked",
                detail={"retry_after_sec": max(1, retry_after)},
            )
            return {
                "ok": False,
                "error": "locked",
                "retry_after_sec": max(1, retry_after),
            }

        valid = False
        if cred_type == "token":
            valid = constant_time_eq(str(row["token_hash"] or ""), hash_token(cred))
        else:
            pwd_hash = str(row["password_hash"] or "")
            if not pwd_hash:
                consume_dummy_password_verify(cred)
                store._append_login_attempt(
                    conn,
                    role=role_norm,
                    candidate_id=sid,
                    credential_type=cred_type,
                    result="password_not_set",
                )
                return {"ok": False, "error": "password_not_set"}
            valid = verify_password(cred, pwd_hash)

        if not valid:
            failed_state = store._record_failed_login(
                conn,
                table=table,
                id_field=id_field,
                subject_id=sid,
                current_failed=int(row["failed_count"] or 0),
                now=now,
            )
            store._append_login_attempt(
                conn,
                role=role_norm,
                candidate_id=sid,
                credential_type=cred_type,
                result="invalid_credential",
                detail=failed_state,
            )
            return {"ok": False, "error": "invalid_credential"}

        conn.execute(
            (
                f"UPDATE {table} SET failed_count = 0, locked_until = NULL, updated_at = ? "
                f"WHERE {id_field} = ?"
            ),
            (iso(now), sid),
        )
        store._append_login_attempt(
            conn,
            role=role_norm,
            candidate_id=sid,
            credential_type=cred_type,
            result="success",
        )

        result: Dict[str, Any] = {
            "ok": True,
            "role": role_norm,
            "subject_id": sid,
            "token_version": int(row["token_version"] or 1),
            "password_set": bool(str(row["password_hash"] or "").strip()),
        }
        if role_norm == "student":
            result["student"] = {
                "student_id": sid,
                "student_name": str(row["student_name"] or ""),
                "class_name": str(row["class_name"] or ""),
            }
        else:
            result["teacher"] = {
                "teacher_id": sid,
                "teacher_name": str(row["teacher_name"] or ""),
                "email": str(row["email"] or ""),
            }
        return result

