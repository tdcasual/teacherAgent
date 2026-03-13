from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Dict, Optional


def _append_login_attempt(
    store: Any,
    conn: Any,
    *,
    role: str,
    candidate_id: str,
    credential_type: str,
    result: str,
    detail: Optional[Dict[str, Any]] = None,
) -> None:
    payload: Dict[str, Any] = {
        "role": role,
        "candidate_id": candidate_id,
        "credential_type": credential_type,
        "result": result,
    }
    if detail is not None:
        payload["detail"] = detail
    store._append_login_attempt(conn, **payload)


def _consume_dummy_credential(
    cred_type: str,
    cred: str,
    *,
    consume_dummy_password_verify: Callable[[str], None],
    consume_dummy_token_verify: Callable[[str], None],
) -> None:
    if cred_type == "password":
        consume_dummy_password_verify(cred)
    elif cred_type == "token":
        consume_dummy_token_verify(cred)


def _validate_login_inputs(role_norm: str, sid: str, cred_type: str, cred: str) -> Optional[Dict[str, Any]]:
    if role_norm not in {"student", "teacher"}:
        return {"ok": False, "error": "invalid_role"}
    if not sid:
        return {"ok": False, "error": "missing_candidate_id"}
    if cred_type not in {"token", "password"}:
        return {"ok": False, "error": "invalid_credential_type"}
    if not cred:
        return {"ok": False, "error": "missing_credential"}
    return None


def _validate_login_lengths(
    store: Any,
    *,
    role_norm: str,
    sid: str,
    cred_type: str,
    cred: str,
    max_subject_id_len: Callable[[], int],
    max_credential_len: Callable[[], int],
) -> Optional[Dict[str, Any]]:
    subject_id_max_len = max_subject_id_len()
    if len(sid) > subject_id_max_len:
        with store._connect() as conn:
            _append_login_attempt(
                store,
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
            _append_login_attempt(
                store,
                conn,
                role=role_norm,
                candidate_id=sid,
                credential_type=cred_type,
                result="credential_too_long",
                detail={"max_len": credential_max_len, "input_len": len(cred)},
            )
        return {"ok": False, "error": "invalid_credential"}
    return None


def _reject_login(
    store: Any,
    conn: Any,
    *,
    role_norm: str,
    sid: str,
    cred_type: str,
    cred: str,
    result: str,
    error: str,
    detail: Optional[Dict[str, Any]] = None,
    consume_dummy_password_verify: Callable[[str], None],
    consume_dummy_token_verify: Callable[[str], None],
) -> Dict[str, Any]:
    _consume_dummy_credential(
        cred_type,
        cred,
        consume_dummy_password_verify=consume_dummy_password_verify,
        consume_dummy_token_verify=consume_dummy_token_verify,
    )
    _append_login_attempt(
        store,
        conn,
        role=role_norm,
        candidate_id=sid,
        credential_type=cred_type,
        result=result,
        detail=detail,
    )
    payload: Dict[str, Any] = {"ok": False, "error": error}
    if detail and "retry_after_sec" in detail:
        payload["retry_after_sec"] = int(detail["retry_after_sec"])
    return payload


def _guard_login_row(
    store: Any,
    conn: Any,
    row: Any,
    *,
    role_norm: str,
    sid: str,
    cred_type: str,
    cred: str,
    now: datetime,
    parse_ts: Callable[[str], Optional[datetime]],
    consume_dummy_password_verify: Callable[[str], None],
    consume_dummy_token_verify: Callable[[str], None],
) -> Optional[Dict[str, Any]]:
    if row is None:
        return _reject_login(
            store,
            conn,
            role_norm=role_norm,
            sid=sid,
            cred_type=cred_type,
            cred=cred,
            result="not_found",
            error="not_found",
            consume_dummy_password_verify=consume_dummy_password_verify,
            consume_dummy_token_verify=consume_dummy_token_verify,
        )

    if int(row["is_disabled"] or 0) == 1:
        return _reject_login(
            store,
            conn,
            role_norm=role_norm,
            sid=sid,
            cred_type=cred_type,
            cred=cred,
            result="disabled",
            error="disabled",
            consume_dummy_password_verify=consume_dummy_password_verify,
            consume_dummy_token_verify=consume_dummy_token_verify,
        )

    lock_until = parse_ts(str(row["locked_until"] or ""))
    if lock_until is not None and lock_until > now:
        retry_after = max(1, int((lock_until - now).total_seconds()))
        return _reject_login(
            store,
            conn,
            role_norm=role_norm,
            sid=sid,
            cred_type=cred_type,
            cred=cred,
            result="locked",
            error="locked",
            detail={"retry_after_sec": retry_after},
            consume_dummy_password_verify=consume_dummy_password_verify,
            consume_dummy_token_verify=consume_dummy_token_verify,
        )
    return None


def _validate_login_credential(
    store: Any,
    conn: Any,
    row: Any,
    *,
    role_norm: str,
    sid: str,
    cred_type: str,
    cred: str,
    constant_time_eq: Callable[[str, str], bool],
    hash_token: Callable[[str], str],
    verify_password: Callable[[str, str], bool],
    consume_dummy_password_verify: Callable[[str], None],
) -> tuple[Optional[Dict[str, Any]], bool]:
    if cred_type == "token":
        valid = constant_time_eq(str(row["token_hash"] or ""), hash_token(cred))
        return None, valid

    pwd_hash = str(row["password_hash"] or "")
    if not pwd_hash:
        consume_dummy_password_verify(cred)
        _append_login_attempt(
            store,
            conn,
            role=role_norm,
            candidate_id=sid,
            credential_type=cred_type,
            result="password_not_set",
        )
        return {"ok": False, "error": "password_not_set"}, False
    return None, verify_password(cred, pwd_hash)


def _handle_invalid_login(
    store: Any,
    conn: Any,
    row: Any,
    *,
    table: str,
    id_field: str,
    role_norm: str,
    sid: str,
    cred_type: str,
    now: datetime,
) -> Dict[str, Any]:
    failed_state = store._record_failed_login(
        conn,
        table=table,
        id_field=id_field,
        subject_id=sid,
        current_failed=int(row["failed_count"] or 0),
        now=now,
    )
    _append_login_attempt(
        store,
        conn,
        role=role_norm,
        candidate_id=sid,
        credential_type=cred_type,
        result="invalid_credential",
        detail=failed_state,
    )
    return {"ok": False, "error": "invalid_credential"}


def _success_login_payload(row: Any, *, role_norm: str, sid: str) -> Dict[str, Any]:
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
    sid = str(candidate_id or "").strip()
    cred_type = str(credential_type or "").strip().lower()
    cred = str(credential or "")
    invalid = _validate_login_inputs(role_norm, sid, cred_type, cred)
    if invalid is not None:
        return invalid

    table, id_field = table_for_role(role_norm)
    invalid = _validate_login_lengths(
        store,
        role_norm=role_norm,
        sid=sid,
        cred_type=cred_type,
        cred=cred,
        max_subject_id_len=max_subject_id_len,
        max_credential_len=max_credential_len,
    )
    if invalid is not None:
        return invalid

    now = utc_now()
    with store._connect() as conn:
        row = conn.execute(
            f"SELECT * FROM {table} WHERE {id_field} = ?",
            (sid,),
        ).fetchone()
        row_error = _guard_login_row(
            store,
            conn,
            row,
            role_norm=role_norm,
            sid=sid,
            cred_type=cred_type,
            cred=cred,
            now=now,
            parse_ts=parse_ts,
            consume_dummy_password_verify=consume_dummy_password_verify,
            consume_dummy_token_verify=consume_dummy_token_verify,
        )
        if row_error is not None:
            return row_error

        credential_error, valid = _validate_login_credential(
            store,
            conn,
            row,
            role_norm=role_norm,
            sid=sid,
            cred_type=cred_type,
            cred=cred,
            constant_time_eq=constant_time_eq,
            hash_token=hash_token,
            verify_password=verify_password,
            consume_dummy_password_verify=consume_dummy_password_verify,
        )
        if credential_error is not None:
            return credential_error

        if not valid:
            return _handle_invalid_login(
                store,
                conn,
                row,
                table=table,
                id_field=id_field,
                role_norm=role_norm,
                sid=sid,
                cred_type=cred_type,
                now=now,
            )

        conn.execute(
            (
                f"UPDATE {table} SET failed_count = 0, locked_until = NULL, updated_at = ? "
                f"WHERE {id_field} = ?"
            ),
            (iso(now), sid),
        )
        _append_login_attempt(
            store,
            conn,
            role=role_norm,
            candidate_id=sid,
            credential_type=cred_type,
            result="success",
        )
        return _success_login_payload(row, role_norm=role_norm, sid=sid)
