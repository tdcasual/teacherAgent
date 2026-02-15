from __future__ import annotations

import base64
import csv
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from io import StringIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .config import DATA_DIR as CONFIG_DATA_DIR
from .core_utils import normalize
from .paths import resolve_teacher_id
from .settings import default_teacher_id

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class AuthRegistryStore:
    db_path: Path
    data_dir: Path

    def __init__(self, db_path: Path, *, data_dir: Path):
        object.__setattr__(self, "db_path", Path(db_path).expanduser().resolve())
        object.__setattr__(self, "data_dir", Path(data_dir).expanduser().resolve())
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=3.0, isolation_level=None)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            try:
                conn.execute("PRAGMA journal_mode=WAL;")
            except Exception:
                _log.warning("WAL journal mode not available for %s", self.db_path, exc_info=True)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS student_auth (
                    student_id TEXT PRIMARY KEY,
                    student_name TEXT NOT NULL,
                    class_name TEXT NOT NULL,
                    name_norm TEXT NOT NULL,
                    class_norm TEXT NOT NULL,
                    token_hash TEXT NOT NULL,
                    token_hint TEXT,
                    password_hash TEXT,
                    password_algo TEXT,
                    password_set_at TEXT,
                    token_version INTEGER NOT NULL DEFAULT 1,
                    token_rotated_at TEXT,
                    failed_count INTEGER NOT NULL DEFAULT 0,
                    locked_until TEXT,
                    is_disabled INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS teacher_auth (
                    teacher_id TEXT PRIMARY KEY,
                    teacher_name TEXT NOT NULL,
                    email TEXT,
                    name_norm TEXT NOT NULL,
                    email_norm TEXT,
                    token_hash TEXT NOT NULL,
                    token_hint TEXT,
                    password_hash TEXT,
                    password_algo TEXT,
                    password_set_at TEXT,
                    token_version INTEGER NOT NULL DEFAULT 1,
                    token_rotated_at TEXT,
                    failed_count INTEGER NOT NULL DEFAULT 0,
                    locked_until TEXT,
                    is_disabled INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS admin_auth (
                    admin_username TEXT PRIMARY KEY,
                    username_norm TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    password_algo TEXT NOT NULL,
                    password_set_at TEXT NOT NULL,
                    failed_count INTEGER NOT NULL DEFAULT 0,
                    locked_until TEXT,
                    is_disabled INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS auth_audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    actor_id TEXT,
                    actor_role TEXT,
                    action TEXT,
                    target_id TEXT,
                    target_role TEXT,
                    detail_json TEXT,
                    created_at TEXT
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_student_name_class ON student_auth(name_norm, class_norm)"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_teacher_name ON teacher_auth(name_norm)")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_teacher_name_email ON teacher_auth(name_norm, email_norm)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_admin_username_norm ON admin_auth(username_norm)"
            )

    def identify_student(self, *, name: str, class_name: Optional[str]) -> Dict[str, Any]:
        q_name = str(name or "").strip()
        q_class = str(class_name or "").strip()
        if not q_name:
            return {"ok": False, "error": "missing_name", "message": "请先输入姓名。"}

        name_norm = normalize(q_name)
        class_norm = normalize(q_class)
        profiles = [
            item
            for item in self._list_student_profiles()
            if normalize(item.get("student_name", "")) == name_norm
        ]
        if class_norm:
            profiles = [
                item for item in profiles if normalize(item.get("class_name", "")) == class_norm
            ]

        if not profiles:
            return {
                "ok": False,
                "error": "not_found",
                "message": "未找到该学生，请检查姓名或班级。",
            }

        candidates: List[Dict[str, Any]] = []
        for profile in profiles:
            ensured = self._ensure_student_auth(
                student_id=str(profile.get("student_id") or "").strip(),
                student_name=str(profile.get("student_name") or "").strip(),
                class_name=str(profile.get("class_name") or "").strip(),
                regenerate_token=False,
            )
            if not ensured:
                continue
            candidates.append(
                {
                    "candidate_id": ensured["student_id"],
                    "student": {
                        "student_id": ensured["student_id"],
                        "student_name": ensured["student_name"],
                        "class_name": ensured["class_name"],
                    },
                    "password_set": bool(ensured.get("password_hash")),
                }
            )

        if not candidates:
            return {
                "ok": False,
                "error": "not_found",
                "message": "未找到该学生，请检查姓名或班级。",
            }
        if len(candidates) > 1:
            return {
                "ok": False,
                "error": "multiple",
                "message": "同名学生，请补充班级。",
                "candidates": candidates[:10],
            }
        return {"ok": True, **candidates[0]}

    def identify_teacher(self, *, name: str, email: Optional[str]) -> Dict[str, Any]:
        self.bootstrap_teachers(regenerate_token=False)

        q_name = str(name or "").strip()
        q_email = str(email or "").strip()
        if not q_name:
            return {"ok": False, "error": "missing_name", "message": "请先输入教师姓名。"}

        name_norm = normalize(q_name)
        email_norm = normalize(q_email)
        with self._connect() as conn:
            rows = list(
                conn.execute(
                    (
                        "SELECT teacher_id, teacher_name, email, name_norm, email_norm, password_hash "
                        "FROM teacher_auth WHERE name_norm = ? ORDER BY teacher_id"
                    ),
                    (name_norm,),
                ).fetchall()
            )

        if email_norm:
            rows = [row for row in rows if normalize(str(row["email"] or "")) == email_norm]

        if not rows:
            msg = "未找到该教师，请检查姓名或邮箱。" if q_email else "未找到该教师，请检查姓名。"
            return {"ok": False, "error": "not_found", "message": msg}

        if len(rows) > 1 and not email_norm:
            return {
                "ok": False,
                "error": "multiple",
                "message": "同名教师，请补充邮箱进行确认。",
                "need_email_disambiguation": True,
                "candidates": [
                    {
                        "teacher_id": str(row["teacher_id"] or ""),
                        "teacher_name": str(row["teacher_name"] or ""),
                        "email": str(row["email"] or ""),
                    }
                    for row in rows[:10]
                ],
            }

        if len(rows) > 1:
            return {
                "ok": False,
                "error": "multiple",
                "message": "姓名+邮箱仍无法唯一定位，请联系管理员处理重复数据。",
                "need_email_disambiguation": True,
            }

        row = rows[0]
        return {
            "ok": True,
            "candidate_id": str(row["teacher_id"] or ""),
            "teacher": {
                "teacher_id": str(row["teacher_id"] or ""),
                "teacher_name": str(row["teacher_name"] or ""),
                "email": str(row["email"] or ""),
            },
            "password_set": bool(str(row["password_hash"] or "").strip()),
        }

    def login(
        self,
        *,
        role: str,
        candidate_id: str,
        credential_type: str,
        credential: str,
    ) -> Dict[str, Any]:
        role_norm = _normalize_role(role)
        if role_norm not in {"student", "teacher"}:
            return {"ok": False, "error": "invalid_role"}

        table, id_field = _table_for_role(role_norm)
        sid = str(candidate_id or "").strip()
        cred_type = str(credential_type or "").strip().lower()
        cred = str(credential or "")
        if not sid:
            return {"ok": False, "error": "missing_candidate_id"}
        if cred_type not in {"token", "password"}:
            return {"ok": False, "error": "invalid_credential_type"}
        if not cred:
            return {"ok": False, "error": "missing_credential"}
        max_subject_id_len = _max_subject_id_len()
        if len(sid) > max_subject_id_len:
            with self._connect() as conn:
                self._append_login_attempt(
                    conn,
                    role=role_norm,
                    candidate_id=sid,
                    credential_type=cred_type,
                    result="candidate_id_too_long",
                    detail={
                        "max_len": max_subject_id_len,
                        "input_len": len(sid),
                    },
                )
            return {"ok": False, "error": "invalid_credential"}
        max_credential_len = _max_credential_len()
        if len(cred) > max_credential_len:
            with self._connect() as conn:
                self._append_login_attempt(
                    conn,
                    role=role_norm,
                    candidate_id=sid,
                    credential_type=cred_type,
                    result="credential_too_long",
                    detail={
                        "max_len": max_credential_len,
                        "input_len": len(cred),
                    },
                )
            return {"ok": False, "error": "invalid_credential"}

        now = _utc_now()
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT * FROM {table} WHERE {id_field} = ?",
                (sid,),
            ).fetchone()
            if row is None:
                if cred_type == "password":
                    _consume_dummy_password_verify(cred)
                elif cred_type == "token":
                    _consume_dummy_token_verify(cred)
                self._append_login_attempt(
                    conn,
                    role=role_norm,
                    candidate_id=sid,
                    credential_type=cred_type,
                    result="not_found",
                )
                return {"ok": False, "error": "not_found"}
            if int(row["is_disabled"] or 0) == 1:
                if cred_type == "password":
                    _consume_dummy_password_verify(cred)
                elif cred_type == "token":
                    _consume_dummy_token_verify(cred)
                self._append_login_attempt(
                    conn,
                    role=role_norm,
                    candidate_id=sid,
                    credential_type=cred_type,
                    result="disabled",
                )
                return {"ok": False, "error": "disabled"}

            lock_until = _parse_ts(str(row["locked_until"] or ""))
            if lock_until is not None and lock_until > now:
                retry_after = int((lock_until - now).total_seconds())
                if cred_type == "password":
                    _consume_dummy_password_verify(cred)
                elif cred_type == "token":
                    _consume_dummy_token_verify(cred)
                self._append_login_attempt(
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
                valid = _constant_time_eq(str(row["token_hash"] or ""), _hash_token(cred))
            else:
                pwd_hash = str(row["password_hash"] or "")
                if not pwd_hash:
                    _consume_dummy_password_verify(cred)
                    self._append_login_attempt(
                        conn,
                        role=role_norm,
                        candidate_id=sid,
                        credential_type=cred_type,
                        result="password_not_set",
                    )
                    return {"ok": False, "error": "password_not_set"}
                valid = _verify_password(cred, pwd_hash)

            if not valid:
                failed_state = self._record_failed_login(
                    conn,
                    table=table,
                    id_field=id_field,
                    subject_id=sid,
                    current_failed=int(row["failed_count"] or 0),
                    now=now,
                )
                self._append_login_attempt(
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
                (_iso(now), sid),
            )
            self._append_login_attempt(
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

    def bootstrap_admin(self) -> Dict[str, Any]:
        username = _admin_username()
        password = str(os.getenv("ADMIN_PASSWORD", "") or "")
        now = _utc_now()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT admin_username FROM admin_auth WHERE username_norm = ?",
                (normalize(username),),
            ).fetchone()
            if row is not None:
                return {
                    "ok": True,
                    "created": False,
                    "username": str(row["admin_username"] or ""),
                    "generated_password": False,
                    "bootstrap_file": "",
                }

            generated = False
            if not password:
                password = _generate_bootstrap_password()
                generated = True
            conn.execute(
                (
                    "INSERT INTO admin_auth(admin_username, username_norm, password_hash, "
                    "password_algo, password_set_at, failed_count, locked_until, is_disabled, "
                    "updated_at) VALUES (?, ?, ?, ?, ?, 0, NULL, 0, ?)"
                ),
                (
                    username,
                    normalize(username),
                    _hash_password(password),
                    "pbkdf2_sha256",
                    _iso(now),
                    _iso(now),
                ),
            )

        bootstrap_file = ""
        if generated:
            bootstrap_file = self._write_admin_bootstrap_file(username=username, password=password)

        return {
            "ok": True,
            "created": True,
            "username": username,
            "generated_password": generated,
            "bootstrap_file": bootstrap_file,
        }

    def login_admin(self, *, username: str, password: str) -> Dict[str, Any]:
        bootstrap_result = self.bootstrap_admin()
        if not bootstrap_result.get("ok"):
            return {"ok": False, "error": "admin_bootstrap_failed"}

        user_input = str(username or "").strip()
        pwd_input = str(password or "")
        if not user_input:
            return {"ok": False, "error": "missing_username"}
        if not pwd_input:
            return {"ok": False, "error": "missing_password"}
        max_subject_id_len = _max_subject_id_len()
        if len(user_input) > max_subject_id_len:
            with self._connect() as conn:
                self._append_login_attempt(
                    conn,
                    role="admin",
                    candidate_id=user_input,
                    credential_type="password",
                    result="candidate_id_too_long",
                    detail={
                        "max_len": max_subject_id_len,
                        "input_len": len(user_input),
                    },
                )
            return {"ok": False, "error": "invalid_credential"}
        max_credential_len = _max_credential_len()
        if len(pwd_input) > max_credential_len:
            with self._connect() as conn:
                self._append_login_attempt(
                    conn,
                    role="admin",
                    candidate_id=user_input,
                    credential_type="password",
                    result="credential_too_long",
                    detail={
                        "max_len": max_credential_len,
                        "input_len": len(pwd_input),
                    },
                )
            return {"ok": False, "error": "invalid_credential"}

        now = _utc_now()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM admin_auth WHERE username_norm = ?",
                (normalize(user_input),),
            ).fetchone()
            if row is None:
                _consume_dummy_password_verify(pwd_input)
                self._append_login_attempt(
                    conn,
                    role="admin",
                    candidate_id=user_input,
                    credential_type="password",
                    result="not_found",
                )
                return {"ok": False, "error": "not_found"}
            if int(row["is_disabled"] or 0) == 1:
                _consume_dummy_password_verify(pwd_input)
                self._append_login_attempt(
                    conn,
                    role="admin",
                    candidate_id=str(row["admin_username"] or user_input),
                    credential_type="password",
                    result="disabled",
                )
                return {"ok": False, "error": "disabled"}

            lock_until = _parse_ts(str(row["locked_until"] or ""))
            if lock_until is not None and lock_until > now:
                retry_after = int((lock_until - now).total_seconds())
                _consume_dummy_password_verify(pwd_input)
                self._append_login_attempt(
                    conn,
                    role="admin",
                    candidate_id=str(row["admin_username"] or user_input),
                    credential_type="password",
                    result="locked",
                    detail={"retry_after_sec": max(1, retry_after)},
                )
                return {
                    "ok": False,
                    "error": "locked",
                    "retry_after_sec": max(1, retry_after),
                }

            pwd_hash = str(row["password_hash"] or "")
            if not pwd_hash or not _verify_password(pwd_input, pwd_hash):
                failed_state = self._record_failed_login(
                    conn,
                    table="admin_auth",
                    id_field="admin_username",
                    subject_id=str(row["admin_username"] or ""),
                    current_failed=int(row["failed_count"] or 0),
                    now=now,
                )
                self._append_login_attempt(
                    conn,
                    role="admin",
                    candidate_id=str(row["admin_username"] or user_input),
                    credential_type="password",
                    result="invalid_credential",
                    detail=failed_state,
                )
                return {"ok": False, "error": "invalid_credential"}

            admin_username = str(row["admin_username"] or "")
            conn.execute(
                (
                    "UPDATE admin_auth SET failed_count = 0, locked_until = NULL, updated_at = ? "
                    "WHERE admin_username = ?"
                ),
                (_iso(now), admin_username),
            )
            self._append_login_attempt(
                conn,
                role="admin",
                candidate_id=admin_username,
                credential_type="password",
                result="success",
            )

        return {
            "ok": True,
            "role": "admin",
            "subject_id": admin_username,
        }

    def list_teacher_auth_status(self) -> Dict[str, Any]:
        self.bootstrap_teachers(regenerate_token=False)
        with self._connect() as conn:
            rows = list(
                conn.execute(
                    (
                        "SELECT teacher_id, teacher_name, email, token_hint, password_hash, "
                        "token_version, failed_count, locked_until, is_disabled, updated_at "
                        "FROM teacher_auth ORDER BY teacher_id"
                    )
                ).fetchall()
            )
        items: List[Dict[str, Any]] = []
        for row in rows:
            items.append(
                {
                    "teacher_id": str(row["teacher_id"] or ""),
                    "teacher_name": str(row["teacher_name"] or ""),
                    "email": str(row["email"] or ""),
                    "token_hint": str(row["token_hint"] or ""),
                    "password_set": bool(str(row["password_hash"] or "").strip()),
                    "token_version": int(row["token_version"] or 1),
                    "failed_count": int(row["failed_count"] or 0),
                    "locked_until": str(row["locked_until"] or ""),
                    "is_disabled": bool(int(row["is_disabled"] or 0)),
                    "updated_at": str(row["updated_at"] or ""),
                }
            )
        return {"ok": True, "count": len(items), "items": items}

    def set_teacher_disabled(
        self,
        *,
        target_id: str,
        is_disabled: bool,
        actor_id: str,
        actor_role: str,
    ) -> Dict[str, Any]:
        identity = self._get_teacher_identity(target_id)
        if identity is None:
            return {"ok": False, "error": "not_found"}

        tid = str(identity.get("teacher_id") or "").strip()
        ensured = self._ensure_teacher_auth(
            teacher_id=tid,
            teacher_name=str(identity.get("teacher_name") or "").strip() or tid,
            email=str(identity.get("email") or "").strip() or None,
            regenerate_token=False,
        )
        if not ensured:
            return {"ok": False, "error": "not_found"}

        disabled_val = 1 if bool(is_disabled) else 0
        now = _utc_now()
        with self._connect() as conn:
            conn.execute(
                (
                    "UPDATE teacher_auth SET is_disabled = ?, token_version = token_version + 1, "
                    "failed_count = 0, locked_until = NULL, updated_at = ? WHERE teacher_id = ?"
                ),
                (disabled_val, _iso(now), tid),
            )
            self._append_audit(
                conn,
                actor_id=actor_id,
                actor_role=actor_role,
                action="set_disabled",
                target_id=tid,
                target_role="teacher",
                detail={"is_disabled": bool(disabled_val)},
            )
            row = conn.execute(
                (
                    "SELECT teacher_id, teacher_name, email, is_disabled, token_version "
                    "FROM teacher_auth WHERE teacher_id = ?"
                ),
                (tid,),
            ).fetchone()
        if row is None:
            return {"ok": False, "error": "not_found"}

        return {
            "ok": True,
            "role": "teacher",
            "target_id": tid,
            "is_disabled": bool(int(row["is_disabled"] or 0)),
            "token_version": int(row["token_version"] or 1),
            "teacher": {
                "teacher_id": str(row["teacher_id"] or ""),
                "teacher_name": str(row["teacher_name"] or ""),
                "email": str(row["email"] or ""),
            },
        }

    def reset_teacher_password(
        self,
        *,
        target_id: str,
        new_password: Optional[str],
        actor_id: str,
        actor_role: str,
    ) -> Dict[str, Any]:
        identity = self._get_teacher_identity(target_id)
        if identity is None:
            return {"ok": False, "error": "not_found"}

        tid = str(identity.get("teacher_id") or "").strip()
        ensured = self._ensure_teacher_auth(
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
            password_value = _generate_bootstrap_password()
            generated_password = True

        password_error = validate_password_strength(password_value)
        if password_error:
            return {
                "ok": False,
                "error": password_error,
                "message": "密码至少 8 位，且需同时包含字母与数字。",
            }

        now = _utc_now()
        with self._connect() as conn:
            conn.execute(
                (
                    "UPDATE teacher_auth SET password_hash = ?, password_algo = ?, password_set_at = ?, "
                    "token_version = token_version + 1, failed_count = 0, locked_until = NULL, "
                    "updated_at = ? WHERE teacher_id = ?"
                ),
                (
                    _hash_password(password_value),
                    "pbkdf2_sha256",
                    _iso(now),
                    _iso(now),
                    tid,
                ),
            )
            self._append_audit(
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

    def _write_admin_bootstrap_file(self, *, username: str, password: str) -> str:
        auth_dir = self.data_dir / "auth"
        auth_dir.mkdir(parents=True, exist_ok=True)
        path = auth_dir / "admin_bootstrap.txt"
        content = (
            "# Generated by auth bootstrap. Rotate password after first login.\n"
            f"username={str(username or '').strip()}\n"
            f"password={str(password or '').strip()}\n"
            f"generated_at={_iso(_utc_now())}\n"
        )
        path.write_text(content, encoding="utf-8")
        try:
            os.chmod(path, 0o600)
        except Exception:
            _log.warning("failed to chmod admin bootstrap file: %s", path, exc_info=True)
        return str(path)

    def set_password(
        self,
        *,
        role: str,
        candidate_id: str,
        credential_type: str,
        credential: str,
        new_password: str,
        actor_id: str,
        actor_role: str,
    ) -> Dict[str, Any]:
        password_error = validate_password_strength(new_password)
        if password_error:
            return {
                "ok": False,
                "error": password_error,
                "message": "密码至少 8 位，且需同时包含字母与数字。",
            }

        auth_result = self.login(
            role=role,
            candidate_id=candidate_id,
            credential_type=credential_type,
            credential=credential,
        )
        if not auth_result.get("ok"):
            return auth_result

        role_norm = _normalize_role(role)
        table, id_field = _table_for_role(role_norm)
        sid = str(candidate_id or "").strip()
        now = _utc_now()
        with self._connect() as conn:
            conn.execute(
                (
                    f"UPDATE {table} SET password_hash = ?, password_algo = ?, password_set_at = ?, "
                    f"updated_at = ? WHERE {id_field} = ?"
                ),
                (
                    _hash_password(new_password),
                    "pbkdf2_sha256",
                    _iso(now),
                    _iso(now),
                    sid,
                ),
            )
            self._append_audit(
                conn,
                actor_id=actor_id,
                actor_role=actor_role,
                action="set_password",
                target_id=sid,
                target_role=role_norm,
                detail={"credential_type": str(credential_type or "").strip().lower()},
            )
        return {"ok": True, "role": role_norm, "subject_id": sid}

    def reset_token(
        self,
        *,
        role: str,
        target_id: str,
        actor_id: str,
        actor_role: str,
    ) -> Dict[str, Any]:
        role_norm = _normalize_role(role)
        sid = str(target_id or "").strip()
        if role_norm not in {"student", "teacher"}:
            return {"ok": False, "error": "invalid_role"}
        if not sid:
            return {"ok": False, "error": "missing_target_id"}

        if role_norm == "student":
            identity = self._get_student_identity(sid)
            if identity is None:
                return {"ok": False, "error": "not_found"}
            row = self._ensure_student_auth(
                student_id=sid,
                student_name=identity["student_name"],
                class_name=identity["class_name"],
                regenerate_token=True,
            )
            if not row:
                return {"ok": False, "error": "not_found"}
            out = {
                "ok": True,
                "role": "student",
                "target_id": sid,
                "token": str(row.get("_plain_token") or ""),
                "token_hint": str(row.get("token_hint") or ""),
                "student": {
                    "student_id": sid,
                    "student_name": str(row.get("student_name") or ""),
                    "class_name": str(row.get("class_name") or ""),
                },
            }
        else:
            identity = self._get_teacher_identity(sid)
            if identity is None:
                return {"ok": False, "error": "not_found"}
            row = self._ensure_teacher_auth(
                teacher_id=sid,
                teacher_name=identity["teacher_name"],
                email=identity.get("email"),
                regenerate_token=True,
            )
            if not row:
                return {"ok": False, "error": "not_found"}
            out = {
                "ok": True,
                "role": "teacher",
                "target_id": sid,
                "token": str(row.get("_plain_token") or ""),
                "token_hint": str(row.get("token_hint") or ""),
                "teacher": {
                    "teacher_id": sid,
                    "teacher_name": str(row.get("teacher_name") or ""),
                    "email": str(row.get("email") or ""),
                },
            }

        with self._connect() as conn:
            self._append_audit(
                conn,
                actor_id=actor_id,
                actor_role=actor_role,
                action="reset_token",
                target_id=sid,
                target_role=role_norm,
                detail={"token_hint": out.get("token_hint")},
            )
        return out

    def export_tokens(
        self,
        *,
        role: str,
        ids: Optional[Sequence[str]],
        actor_id: str,
        actor_role: str,
    ) -> Dict[str, Any]:
        role_norm = _normalize_role(role)
        if role_norm not in {"student", "teacher"}:
            return {"ok": False, "error": "invalid_role"}

        id_filter = {str(item or "").strip() for item in (ids or []) if str(item or "").strip()}

        items: List[Dict[str, Any]] = []
        if role_norm == "student":
            for profile in self._list_student_profiles():
                sid = str(profile.get("student_id") or "").strip()
                if not sid:
                    continue
                if id_filter and sid not in id_filter:
                    continue
                row = self._ensure_student_auth(
                    student_id=sid,
                    student_name=str(profile.get("student_name") or "").strip(),
                    class_name=str(profile.get("class_name") or "").strip(),
                    regenerate_token=True,
                )
                if not row:
                    continue
                items.append(
                    {
                        "student_id": sid,
                        "student_name": str(row.get("student_name") or ""),
                        "class_name": str(row.get("class_name") or ""),
                        "token": str(row.get("_plain_token") or ""),
                    }
                )
        else:
            for teacher in self._list_teacher_identities():
                tid = str(teacher.get("teacher_id") or "").strip()
                if not tid:
                    continue
                if id_filter and tid not in id_filter:
                    continue
                row = self._ensure_teacher_auth(
                    teacher_id=tid,
                    teacher_name=str(teacher.get("teacher_name") or "").strip() or tid,
                    email=str(teacher.get("email") or "").strip() or None,
                    regenerate_token=True,
                )
                if not row:
                    continue
                items.append(
                    {
                        "teacher_id": tid,
                        "teacher_name": str(row.get("teacher_name") or ""),
                        "email": str(row.get("email") or ""),
                        "token": str(row.get("_plain_token") or ""),
                    }
                )

        csv_text = self._to_csv(role_norm, items)
        with self._connect() as conn:
            self._append_audit(
                conn,
                actor_id=actor_id,
                actor_role=actor_role,
                action="export_tokens",
                target_id="*",
                target_role=role_norm,
                detail={"count": len(items), "filtered": bool(id_filter)},
            )
        return {
            "ok": True,
            "role": role_norm,
            "count": len(items),
            "items": items,
            "csv": csv_text,
        }

    def bootstrap_teachers(self, *, regenerate_token: bool) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for teacher in self._list_teacher_identities():
            tid = str(teacher.get("teacher_id") or "").strip()
            if not tid:
                continue
            row = self._ensure_teacher_auth(
                teacher_id=tid,
                teacher_name=str(teacher.get("teacher_name") or "").strip() or tid,
                email=str(teacher.get("email") or "").strip() or None,
                regenerate_token=regenerate_token,
            )
            if row:
                rows.append(row)
        return rows

    def token_version_matches(self, *, role: str, subject_id: str, token_version: int) -> bool:
        role_norm = _normalize_role(role)
        if role_norm not in {"student", "teacher"}:
            return True
        sid = str(subject_id or "").strip()
        if not sid:
            return False
        table, id_field = _table_for_role(role_norm)
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT token_version, is_disabled FROM {table} WHERE {id_field} = ?",
                (sid,),
            ).fetchone()
        if row is None:
            return False
        if int(row["is_disabled"] or 0) == 1:
            return False
        return int(row["token_version"] or 0) == int(token_version)

    def _record_failed_login(
        self,
        conn: sqlite3.Connection,
        *,
        table: str,
        id_field: str,
        subject_id: str,
        current_failed: int,
        now: datetime,
    ) -> Dict[str, Any]:
        threshold = _lock_threshold()
        lock_minutes = _lock_minutes()
        next_failed = max(0, int(current_failed)) + 1
        locked_until = None
        if next_failed >= threshold:
            locked_until = _iso(now + timedelta(minutes=lock_minutes))
            next_failed = 0
        conn.execute(
            (
                f"UPDATE {table} SET failed_count = ?, locked_until = ?, updated_at = ? "
                f"WHERE {id_field} = ?"
            ),
            (next_failed, locked_until, _iso(now), subject_id),
        )
        return {
            "failed_count": int(next_failed),
            "locked_until": str(locked_until or ""),
        }

    def _append_login_attempt(
        self,
        conn: sqlite3.Connection,
        *,
        role: str,
        candidate_id: str,
        credential_type: str,
        result: str,
        detail: Optional[Dict[str, Any]] = None,
    ) -> None:
        audit_candidate_id = _audit_subject_id(candidate_id)
        payload: Dict[str, Any] = {
            "credential_type": str(credential_type or "").strip().lower(),
            "result": str(result or "").strip().lower(),
        }
        if detail:
            payload.update(detail)
        self._append_audit(
            conn,
            actor_id=audit_candidate_id,
            actor_role=str(role or "").strip().lower(),
            action="login_attempt",
            target_id=audit_candidate_id,
            target_role=str(role or "").strip().lower(),
            detail=payload,
        )

    def _append_audit(
        self,
        conn: sqlite3.Connection,
        *,
        actor_id: str,
        actor_role: str,
        action: str,
        target_id: str,
        target_role: str,
        detail: Dict[str, Any],
    ) -> None:
        conn.execute(
            (
                "INSERT INTO auth_audit_log(actor_id, actor_role, action, target_id, "
                "target_role, detail_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)"
            ),
            (
                str(actor_id or "").strip(),
                str(actor_role or "").strip(),
                str(action or "").strip(),
                str(target_id or "").strip(),
                str(target_role or "").strip(),
                json.dumps(detail or {}, ensure_ascii=False),
                _iso(_utc_now()),
            ),
        )

    def _ensure_student_auth(
        self,
        *,
        student_id: str,
        student_name: str,
        class_name: str,
        regenerate_token: bool,
    ) -> Optional[Dict[str, Any]]:
        sid = str(student_id or "").strip()
        if not sid:
            return None
        name = str(student_name or "").strip()
        class_text = str(class_name or "").strip()
        now = _utc_now()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM student_auth WHERE student_id = ?",
                (sid,),
            ).fetchone()
            token_plain = ""
            token_hash = ""
            token_hint = ""
            token_version = 1
            token_rotated_at = None
            if row is None or regenerate_token:
                token_plain = _generate_token()
                token_hash = _hash_token(token_plain)
                token_hint = _token_hint(token_plain)
                token_version = 1 if row is None else int(row["token_version"] or 1) + 1
                token_rotated_at = _iso(now)
            if row is None:
                conn.execute(
                    (
                        "INSERT INTO student_auth(student_id, student_name, class_name, name_norm, class_norm, "
                        "token_hash, token_hint, password_hash, password_algo, password_set_at, token_version, "
                        "token_rotated_at, failed_count, locked_until, is_disabled, updated_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, ?, ?, 0, NULL, 0, ?)"
                    ),
                    (
                        sid,
                        name,
                        class_text,
                        normalize(name),
                        normalize(class_text),
                        token_hash,
                        token_hint,
                        token_version,
                        token_rotated_at,
                        _iso(now),
                    ),
                )
            else:
                update_fields: List[str] = [
                    "student_name = ?",
                    "class_name = ?",
                    "name_norm = ?",
                    "class_norm = ?",
                    "updated_at = ?",
                ]
                params: List[Any] = [
                    name,
                    class_text,
                    normalize(name),
                    normalize(class_text),
                    _iso(now),
                ]
                if regenerate_token:
                    update_fields.extend(
                        [
                            "token_hash = ?",
                            "token_hint = ?",
                            "token_version = ?",
                            "token_rotated_at = ?",
                            "failed_count = 0",
                            "locked_until = NULL",
                        ]
                    )
                    params.extend([token_hash, token_hint, token_version, token_rotated_at])
                params.append(sid)
                conn.execute(
                    f"UPDATE student_auth SET {', '.join(update_fields)} WHERE student_id = ?",
                    tuple(params),
                )

            final_row = conn.execute(
                "SELECT * FROM student_auth WHERE student_id = ?",
                (sid,),
            ).fetchone()
            if final_row is None:
                return None
            out = _row_to_dict(final_row)
            if token_plain:
                out["_plain_token"] = token_plain
            return out

    def _ensure_teacher_auth(
        self,
        *,
        teacher_id: str,
        teacher_name: str,
        email: Optional[str],
        regenerate_token: bool,
    ) -> Optional[Dict[str, Any]]:
        tid = resolve_teacher_id(teacher_id)
        if not tid:
            return None
        name = str(teacher_name or "").strip() or tid
        email_text = str(email or "").strip()
        now = _utc_now()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM teacher_auth WHERE teacher_id = ?",
                (tid,),
            ).fetchone()
            token_plain = ""
            token_hash = ""
            token_hint = ""
            token_version = 1
            token_rotated_at = None
            if row is None or regenerate_token:
                token_plain = _generate_token()
                token_hash = _hash_token(token_plain)
                token_hint = _token_hint(token_plain)
                token_version = 1 if row is None else int(row["token_version"] or 1) + 1
                token_rotated_at = _iso(now)
            if row is None:
                conn.execute(
                    (
                        "INSERT INTO teacher_auth(teacher_id, teacher_name, email, name_norm, email_norm, token_hash, "
                        "token_hint, password_hash, password_algo, password_set_at, token_version, token_rotated_at, "
                        "failed_count, locked_until, is_disabled, updated_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, ?, ?, 0, NULL, 0, ?)"
                    ),
                    (
                        tid,
                        name,
                        email_text,
                        normalize(name),
                        normalize(email_text),
                        token_hash,
                        token_hint,
                        token_version,
                        token_rotated_at,
                        _iso(now),
                    ),
                )
            else:
                update_fields: List[str] = [
                    "teacher_name = ?",
                    "email = ?",
                    "name_norm = ?",
                    "email_norm = ?",
                    "updated_at = ?",
                ]
                params: List[Any] = [
                    name,
                    email_text,
                    normalize(name),
                    normalize(email_text),
                    _iso(now),
                ]
                if regenerate_token:
                    update_fields.extend(
                        [
                            "token_hash = ?",
                            "token_hint = ?",
                            "token_version = ?",
                            "token_rotated_at = ?",
                            "failed_count = 0",
                            "locked_until = NULL",
                        ]
                    )
                    params.extend([token_hash, token_hint, token_version, token_rotated_at])
                params.append(tid)
                conn.execute(
                    f"UPDATE teacher_auth SET {', '.join(update_fields)} WHERE teacher_id = ?",
                    tuple(params),
                )

            final_row = conn.execute(
                "SELECT * FROM teacher_auth WHERE teacher_id = ?",
                (tid,),
            ).fetchone()
            if final_row is None:
                return None
            out = _row_to_dict(final_row)
            if token_plain:
                out["_plain_token"] = token_plain
            return out

    def _list_student_profiles(self) -> List[Dict[str, str]]:
        root = self.data_dir / "student_profiles"
        if not root.exists():
            return []
        out: List[Dict[str, str]] = []
        seen: set[str] = set()
        for path in sorted(root.glob("*.json")):
            try:
                profile = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                _log.warning("failed to load student profile %s", path, exc_info=True)
                continue
            sid = str(profile.get("student_id") or path.stem).strip()
            if not sid or sid in seen:
                continue
            seen.add(sid)
            out.append(
                {
                    "student_id": sid,
                    "student_name": str(profile.get("student_name") or "").strip(),
                    "class_name": str(profile.get("class_name") or "").strip(),
                }
            )
        return out

    def _list_teacher_identities(self) -> List[Dict[str, str]]:
        out: Dict[str, Dict[str, str]] = {}

        # Existing auth rows have highest priority for display name/email
        with self._connect() as conn:
            for row in conn.execute(
                "SELECT teacher_id, teacher_name, email FROM teacher_auth ORDER BY teacher_id"
            ).fetchall():
                tid = str(row["teacher_id"] or "").strip()
                if not tid:
                    continue
                out[tid] = {
                    "teacher_id": tid,
                    "teacher_name": str(row["teacher_name"] or "").strip() or tid,
                    "email": str(row["email"] or "").strip(),
                }

        workspace_root = self.data_dir / "teacher_workspaces"
        if workspace_root.exists():
            for path in sorted(workspace_root.iterdir()):
                if not path.is_dir():
                    continue
                tid = str(path.name or "").strip()
                if not tid:
                    continue
                profile = _parse_teacher_profile_markdown(path / "USER.md")
                name = profile.get("name") or tid
                email = profile.get("email") or ""
                existing = out.get(tid)
                if existing is None:
                    out[tid] = {
                        "teacher_id": tid,
                        "teacher_name": str(name).strip() or tid,
                        "email": str(email).strip(),
                    }
                else:
                    if (existing.get("teacher_name") or "").strip() in {"", "(unknown)", "unknown"}:
                        existing["teacher_name"] = str(name).strip() or tid
                    if not (existing.get("email") or "").strip() and str(email).strip():
                        existing["email"] = str(email).strip()

        fallback_tid = resolve_teacher_id(default_teacher_id())
        if fallback_tid and fallback_tid not in out:
            out[fallback_tid] = {
                "teacher_id": fallback_tid,
                "teacher_name": fallback_tid,
                "email": "",
            }

        return [out[key] for key in sorted(out.keys())]

    def _get_student_identity(self, student_id: str) -> Optional[Dict[str, str]]:
        sid = str(student_id or "").strip()
        if not sid:
            return None
        for item in self._list_student_profiles():
            if str(item.get("student_id") or "").strip() == sid:
                return item
        with self._connect() as conn:
            row = conn.execute(
                "SELECT student_id, student_name, class_name FROM student_auth WHERE student_id = ?",
                (sid,),
            ).fetchone()
        if row is None:
            return None
        return {
            "student_id": sid,
            "student_name": str(row["student_name"] or "").strip(),
            "class_name": str(row["class_name"] or "").strip(),
        }

    def _get_teacher_identity(self, teacher_id: str) -> Optional[Dict[str, str]]:
        tid = resolve_teacher_id(teacher_id)
        for item in self._list_teacher_identities():
            if str(item.get("teacher_id") or "").strip() == tid:
                return item
        return None

    def _to_csv(self, role: str, items: Sequence[Dict[str, Any]]) -> str:
        output = StringIO()
        writer = csv.writer(output)
        if role == "student":
            writer.writerow(["student_id", "student_name", "class_name", "token"])
            for item in items:
                writer.writerow(
                    [
                        _csv_safe(str(item.get("student_id") or "")),
                        _csv_safe(str(item.get("student_name") or "")),
                        _csv_safe(str(item.get("class_name") or "")),
                        _csv_safe(str(item.get("token") or "")),
                    ]
                )
        else:
            writer.writerow(["teacher_id", "teacher_name", "email", "token"])
            for item in items:
                writer.writerow(
                    [
                        _csv_safe(str(item.get("teacher_id") or "")),
                        _csv_safe(str(item.get("teacher_name") or "")),
                        _csv_safe(str(item.get("email") or "")),
                        _csv_safe(str(item.get("token") or "")),
                    ]
                )
        return output.getvalue()


def build_auth_registry_store(*, data_dir: Optional[Path] = None) -> AuthRegistryStore:
    if data_dir is not None:
        base = Path(data_dir)
    else:
        env_data_dir = str(os.getenv("DATA_DIR", "") or "").strip()
        base = Path(env_data_dir) if env_data_dir else Path(CONFIG_DATA_DIR)
    db_path = base / "auth" / "auth_registry.sqlite3"
    return AuthRegistryStore(db_path=db_path, data_dir=base)


def validate_subject_token_version(*, role: str, subject_id: str, token_version: int) -> bool:
    store = build_auth_registry_store()
    return store.token_version_matches(
        role=role, subject_id=subject_id, token_version=token_version
    )


def validate_password_strength(password: str) -> Optional[str]:
    text = str(password or "")
    if len(text) < _min_password_len():
        return "weak_password"
    if len(text) > 256:
        return "weak_password"
    has_alpha = bool(re.search(r"[A-Za-z]", text))
    has_digit = bool(re.search(r"\d", text))
    if not (has_alpha and has_digit):
        return "weak_password"
    return None


def _table_for_role(role: str) -> tuple[str, str]:
    if role == "student":
        return "student_auth", "student_id"
    return "teacher_auth", "teacher_id"


def _normalize_role(value: Any) -> str:
    return str(value or "").strip().lower()


def _utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def _parse_ts(text: str) -> Optional[datetime]:
    raw = str(text or "").strip()
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _min_password_len() -> int:
    try:
        return max(8, int(str(os.getenv("AUTH_PASSWORD_MIN_LEN", "8") or "8")))
    except Exception:
        return 8


def _lock_threshold() -> int:
    try:
        return max(3, int(str(os.getenv("AUTH_LOGIN_LOCK_THRESHOLD", "5") or "5")))
    except Exception:
        return 5


def _lock_minutes() -> int:
    try:
        return max(1, int(str(os.getenv("AUTH_LOGIN_LOCK_MINUTES", "15") or "15")))
    except Exception:
        return 15


def _max_credential_len() -> int:
    try:
        return max(256, int(str(os.getenv("AUTH_CREDENTIAL_MAX_LEN", "2048") or "2048")))
    except Exception:
        return 2048


def _max_subject_id_len() -> int:
    try:
        return max(32, int(str(os.getenv("AUTH_SUBJECT_ID_MAX_LEN", "128") or "128")))
    except Exception:
        return 128


def _audit_subject_id(value: str) -> str:
    text = str(value or "").strip()
    max_len = _max_subject_id_len()
    if len(text) <= max_len:
        return text
    return text[:max_len]


@lru_cache(maxsize=1)
def _dummy_password_hash() -> str:
    # Cached once to avoid repeatedly burning CPU just to construct a dummy hash.
    return _hash_password("dummy-password-not-used-for-auth")


def _consume_dummy_password_verify(candidate_password: str) -> None:
    _verify_password(str(candidate_password or ""), _dummy_password_hash())


@lru_cache(maxsize=1)
def _dummy_token_hash() -> str:
    return _hash_token("dummy-token-not-used-for-auth")


def _consume_dummy_token_verify(candidate_token: str) -> None:
    _constant_time_eq(_hash_token(str(candidate_token or "")), _dummy_token_hash())


def _credential_pepper() -> str:
    return (
        str(os.getenv("AUTH_CREDENTIAL_PEPPER", "") or "").strip()
        or str(os.getenv("AUTH_TOKEN_SECRET", "") or "").strip()
        or "dev-auth-pepper"
    )


def _hash_token(token: str) -> str:
    text = str(token or "")
    digest = hmac.new(
        _credential_pepper().encode("utf-8"),
        text.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return digest


def _generate_token() -> str:
    return secrets.token_urlsafe(24)


def _admin_username() -> str:
    return str(os.getenv("ADMIN_USERNAME", "admin") or "admin").strip() or "admin"


def _generate_bootstrap_password() -> str:
    for _ in range(8):
        candidate = secrets.token_urlsafe(18)
        if validate_password_strength(candidate) is None:
            return candidate
    return "Admin1234" + secrets.token_hex(6)


def _token_hint(token: str) -> str:
    text = str(token or "")
    if len(text) <= 4:
        return text
    return text[-4:]


def _constant_time_eq(left: str, right: str) -> bool:
    return hmac.compare_digest(str(left or ""), str(right or ""))


def _csv_safe(value: str) -> str:
    text = str(value or "")
    if not text:
        return text
    if text[0] in {"=", "+", "-", "@"}:
        return f"'{text}"
    return text


def _hash_password(password: str) -> str:
    iterations = 310_000
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        str(password or "").encode("utf-8"),
        salt,
        iterations,
    )
    return "pbkdf2_sha256${}${}${}".format(
        iterations,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    )


def _verify_password(password: str, stored: str) -> bool:
    text = str(stored or "").strip()
    parts = text.split("$")
    if len(parts) != 4:
        return False
    algo, iter_text, salt_text, digest_text = parts
    if algo != "pbkdf2_sha256":
        return False
    try:
        iterations = int(iter_text)
        salt = base64.b64decode(salt_text.encode("ascii"), validate=True)
        expected = base64.b64decode(digest_text.encode("ascii"), validate=True)
    except Exception:
        return False
    computed = hashlib.pbkdf2_hmac(
        "sha256",
        str(password or "").encode("utf-8"),
        salt,
        max(1, iterations),
    )
    return hmac.compare_digest(computed, expected)


def _parse_teacher_profile_markdown(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {"name": "", "email": ""}
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return {"name": "", "email": ""}

    name = ""
    email = ""
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        name_match = re.match(r"^-\s*name\s*:\s*(.+)$", line, flags=re.IGNORECASE)
        if name_match:
            candidate = str(name_match.group(1) or "").strip()
            if candidate.lower() not in {"(unknown)", "unknown", "(none)", "none"}:
                name = candidate
            continue
        email_match = re.match(r"^-\s*email\s*:\s*(.+)$", line, flags=re.IGNORECASE)
        if email_match:
            candidate = str(email_match.group(1) or "").strip()
            if candidate.lower() not in {"(unknown)", "unknown", "(none)", "none"}:
                email = candidate
    return {"name": name, "email": email}


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return {key: row[key] for key in row.keys()}


__all__ = [
    "AuthRegistryStore",
    "build_auth_registry_store",
    "validate_password_strength",
    "validate_subject_token_version",
]
