from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from services.api.auth_service import mint_test_token
from services.api.core_utils import normalize
from tests.helpers.app_factory import create_test_app

SECRET = "admin-create-teacher-secret"


@pytest.fixture(autouse=True)
def _restore_auth_env() -> None:
    keys = ("AUTH_REQUIRED", "AUTH_TOKEN_SECRET", "APP_ENV", "ADMIN_USERNAME", "ADMIN_PASSWORD")
    saved = {key: os.environ.get(key) for key in keys}
    try:
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _admin_headers(actor_id: str = "admin") -> dict[str, str]:
    token = mint_test_token(
        {"sub": actor_id, "role": "admin", "tv": 1, "tenant_id": "school"},
        secret=SECRET,
    )
    return {"Authorization": f"Bearer {token}"}


def _auth_off_app(tmp_path: Path):
    return create_test_app(
        tmp_path,
        env_overrides={
            "MASTER_KEY_DEV_DEFAULT": "dev-key",
            "AUTH_REQUIRED": "0",
            "AUTH_TOKEN_SECRET": SECRET,
            "APP_ENV": "development",
        },
    )


def _auth_on_app(tmp_path: Path):
    return create_test_app(
        tmp_path,
        env_overrides={
            "MASTER_KEY_DEV_DEFAULT": "dev-key",
            "AUTH_REQUIRED": "1",
            "AUTH_TOKEN_SECRET": SECRET,
            "APP_ENV": "development",
            "ADMIN_USERNAME": "admin",
        },
        env_unset=["ADMIN_PASSWORD"],
    )


def _expected_teacher_id(name: str, email: str = "") -> str:
    seed = f"{normalize(name)}|{normalize(email)}"
    return "t_" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]


def test_create_teacher_auth_off_without_bearer_is_401(tmp_path: Path) -> None:
    app_mod = _auth_off_app(tmp_path)
    client = TestClient(app_mod.app)
    res = client.post("/auth/admin/teacher/create", json={"teacher_name": "张老师"})
    assert res.status_code == 401
    assert res.json().get("detail") == "missing_authorization"
    assert res.json().get("detail") != "admin_local"


def test_list_disable_reset_auth_off_without_bearer_is_401(tmp_path: Path) -> None:
    app_mod = _auth_off_app(tmp_path)
    client = TestClient(app_mod.app)
    listed = client.get("/auth/admin/teacher/list")
    assert listed.status_code == 401
    disabled = client.post(
        "/auth/admin/teacher/set-disabled",
        json={"target_id": "t_zhang", "is_disabled": True},
    )
    assert disabled.status_code == 401
    reset = client.post(
        "/auth/admin/teacher/reset-password",
        json={"target_id": "t_zhang"},
    )
    assert reset.status_code == 401


def test_create_teacher_with_optional_id_and_generated_password(tmp_path: Path) -> None:
    app_mod = _auth_on_app(tmp_path)
    client = TestClient(app_mod.app)
    headers = _admin_headers()
    res = client.post(
        "/auth/admin/teacher/create",
        headers=headers,
        json={
            "teacher_name": "张老师",
            "email": "zhang@example.com",
            "teacher_id": "t_zhang",
        },
    )
    assert res.status_code == 201
    payload = res.json()
    assert payload.get("ok") is True
    assert payload.get("teacher_id") == "t_zhang"
    temp_password = str(payload.get("temp_password") or "")
    assert temp_password
    assert "temp_password" not in str(payload.get("teacher") or {})

    login = client.post(
        "/auth/teacher/login",
        json={
            "candidate_id": "t_zhang",
            "credential_type": "password",
            "credential": temp_password,
        },
    )
    assert login.status_code == 200
    assert login.json().get("ok") is True
    assert login.json().get("role") == "teacher"


def test_create_teacher_omitted_id_is_stable_hash(tmp_path: Path) -> None:
    app_mod = _auth_on_app(tmp_path)
    client = TestClient(app_mod.app)
    headers = _admin_headers()
    res = client.post(
        "/auth/admin/teacher/create",
        headers=headers,
        json={"teacher_name": "李老师", "email": "li@example.com"},
    )
    assert res.status_code == 201
    teacher_id = str(res.json().get("teacher_id") or "")
    assert teacher_id == _expected_teacher_id("李老师", "li@example.com")
    assert teacher_id.startswith("t_")
    assert teacher_id != "teacher"


def test_create_teacher_rejects_reserved_and_invalid_ids(tmp_path: Path) -> None:
    app_mod = _auth_on_app(tmp_path)
    client = TestClient(app_mod.app)
    headers = _admin_headers()
    reserved = client.post(
        "/auth/admin/teacher/create",
        headers=headers,
        json={"teacher_name": "系统老师", "teacher_id": "teacher"},
    )
    assert reserved.status_code == 400
    assert reserved.json().get("detail") == "invalid_teacher_id"

    invalid = client.post(
        "/auth/admin/teacher/create",
        headers=headers,
        json={"teacher_name": "系统老师", "teacher_id": "-bad"},
    )
    assert invalid.status_code == 400
    assert invalid.json().get("detail") == "invalid_teacher_id"

    too_short = client.post(
        "/auth/admin/teacher/create",
        headers=headers,
        json={"teacher_name": "系统老师", "teacher_id": "T01"},
    )
    assert too_short.status_code == 400
    assert too_short.json().get("detail") == "invalid_teacher_id"


def test_create_teacher_conflict_on_id_and_email(tmp_path: Path) -> None:
    app_mod = _auth_on_app(tmp_path)
    client = TestClient(app_mod.app)
    headers = _admin_headers()
    first = client.post(
        "/auth/admin/teacher/create",
        headers=headers,
        json={
            "teacher_name": "王老师",
            "email": "wang@example.com",
            "teacher_id": "t_wang",
        },
    )
    assert first.status_code == 201

    taken_id = client.post(
        "/auth/admin/teacher/create",
        headers=headers,
        json={"teacher_name": "另一人", "teacher_id": "t_wang"},
    )
    assert taken_id.status_code == 409
    assert taken_id.json().get("detail") == "teacher_id_taken"

    taken_email = client.post(
        "/auth/admin/teacher/create",
        headers=headers,
        json={"teacher_name": "另一人", "email": "wang@example.com", "teacher_id": "t_wang2"},
    )
    assert taken_email.status_code == 409
    assert taken_email.json().get("detail") == "email_taken"


def test_admin_can_list_disable_and_reset_created_teacher(tmp_path: Path) -> None:
    app_mod = _auth_on_app(tmp_path)
    client = TestClient(app_mod.app)
    headers = _admin_headers()
    created = client.post(
        "/auth/admin/teacher/create",
        headers=headers,
        json={"teacher_name": "赵老师", "teacher_id": "t_zhao"},
    )
    assert created.status_code == 201

    listed = client.get("/auth/admin/teacher/list", headers=headers)
    assert listed.status_code == 200
    ids = {str(item.get("teacher_id") or "") for item in listed.json().get("items") or []}
    assert "t_zhao" in ids

    disabled = client.post(
        "/auth/admin/teacher/set-disabled",
        headers=headers,
        json={"target_id": "t_zhao", "is_disabled": True},
    )
    assert disabled.status_code == 200
    assert disabled.json().get("is_disabled") is True

    reset = client.post(
        "/auth/admin/teacher/reset-password",
        headers=headers,
        json={"target_id": "t_zhao"},
    )
    assert reset.status_code == 200
    assert str(reset.json().get("temp_password") or "").strip()
