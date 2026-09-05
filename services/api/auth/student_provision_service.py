from __future__ import annotations

import csv
import hashlib
import re
import sqlite3
from datetime import datetime
from io import StringIO
from typing import Any, Callable, Dict, List, Optional

from ..core_utils import normalize

MAX_CSV_BYTES = 256 * 1024
MAX_CSV_ROWS = 2000
ALLOWED_COLUMNS = frozenset({"student_name", "class_name", "student_id"})
REQUIRED_COLUMNS = frozenset({"student_name", "class_name"})
_STUDENT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


def _fail(error: str) -> Dict[str, Any]:
    return {"ok": False, "error": error}


def _header_name(raw: Any) -> str:
    return str(raw or "").strip().lstrip("\ufeff")


def allocate_student_id(
    *, student_name: str, class_name: str, student_id: Optional[str]
) -> tuple[str, Optional[str]]:
    raw = str(student_id or "").strip()
    if raw:
        if not _STUDENT_ID_RE.fullmatch(raw):
            return raw, "invalid_student_id"
        return raw, None
    seed = f"{normalize(class_name)}|{normalize(student_name)}"
    return "s_" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12], None


def parse_roster_csv(text: str) -> Dict[str, Any]:
    reader = csv.DictReader(StringIO(text))
    if reader.fieldnames is None:
        return _fail("missing_column")
    headers = {_header_name(name) for name in reader.fieldnames if _header_name(name)}
    if not REQUIRED_COLUMNS.issubset(headers):
        return _fail("missing_column")
    if headers - ALLOWED_COLUMNS:
        return _fail("unknown_column")
    rows: List[Dict[str, str]] = []
    for raw_row in reader:
        parsed, error = _parse_roster_row(raw_row)
        if error:
            return _fail(error)
        if parsed is None:
            continue
        rows.append(parsed)
        if len(rows) > MAX_CSV_ROWS:
            return _fail("too_many_rows")
    if not rows:
        return _fail("empty_csv")
    return {"ok": True, "rows": _collapse_roster_rows(rows)}


def decode_roster_csv_bytes(raw: bytes) -> Dict[str, Any]:
    if len(raw) > MAX_CSV_BYTES:
        return _fail("file_too_large")
    if not raw:
        return _fail("empty_csv")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return _fail("invalid_encoding")
    return parse_roster_csv(text)


def _row_value(row: Dict[str, Any], key: str) -> str:
    for name, value in row.items():
        if _header_name(name) == key:
            return str(value or "").strip()
    return ""


def _parse_roster_row(row: Dict[str, Any]) -> tuple[Optional[Dict[str, str]], Optional[str]]:
    student_name = _row_value(row, "student_name")
    class_name = _row_value(row, "class_name")
    student_id = _row_value(row, "student_id")
    if not student_name and not class_name and not student_id:
        return None, None
    if not student_name:
        return None, "missing_student_name"
    if not class_name:
        return None, "missing_class_name"
    allocated, error = allocate_student_id(
        student_name=student_name, class_name=class_name, student_id=student_id
    )
    if error:
        return None, error
    return {
        "student_id": allocated,
        "student_name": student_name,
        "class_name": class_name,
    }, None


def _collapse_roster_rows(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    by_id: Dict[str, Dict[str, str]] = {}
    order: List[str] = []
    for row in rows:
        sid = row["student_id"]
        if sid not in by_id:
            order.append(sid)
        by_id[sid] = row
    return [by_id[sid] for sid in order]


def handle_import_students(
    store: Any,
    *,
    raw_csv: bytes,
    reset_passwords: bool,
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
    parsed = decode_roster_csv_bytes(raw_csv)
    if not parsed.get("ok"):
        return parsed
    rows = list(parsed.get("rows") or [])
    conn = store._connect()
    try:
        conn.execute("BEGIN")
        items, created, updated = _upsert_roster_rows(
            conn,
            rows=rows,
            reset_passwords=bool(reset_passwords),
            generate_bootstrap_password=generate_bootstrap_password,
            validate_password_strength=validate_password_strength,
            hash_password=hash_password,
            generate_token=generate_token,
            hash_token=hash_token,
            token_hint=token_hint,
            utc_now=utc_now,
            iso=iso,
        )
        store._append_audit(
            conn,
            actor_id=actor_id,
            actor_role=actor_role,
            action="import_students",
            target_id="",
            target_role="student",
            detail={"created": created, "updated": updated, "count": len(items)},
        )
        conn.execute("COMMIT")
    except (sqlite3.Error, RuntimeError):
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
    return {"ok": True, "created": created, "updated": updated, "count": len(items), "items": items}


def _upsert_roster_rows(
    conn: sqlite3.Connection,
    *,
    rows: List[Dict[str, str]],
    reset_passwords: bool,
    generate_bootstrap_password: Callable[[], str],
    validate_password_strength: Callable[[str], Optional[str]],
    hash_password: Callable[[str], str],
    generate_token: Callable[[], str],
    hash_token: Callable[[str], str],
    token_hint: Callable[[str], str],
    utc_now: Callable[[], datetime],
    iso: Callable[[datetime], str],
) -> tuple[List[Dict[str, Any]], int, int]:
    items: List[Dict[str, Any]] = []
    created = 0
    updated = 0
    now_iso = iso(utc_now())
    for row in rows:
        existing = conn.execute(
            "SELECT student_id FROM student_auth WHERE student_id = ?",
            (row["student_id"],),
        ).fetchone()
        if existing is None:
            item = _insert_student_auth(
                conn,
                row=row,
                now_iso=now_iso,
                generate_bootstrap_password=generate_bootstrap_password,
                validate_password_strength=validate_password_strength,
                hash_password=hash_password,
                generate_token=generate_token,
                hash_token=hash_token,
                token_hint=token_hint,
            )
            created += 1
        else:
            item = _update_student_auth(
                conn,
                row=row,
                now_iso=now_iso,
                reset_passwords=reset_passwords,
                generate_bootstrap_password=generate_bootstrap_password,
                validate_password_strength=validate_password_strength,
                hash_password=hash_password,
            )
            updated += 1
        items.append(item)
    return items, created, updated


def _require_temp_password(
    generate_bootstrap_password: Callable[[], str],
    validate_password_strength: Callable[[str], Optional[str]],
) -> str:
    temp_password = generate_bootstrap_password()
    password_error = validate_password_strength(temp_password)
    if password_error:
        raise RuntimeError(password_error)
    return temp_password


def _insert_student_auth(
    conn: sqlite3.Connection,
    *,
    row: Dict[str, str],
    now_iso: str,
    generate_bootstrap_password: Callable[[], str],
    validate_password_strength: Callable[[str], Optional[str]],
    hash_password: Callable[[str], str],
    generate_token: Callable[[], str],
    hash_token: Callable[[str], str],
    token_hint: Callable[[str], str],
) -> Dict[str, Any]:
    temp_password = _require_temp_password(generate_bootstrap_password, validate_password_strength)
    token_plain = generate_token()
    conn.execute(
        (
            "INSERT INTO student_auth(student_id, student_name, class_name, name_norm, class_norm, "
            "token_hash, token_hint, password_hash, password_algo, password_set_at, token_version, "
            "token_rotated_at, failed_count, locked_until, is_disabled, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, 0, NULL, 0, ?)"
        ),
        (
            row["student_id"],
            row["student_name"],
            row["class_name"],
            normalize(row["student_name"]),
            normalize(row["class_name"]),
            hash_token(token_plain),
            token_hint(token_plain),
            hash_password(temp_password),
            "pbkdf2_sha256",
            now_iso,
            now_iso,
            now_iso,
        ),
    )
    return {
        "student_id": row["student_id"],
        "student_name": row["student_name"],
        "class_name": row["class_name"],
        "created": True,
        "temp_password": temp_password,
    }


def _update_student_auth(
    conn: sqlite3.Connection,
    *,
    row: Dict[str, str],
    now_iso: str,
    reset_passwords: bool,
    generate_bootstrap_password: Callable[[], str],
    validate_password_strength: Callable[[str], Optional[str]],
    hash_password: Callable[[str], str],
) -> Dict[str, Any]:
    temp_password = ""
    if reset_passwords:
        temp_password = _require_temp_password(generate_bootstrap_password, validate_password_strength)
        conn.execute(
            (
                "UPDATE student_auth SET student_name = ?, class_name = ?, name_norm = ?, class_norm = ?, "
                "password_hash = ?, password_algo = ?, password_set_at = ?, token_version = token_version + 1, "
                "failed_count = 0, locked_until = NULL, updated_at = ? WHERE student_id = ?"
            ),
            (
                row["student_name"],
                row["class_name"],
                normalize(row["student_name"]),
                normalize(row["class_name"]),
                hash_password(temp_password),
                "pbkdf2_sha256",
                now_iso,
                now_iso,
                row["student_id"],
            ),
        )
    else:
        conn.execute(
            (
                "UPDATE student_auth SET student_name = ?, class_name = ?, name_norm = ?, class_norm = ?, "
                "updated_at = ? WHERE student_id = ?"
            ),
            (
                row["student_name"],
                row["class_name"],
                normalize(row["student_name"]),
                normalize(row["class_name"]),
                now_iso,
                row["student_id"],
            ),
        )
    item: Dict[str, Any] = {
        "student_id": row["student_id"],
        "student_name": row["student_name"],
        "class_name": row["class_name"],
        "created": False,
    }
    if temp_password:
        item["temp_password"] = temp_password
    return item


def import_students(
    store: Any,
    *,
    raw_csv: bytes,
    reset_passwords: bool,
    actor_id: str,
    actor_role: str,
) -> Dict[str, Any]:
    from ..auth_registry_service import (
        _generate_bootstrap_password,
        _generate_token,
        _hash_password,
        _hash_token,
        _iso,
        _token_hint,
        _utc_now,
        validate_password_strength,
    )

    return handle_import_students(
        store,
        raw_csv=raw_csv,
        reset_passwords=reset_passwords,
        actor_id=actor_id,
        actor_role=actor_role,
        generate_bootstrap_password=_generate_bootstrap_password,
        validate_password_strength=validate_password_strength,
        hash_password=_hash_password,
        generate_token=_generate_token,
        hash_token=_hash_token,
        token_hint=_token_hint,
        utc_now=_utc_now,
        iso=_iso,
    )
