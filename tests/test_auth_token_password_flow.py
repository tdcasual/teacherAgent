from __future__ import annotations

import importlib
import json
import time
from pathlib import Path

from fastapi.testclient import TestClient

from services.api.auth_service import mint_test_token


def _auth_headers(actor_id: str, role: str, *, secret: str) -> dict[str, str]:
    now = int(time.time())
    token = mint_test_token(
        {
            "sub": actor_id,
            "role": role,
            "exp": now + 3600,
        },
        secret=secret,
    )
    return {"Authorization": f"Bearer {token}"}


def _load_app(
    tmp_path: Path,
    *,
    secret: str,
    admin_username: str = "admin",
    admin_password: str | None = None,
):
    import os

    os.environ["DATA_DIR"] = str(tmp_path / "data")
    os.environ["UPLOADS_DIR"] = str(tmp_path / "uploads")
    os.environ["DIAG_LOG"] = "0"
    os.environ["MASTER_KEY_DEV_DEFAULT"] = "dev-key"
    os.environ["AUTH_REQUIRED"] = "1"
    os.environ["AUTH_TOKEN_SECRET"] = secret
    os.environ["ADMIN_USERNAME"] = admin_username
    if admin_password is None:
        os.environ.pop("ADMIN_PASSWORD", None)
    else:
        os.environ["ADMIN_PASSWORD"] = admin_password

    import services.api.app as app_mod

    importlib.reload(app_mod)
    return app_mod


def _write_student_profile(base: Path, *, student_id: str, student_name: str, class_name: str) -> None:
    profiles_dir = base / "data" / "student_profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "student_id": student_id,
        "student_name": student_name,
        "class_name": class_name,
    }
    (profiles_dir / f"{student_id}.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )


def _write_teacher_profile(base: Path, *, teacher_id: str, teacher_name: str, email: str) -> None:
    root = base / "data" / "teacher_workspaces" / teacher_id
    root.mkdir(parents=True, exist_ok=True)
    profile = "\n".join(
        [
            "# Teacher Profile",
            f"- name: {teacher_name}",
            f"- email: {email}",
        ]
    )
    (root / "USER.md").write_text(profile, encoding="utf-8")


def test_student_token_password_login_and_token_rotation(tmp_path: Path):
    secret = "auth-token-flow-secret"
    _write_student_profile(
        tmp_path,
        student_id="S001",
        student_name="刘昊然",
        class_name="高二2403班",
    )

    app_mod = _load_app(tmp_path, secret=secret)
    client = TestClient(app_mod.app)
    admin_headers = _auth_headers("admin_1", "admin", secret=secret)

    export_res = client.post(
        "/auth/admin/student/export-tokens",
        headers=admin_headers,
        json={"ids": ["S001"]},
    )
    assert export_res.status_code == 200
    exported = export_res.json()
    assert exported.get("ok") is True
    token = str((exported.get("items") or [{}])[0].get("token") or "")
    assert token

    identify_res = client.post(
        "/auth/student/identify",
        json={"name": "刘昊然", "class_name": "高二2403班"},
    )
    assert identify_res.status_code == 200
    identify_payload = identify_res.json()
    assert identify_payload.get("ok") is True
    candidate_id = str(identify_payload.get("candidate_id") or "")
    assert candidate_id == "S001"

    login_res = client.post(
        "/auth/student/login",
        json={
            "candidate_id": candidate_id,
            "credential_type": "token",
            "credential": token,
        },
    )
    assert login_res.status_code == 200
    login_payload = login_res.json()
    assert login_payload.get("ok") is True
    access_token = str(login_payload.get("access_token") or "")
    assert access_token

    protected_before_rotate = client.get(
        "/student/history/sessions",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"student_id": "S001"},
    )
    assert protected_before_rotate.status_code == 200

    set_password_res = client.post(
        "/auth/student/set-password",
        json={
            "candidate_id": "S001",
            "credential_type": "token",
            "credential": token,
            "new_password": "A1b2c3d4",
        },
    )
    assert set_password_res.status_code == 200
    assert set_password_res.json().get("ok") is True

    pwd_login_res = client.post(
        "/auth/student/login",
        json={
            "candidate_id": "S001",
            "credential_type": "password",
            "credential": "A1b2c3d4",
        },
    )
    assert pwd_login_res.status_code == 200
    pwd_payload = pwd_login_res.json()
    assert pwd_payload.get("ok") is True
    old_access_token = str(pwd_payload.get("access_token") or "")
    assert old_access_token

    rotate_res = client.post(
        "/auth/admin/student/reset-token",
        headers=admin_headers,
        json={"target_id": "S001"},
    )
    assert rotate_res.status_code == 200
    assert rotate_res.json().get("ok") is True

    protected_after_rotate = client.get(
        "/student/history/sessions",
        headers={"Authorization": f"Bearer {old_access_token}"},
        params={"student_id": "S001"},
    )
    assert protected_after_rotate.status_code == 401
    assert protected_after_rotate.json().get("detail") == "token_revoked"


def test_teacher_identify_requires_email_for_duplicate_names(tmp_path: Path):
    secret = "auth-teacher-flow-secret"
    _write_teacher_profile(
        tmp_path,
        teacher_id="teacher_alpha",
        teacher_name="张老师",
        email="alpha@example.com",
    )
    _write_teacher_profile(
        tmp_path,
        teacher_id="teacher_beta",
        teacher_name="张老师",
        email="beta@example.com",
    )

    app_mod = _load_app(tmp_path, secret=secret)
    client = TestClient(app_mod.app)
    admin_headers = _auth_headers("admin_1", "admin", secret=secret)

    export_res = client.post(
        "/auth/admin/teacher/export-tokens",
        headers=admin_headers,
        json={"ids": ["teacher_alpha", "teacher_beta"]},
    )
    assert export_res.status_code == 200
    export_payload = export_res.json()
    assert export_payload.get("ok") is True
    items = export_payload.get("items") or []
    by_id = {str(item.get("teacher_id") or ""): item for item in items}
    assert "teacher_alpha" in by_id
    assert "teacher_beta" in by_id

    ambiguous = client.post(
        "/auth/teacher/identify",
        json={"name": "张老师"},
    )
    assert ambiguous.status_code == 200
    ambiguous_payload = ambiguous.json()
    assert ambiguous_payload.get("ok") is False
    assert ambiguous_payload.get("error") == "multiple"
    assert ambiguous_payload.get("need_email_disambiguation") is True

    identified = client.post(
        "/auth/teacher/identify",
        json={"name": "张老师", "email": "alpha@example.com"},
    )
    assert identified.status_code == 200
    identified_payload = identified.json()
    assert identified_payload.get("ok") is True
    assert identified_payload.get("candidate_id") == "teacher_alpha"

    token_alpha = str(by_id["teacher_alpha"].get("token") or "")
    login_res = client.post(
        "/auth/teacher/login",
        json={
            "candidate_id": "teacher_alpha",
            "credential_type": "token",
            "credential": token_alpha,
        },
    )
    assert login_res.status_code == 200
    login_payload = login_res.json()
    assert login_payload.get("ok") is True
    access_token = str(login_payload.get("access_token") or "")
    assert access_token

    protected = client.get(
        "/teacher/history/sessions",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert protected.status_code == 200


def test_admin_bootstrap_login_and_manage_teacher_accounts(tmp_path: Path):
    secret = "auth-admin-bootstrap-secret"
    _write_teacher_profile(
        tmp_path,
        teacher_id="teacher_alpha",
        teacher_name="张老师",
        email="alpha@example.com",
    )
    app_mod = _load_app(
        tmp_path,
        secret=secret,
        admin_username="principal_admin",
        admin_password=None,
    )
    client = TestClient(app_mod.app)

    bootstrap_trigger = client.post(
        "/auth/admin/login",
        json={"username": "principal_admin", "password": "wrong-password"},
    )
    assert bootstrap_trigger.status_code == 200
    assert bootstrap_trigger.json().get("ok") is False

    bootstrap_path = tmp_path / "data" / "auth" / "admin_bootstrap.txt"
    assert bootstrap_path.exists()
    bootstrap_text = bootstrap_path.read_text(encoding="utf-8")
    assert "username=principal_admin" in bootstrap_text
    password_line = next(
        (line for line in bootstrap_text.splitlines() if line.startswith("password=")),
        "",
    )
    admin_password = password_line.replace("password=", "", 1).strip()
    assert admin_password

    login_res = client.post(
        "/auth/admin/login",
        json={"username": "principal_admin", "password": admin_password},
    )
    assert login_res.status_code == 200
    login_payload = login_res.json()
    assert login_payload.get("ok") is True
    assert login_payload.get("role") == "admin"
    admin_access_token = str(login_payload.get("access_token") or "")
    assert admin_access_token
    admin_headers = {"Authorization": f"Bearer {admin_access_token}"}

    teacher_list = client.get("/auth/admin/teacher/list", headers=admin_headers)
    assert teacher_list.status_code == 200
    teacher_items = teacher_list.json().get("items") or []
    teacher_ids = {str(item.get("teacher_id") or "") for item in teacher_items}
    assert "teacher_alpha" in teacher_ids

    disable_res = client.post(
        "/auth/admin/teacher/set-disabled",
        headers=admin_headers,
        json={"target_id": "teacher_alpha", "is_disabled": True},
    )
    assert disable_res.status_code == 200
    assert disable_res.json().get("ok") is True
    assert disable_res.json().get("is_disabled") is True

    export_res = client.post(
        "/auth/admin/teacher/export-tokens",
        headers=admin_headers,
        json={"ids": ["teacher_alpha"]},
    )
    assert export_res.status_code == 200
    export_items = export_res.json().get("items") or []
    teacher_token = str((export_items[0] if export_items else {}).get("token") or "")
    assert teacher_token

    disabled_login = client.post(
        "/auth/teacher/login",
        json={
            "candidate_id": "teacher_alpha",
            "credential_type": "token",
            "credential": teacher_token,
        },
    )
    assert disabled_login.status_code == 200
    assert disabled_login.json().get("ok") is False
    assert disabled_login.json().get("error") == "disabled"

    enable_res = client.post(
        "/auth/admin/teacher/set-disabled",
        headers=admin_headers,
        json={"target_id": "teacher_alpha", "is_disabled": False},
    )
    assert enable_res.status_code == 200
    assert enable_res.json().get("ok") is True
    assert enable_res.json().get("is_disabled") is False

    reset_pwd_res = client.post(
        "/auth/admin/teacher/reset-password",
        headers=admin_headers,
        json={"target_id": "teacher_alpha"},
    )
    assert reset_pwd_res.status_code == 200
    reset_payload = reset_pwd_res.json()
    assert reset_payload.get("ok") is True
    assert reset_payload.get("generated_password") is True
    temp_password = str(reset_payload.get("temp_password") or "")
    assert temp_password

    pwd_login_res = client.post(
        "/auth/teacher/login",
        json={
            "candidate_id": "teacher_alpha",
            "credential_type": "password",
            "credential": temp_password,
        },
    )
    assert pwd_login_res.status_code == 200
    assert pwd_login_res.json().get("ok") is True
