from __future__ import annotations

import json
import subprocess
import sys
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any

from services.api.auth.identify_service import handle_identify_student, handle_identify_teacher


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


class _StudentStore:
    def __init__(self, profiles: list[dict[str, str]]) -> None:
        self._profiles = profiles
        self.issued: list[tuple[str, str]] = []

    def _list_student_identities(self) -> list[dict[str, str]]:
        return list(self._profiles)

    def _ensure_student_auth(self, **kwargs: Any) -> dict[str, Any] | None:
        sid = str(kwargs.get("student_id") or "").strip()
        if not sid:
            return None
        return {
            "student_id": sid,
            "student_name": str(kwargs.get("student_name") or ""),
            "class_name": str(kwargs.get("class_name") or ""),
            "password_hash": None,
        }

    def issue_opaque_candidate_id(self, *, role: str, subject_id: str) -> str:
        self.issued.append((role, subject_id))
        return f"cid_{role}_{subject_id}"


class _QueryResult:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def fetchall(self) -> list[dict[str, Any]]:
        return list(self._rows)


class _Conn:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def execute(self, query: str, params: tuple[Any, ...]) -> _QueryResult:
        name_norm = str(params[0] or "") if params else ""
        matched = [row for row in self._rows if row.get("name_norm") == name_norm]
        return _QueryResult(matched)


class _ConnectCtx(AbstractContextManager["_Conn"]):
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._conn = _Conn(rows)

    def __enter__(self) -> _Conn:
        return self._conn

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class _TeacherStore:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows
        self.bootstrapped = False
        self.issued: list[tuple[str, str]] = []

    def bootstrap_teachers(self, *, regenerate_token: bool) -> list[dict[str, Any]]:
        self.bootstrapped = True
        return []

    def _connect(self) -> _ConnectCtx:
        return _ConnectCtx(self._rows)

    def issue_opaque_candidate_id(self, *, role: str, subject_id: str) -> str:
        self.issued.append((role, subject_id))
        return f"cid_{role}_{subject_id}"


def test_identify_service_hotspot_removed() -> None:
    target = "services/api/auth/identify_service.py"
    source = Path(target).read_text(encoding="utf-8")
    assert "def handle_identify_student(" in source
    assert "def handle_identify_teacher(" in source
    issues = _issues(target)
    assert not issues, f"C901 issues still present: {issues}"


def test_handle_identify_student_rejects_missing_name() -> None:
    result = handle_identify_student(_StudentStore([]), name="  ", class_name="高二2403班")
    assert result == {"ok": False, "error": "missing_name", "message": "请先输入姓名。"}


def test_handle_identify_student_returns_opaque_candidate_for_unique_match() -> None:
    store = _StudentStore(
        [
            {
                "student_id": "S001",
                "student_name": "刘昊然",
                "class_name": "高二2403班",
            }
        ]
    )
    result = handle_identify_student(store, name="刘昊然", class_name="高二2403班")
    assert result["ok"] is True
    assert result["candidate_id"] == "cid_student_S001"
    assert result["student"] == {"student_name": "刘昊然", "class_name": "高二2403班"}
    assert "student_id" not in result
    assert "student_id" not in result["student"]
    assert store.issued == [("student", "S001")]


def test_handle_identify_student_requires_class_for_duplicate_names() -> None:
    store = _StudentStore(
        [
            {"student_id": "S001", "student_name": "刘昊然", "class_name": "高二2403班"},
            {"student_id": "S002", "student_name": "刘昊然", "class_name": "高二2404班"},
        ]
    )
    result = handle_identify_student(store, name="刘昊然", class_name=None)
    assert result["ok"] is False
    assert result["error"] == "multiple"
    assert len(result["candidates"]) == 2
    assert all("student_id" not in item for item in result["candidates"])


def test_handle_identify_teacher_bootstraps_and_returns_opaque_candidate() -> None:
    store = _TeacherStore(
        [
            {
                "teacher_id": "teacher_alpha",
                "teacher_name": "张老师",
                "email": "alpha@example.com",
                "name_norm": "张老师",
                "email_norm": "alpha@example.com",
                "password_hash": "hashed",
            }
        ]
    )
    result = handle_identify_teacher(store, name="张老师", email="alpha@example.com")
    assert store.bootstrapped is True
    assert result["ok"] is True
    assert result["candidate_id"] == "cid_teacher_teacher_alpha"
    assert result["teacher"] == {"teacher_name": "张老师", "email": "alpha@example.com"}
    assert "teacher_id" not in result
    assert result["password_set"] is True


def test_handle_identify_teacher_requires_email_for_duplicate_names() -> None:
    store = _TeacherStore(
        [
            {
                "teacher_id": "teacher_alpha",
                "teacher_name": "张老师",
                "email": "alpha@example.com",
                "name_norm": "张老师",
                "email_norm": "alpha@example.com",
                "password_hash": "",
            },
            {
                "teacher_id": "teacher_beta",
                "teacher_name": "张老师",
                "email": "beta@example.com",
                "name_norm": "张老师",
                "email_norm": "beta@example.com",
                "password_hash": "",
            },
        ]
    )
    result = handle_identify_teacher(store, name="张老师", email=None)
    assert result["ok"] is False
    assert result["error"] == "multiple"
    assert result["need_email_disambiguation"] is True
    assert len(result["candidates"]) == 2
