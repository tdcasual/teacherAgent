from __future__ import annotations

import json
import subprocess
import sys
from contextlib import AbstractContextManager
from datetime import datetime
from pathlib import Path
from typing import Any

from services.api.auth.login_service import handle_login


def _issues(path: str) -> list[dict]:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            path,
            "--select",
            "C901",
            "--config",
            "lint.mccabe.max-complexity=10",
            "--output-format",
            "json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    output = (proc.stdout or "").strip()
    return json.loads(output) if output else []


class _QueryResult:
    def __init__(self, row: dict[str, Any] | None) -> None:
        self._row = row

    def fetchone(self) -> dict[str, Any] | None:
        return self._row


class _Conn:
    def __init__(self, row: dict[str, Any] | None) -> None:
        self._row = row

    def execute(self, query: str, params: tuple[Any, ...]) -> _QueryResult:
        if "SELECT * FROM" in query:
            return _QueryResult(self._row)
        return _QueryResult(None)


class _ConnectCtx(AbstractContextManager["_Conn"]):
    def __init__(self, row: dict[str, Any] | None) -> None:
        self._conn = _Conn(row)

    def __enter__(self) -> _Conn:
        return self._conn

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class _Store:
    def __init__(self, row: dict[str, Any] | None) -> None:
        self.row = row
        self.login_attempts: list[dict[str, Any]] = []

    def _connect(self) -> _ConnectCtx:
        return _ConnectCtx(self.row)

    def _append_login_attempt(self, _conn: _Conn, **kwargs: Any) -> None:
        self.login_attempts.append(kwargs)

    def _record_failed_login(self, **_: Any) -> dict[str, Any]:
        return {"failed_count": 1}


def test_login_service_hotspot_removed() -> None:
    target = "services/api/auth/login_service.py"
    source = Path(target).read_text(encoding="utf-8")
    assert "def handle_login(" in source
    issues = _issues(target)
    assert not issues, f"C901 issues still present: {issues}"


def _handle_login(
    store: _Store,
    *,
    role: str,
    candidate_id: str,
    credential_type: str,
    credential: str,
    table: str,
    id_field: str,
    verify_password: Any = lambda _password, _hash: False,
) -> dict[str, Any]:
    return handle_login(
        store,
        role=role,
        candidate_id=candidate_id,
        credential_type=credential_type,
        credential=credential,
        normalize_role=lambda value: str(value or "").strip().lower(),
        table_for_role=lambda _role: (table, id_field),
        max_subject_id_len=lambda: 64,
        max_credential_len=lambda: 128,
        utc_now=lambda: datetime(2026, 2, 16, 12, 0, 0),
        parse_ts=lambda _value: None,
        consume_dummy_password_verify=lambda _value: None,
        consume_dummy_token_verify=lambda _value: None,
        constant_time_eq=lambda left, right: left == right,
        hash_token=lambda value: f"hashed:{value}",
        verify_password=verify_password,
        iso=lambda value: value.isoformat(),
    )


def test_handle_login_rejects_student_token() -> None:
    store = _Store(
        {
            "is_disabled": 0,
            "locked_until": "",
            "token_hash": "hashed:token-123",
            "password_hash": "pwd-hash",
            "token_version": 4,
            "student_name": "刘昊然",
            "class_name": "高二2403班",
        }
    )

    result = _handle_login(
        store,
        role="student",
        candidate_id="S001",
        credential_type="token",
        credential="token-123",
        table="student_auth",
        id_field="student_id",
    )

    assert result == {"ok": False, "error": "invalid_credential_type"}


def test_handle_login_returns_teacher_payload_for_valid_token() -> None:
    store = _Store(
        {
            "is_disabled": 0,
            "locked_until": "",
            "token_hash": "hashed:token-123",
            "password_hash": "pwd-hash",
            "token_version": 4,
            "teacher_name": "张老师",
            "email": "alpha@example.com",
        }
    )

    result = _handle_login(
        store,
        role="teacher",
        candidate_id="teacher_alpha",
        credential_type="token",
        credential="token-123",
        table="teacher_auth",
        id_field="teacher_id",
    )

    assert result["ok"] is True
    assert result["role"] == "teacher"
    assert result["subject_id"] == "teacher_alpha"
    assert result["teacher"]["teacher_name"] == "张老师"
    assert result["token_version"] == 4
