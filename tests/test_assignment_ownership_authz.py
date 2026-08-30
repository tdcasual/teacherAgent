from __future__ import annotations

import json
import os
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from services.api.auth_service import mint_test_token
from tests.helpers.app_factory import create_test_app

SECRET = "test-secret-key-for-unit-tests"
_AUTH_KEYS = ("AUTH_REQUIRED", "AUTH_TOKEN_SECRET", "APP_ENV")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


@contextmanager
def _auth_env():
    saved = {key: os.environ.get(key) for key in _AUTH_KEYS}
    try:
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _auth_app(tmp: Path):
    return create_test_app(
        tmp,
        env_overrides={
            "AUTH_REQUIRED": "1",
            "AUTH_TOKEN_SECRET": SECRET,
            "APP_ENV": "development",
        },
    )


def _bearer(actor_id: str, role: str) -> dict[str, str]:
    token = mint_test_token({"sub": actor_id, "role": role, "tenant_id": "school"}, secret=SECRET)
    return {"Authorization": f"Bearer {token}"}


def test_assignments_list_filters_to_owning_teacher() -> None:
    with _auth_env(), TemporaryDirectory() as td:
        tmp = Path(td)
        _write_json(
            tmp / "data" / "assignments" / "HW_A" / "meta.json",
            {"assignment_id": "HW_A", "teacher_id": "t_zhang", "generated_at": "2026-02-08T09:00:00"},
        )
        _write_json(
            tmp / "data" / "assignments" / "HW_B" / "meta.json",
            {"assignment_id": "HW_B", "teacher_id": "t_li", "generated_at": "2026-02-08T10:00:00"},
        )
        app_mod = _auth_app(tmp)
        with TestClient(app_mod.app) as client:
            res = client.get("/assignments", headers=_bearer("t_zhang", "teacher"))
        assert res.status_code == 200
        ids = [item.get("assignment_id") for item in res.json().get("assignments") or []]
        assert ids == ["HW_A"]


def test_teacher_progress_forbids_other_teachers_assignment() -> None:
    with _auth_env(), TemporaryDirectory() as td:
        tmp = Path(td)
        _write_json(
            tmp / "data" / "assignments" / "HW_B" / "meta.json",
            {
                "assignment_id": "HW_B",
                "teacher_id": "t_li",
                "date": "2026-02-05",
                "scope": "public",
            },
        )
        app_mod = _auth_app(tmp)
        with TestClient(app_mod.app) as client:
            res = client.get(
                "/teacher/assignment/progress",
                params={"assignment_id": "HW_B"},
                headers=_bearer("t_zhang", "teacher"),
            )
        assert res.status_code == 403
        assert res.json().get("detail") == "forbidden_assignment_owner"


def test_teacher_progress_allows_owner() -> None:
    with _auth_env(), TemporaryDirectory() as td:
        tmp = Path(td)
        _write_json(
            tmp / "data" / "student_profiles" / "S001.json",
            {"student_id": "S001"},
        )
        _write_json(
            tmp / "data" / "assignments" / "HW_A" / "meta.json",
            {
                "assignment_id": "HW_A",
                "teacher_id": "t_zhang",
                "date": "2026-02-05",
                "scope": "student",
                "student_ids": ["S001"],
            },
        )
        app_mod = _auth_app(tmp)
        with TestClient(app_mod.app) as client:
            res = client.get(
                "/teacher/assignment/progress",
                params={"assignment_id": "HW_A", "include_students": "false"},
                headers=_bearer("t_zhang", "teacher"),
            )
        assert res.status_code == 200
        assert res.json().get("ok") is True


def test_student_assignment_detail_compat_published_without_visibility_status() -> None:
    with _auth_env(), TemporaryDirectory() as td:
        tmp = Path(td)
        _write_json(
            tmp / "data" / "assignments" / "HW_LEGACY" / "meta.json",
            {
                "assignment_id": "HW_LEGACY",
                "teacher_id": "t_zhang",
                "scope": "public",
            },
        )
        app_mod = _auth_app(tmp)
        with TestClient(app_mod.app) as client:
            res = client.get(
                "/assignment/HW_LEGACY",
                headers=_bearer("S001", "student"),
            )
        assert res.status_code == 200


def test_student_assignment_detail_hides_orphan_without_teacher_id() -> None:
    with _auth_env(), TemporaryDirectory() as td:
        tmp = Path(td)
        _write_json(
            tmp / "data" / "assignments" / "HW_ORPHAN" / "meta.json",
            {"assignment_id": "HW_ORPHAN", "scope": "public"},
        )
        app_mod = _auth_app(tmp)
        with TestClient(app_mod.app) as client:
            res = client.get(
                "/assignment/HW_ORPHAN",
                headers=_bearer("S001", "student"),
            )
        assert res.status_code == 403


def test_teacher_assignments_progress_filters_to_owner() -> None:
    with _auth_env(), TemporaryDirectory() as td:
        tmp = Path(td)
        _write_json(
            tmp / "data" / "assignments" / "HW_A" / "meta.json",
            {
                "assignment_id": "HW_A",
                "teacher_id": "t_zhang",
                "date": "2026-02-05",
                "scope": "public",
            },
        )
        _write_json(
            tmp / "data" / "assignments" / "HW_B" / "meta.json",
            {
                "assignment_id": "HW_B",
                "teacher_id": "t_li",
                "date": "2026-02-05",
                "scope": "public",
            },
        )
        app_mod = _auth_app(tmp)
        with TestClient(app_mod.app) as client:
            res = client.get(
                "/teacher/assignments/progress",
                params={"date": "2026-02-05"},
                headers=_bearer("t_zhang", "teacher"),
            )
        assert res.status_code == 200
        ids = [item.get("assignment_id") for item in res.json().get("assignments") or []]
        assert ids == ["HW_A"]


def test_service_list_includes_orphans() -> None:
    with _auth_env(), TemporaryDirectory() as td:
        tmp = Path(td)
        _write_json(
            tmp / "data" / "assignments" / "HW_A" / "meta.json",
            {"assignment_id": "HW_A", "teacher_id": "t_zhang", "generated_at": "2026-02-08T09:00:00"},
        )
        _write_json(
            tmp / "data" / "assignments" / "HW_ORPHAN" / "meta.json",
            {"assignment_id": "HW_ORPHAN", "generated_at": "2026-02-08T10:00:00"},
        )
        app_mod = _auth_app(tmp)
        with TestClient(app_mod.app) as client:
            res = client.get("/assignments", headers=_bearer("svc", "service"))
        assert res.status_code == 200
        ids = [item.get("assignment_id") for item in res.json().get("assignments") or []]
        assert "HW_A" in ids
        assert "HW_ORPHAN" in ids
