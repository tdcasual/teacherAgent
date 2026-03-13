from __future__ import annotations

import json
import subprocess
import sys
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any

from services.api.auth.password_reset_service import handle_reset_student_passwords


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
    def __init__(self, rows: dict[str, dict[str, Any]]) -> None:
        self._rows = rows

    def execute(self, query: str, params: tuple[Any, ...]) -> _QueryResult:
        if "FROM student_auth WHERE student_id" in query:
            sid = str(params[0] or "")
            return _QueryResult(self._rows.get(sid))
        return _QueryResult(None)


class _ConnectCtx(AbstractContextManager["_Conn"]):
    def __init__(self, conn: _Conn) -> None:
        self._conn = conn

    def __enter__(self) -> _Conn:
        return self._conn

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class _Store:
    def __init__(self) -> None:
        self.audit: list[dict[str, Any]] = []
        self._rows = {
            "S001": {
                "student_id": "S001",
                "student_name": "刘昊然",
                "class_name": "高二2403班",
                "token_version": 3,
            }
        }

    def _resolve_student_password_targets(self, **_: Any) -> dict[str, Any]:
        return {
            "ok": True,
            "items": [
                {"student_id": "S001", "student_name": "刘昊然", "class_name": "高二2403班"},
                {"student_id": "", "student_name": "bad", "class_name": "高二2403班"},
            ],
        }

    def _ensure_student_auth(self, **kwargs: Any) -> dict[str, Any] | None:
        sid = str(kwargs.get("student_id") or "")
        if not sid:
            return None
        return {
            "student_name": str(kwargs.get("student_name") or ""),
            "class_name": str(kwargs.get("class_name") or ""),
        }

    def _connect(self) -> _ConnectCtx:
        return _ConnectCtx(_Conn(self._rows))

    def _append_audit(self, _conn: _Conn, **kwargs: Any) -> None:
        self.audit.append(kwargs)


def test_password_reset_student_hotspot_removed() -> None:
    target = "services/api/auth/password_reset_service.py"
    source = Path(target).read_text(encoding="utf-8")
    assert "def handle_reset_student_passwords(" in source
    issues = _issues(target)
    assert not issues, f"C901 issues still present: {issues}"


def test_handle_reset_student_passwords_uses_explicit_password_for_each_item() -> None:
    store = _Store()

    result = handle_reset_student_passwords(
        store,
        scope="class",
        student_id=None,
        class_name="高二2403班",
        new_password="ClassPwd123",
        actor_id="teacher_1",
        actor_role="teacher",
        generate_bootstrap_password=lambda: "TempPwd999",
        validate_password_strength=lambda password: None if len(password) >= 8 else "weak_password",
        hash_password=lambda password: f"hashed:{password}",
        utc_now=lambda: object(),  # type: ignore[return-value]
        iso=lambda _value: "2026-02-16T12:00:00",
    )

    assert result["ok"] is True
    assert result["generated_password"] is False
    assert result["count"] == 1
    assert result["items"][0]["temp_password"] == "ClassPwd123"
    assert store.audit[0]["detail"]["generated"] is False
