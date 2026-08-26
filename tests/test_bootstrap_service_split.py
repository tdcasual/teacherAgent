from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from contextlib import AbstractContextManager
from datetime import datetime
from pathlib import Path
from typing import Any

from services.api.auth.bootstrap_service import (
    handle_bootstrap_admin,
    handle_bootstrap_teachers,
    write_admin_bootstrap_file,
)


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
    def __init__(self, store: "_AdminStore") -> None:
        self._store = store

    def execute(self, query: str, params: tuple[Any, ...]) -> _QueryResult:
        if "SELECT admin_username FROM admin_auth" in query:
            if self._store.existing is None:
                return _QueryResult(None)
            return _QueryResult({"admin_username": self._store.existing})
        if "INSERT INTO admin_auth" in query:
            self._store.inserted = params
        return _QueryResult(None)


class _ConnectCtx(AbstractContextManager["_Conn"]):
    def __init__(self, store: "_AdminStore") -> None:
        self._conn = _Conn(store)

    def __enter__(self) -> _Conn:
        return self._conn

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class _AdminStore:
    def __init__(self, *, existing: str | None = None) -> None:
        self.existing = existing
        self.inserted: tuple[Any, ...] | None = None
        self.wrote: tuple[str, str] | None = None

    def _connect(self) -> _ConnectCtx:
        return _ConnectCtx(self)

    def _write_admin_bootstrap_file(self, *, username: str, password: str) -> str:
        self.wrote = (username, password)
        return "/tmp/admin_bootstrap.txt"


class _TeacherStore:
    def __init__(self) -> None:
        self.ensured: list[dict[str, Any]] = []

    def _list_teacher_identities(self) -> list[dict[str, str]]:
        return [
            {"teacher_id": "teacher_alpha", "teacher_name": "张老师", "email": "alpha@example.com"},
            {"teacher_id": "", "teacher_name": "skip", "email": ""},
            {"teacher_id": "teacher_beta", "teacher_name": "李老师", "email": ""},
        ]

    def _ensure_teacher_auth(self, **kwargs: Any) -> dict[str, Any] | None:
        self.ensured.append(kwargs)
        return {"teacher_id": kwargs["teacher_id"], **kwargs}


def test_bootstrap_service_hotspot_removed() -> None:
    target = "services/api/auth/bootstrap_service.py"
    source = Path(target).read_text(encoding="utf-8")
    assert "def handle_bootstrap_admin(" in source
    assert "def handle_bootstrap_teachers(" in source
    issues = _issues(target)
    assert not issues, f"C901 issues still present: {issues}"


def test_handle_bootstrap_admin_skips_existing_user() -> None:
    store = _AdminStore(existing="principal_admin")
    result = handle_bootstrap_admin(
        store,
        admin_username=lambda: "principal_admin",
        generate_bootstrap_password=lambda: "GenPass123",
        hash_password=lambda password: f"hashed:{password}",
        utc_now=lambda: datetime(2026, 8, 26, 12, 0, 0),
        iso=lambda value: value.isoformat(),
        normalize=lambda value: str(value or "").strip().lower(),
    )
    assert result == {
        "ok": True,
        "created": False,
        "username": "principal_admin",
        "generated_password": False,
        "bootstrap_file": "",
    }
    assert store.inserted is None
    assert store.wrote is None


def test_handle_bootstrap_admin_generates_password_and_writes_file(
    monkeypatch: Any,
) -> None:
    store = _AdminStore()
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    result = handle_bootstrap_admin(
        store,
        admin_username=lambda: "principal_admin",
        generate_bootstrap_password=lambda: "GenPass123",
        hash_password=lambda password: f"hashed:{password}",
        utc_now=lambda: datetime(2026, 8, 26, 12, 0, 0),
        iso=lambda value: value.isoformat(),
        normalize=lambda value: str(value or "").strip().lower(),
    )
    assert result["ok"] is True
    assert result["created"] is True
    assert result["generated_password"] is True
    assert result["bootstrap_file"] == "/tmp/admin_bootstrap.txt"
    assert store.wrote == ("principal_admin", "GenPass123")
    assert store.inserted is not None
    assert store.inserted[0] == "principal_admin"
    assert store.inserted[2] == "hashed:GenPass123"


def test_handle_bootstrap_teachers_ensures_each_identity() -> None:
    store = _TeacherStore()
    rows = handle_bootstrap_teachers(store, regenerate_token=False)
    assert [item["teacher_id"] for item in rows] == ["teacher_alpha", "teacher_beta"]
    assert len(store.ensured) == 2
    assert store.ensured[0]["regenerate_token"] is False
    assert store.ensured[1]["teacher_name"] == "李老师"


def test_write_admin_bootstrap_file_chmod_600(tmp_path: Path) -> None:
    class _DirStore:
        data_dir = tmp_path

    path = write_admin_bootstrap_file(
        _DirStore(),
        username="principal_admin",
        password="TempPass123",
        utc_now=lambda: datetime(2026, 8, 26, 12, 0, 0),
        iso=lambda value: value.isoformat(),
    )
    written = Path(path)
    assert written == tmp_path / "auth" / "admin_bootstrap.txt"
    text = written.read_text(encoding="utf-8")
    assert "username=principal_admin" in text
    assert "password=TempPass123" in text
    mode = stat.S_IMODE(written.stat().st_mode)
    assert mode & 0o077 == 0
    assert mode == 0o600 or os.name == "nt"
