from __future__ import annotations

import json
import time
from pathlib import Path

from fastapi.testclient import TestClient

from services.api.auth_service import mint_test_token
from tests.helpers.app_factory import create_test_app


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
    env_overrides = {
        "MASTER_KEY_DEV_DEFAULT": "dev-key",
        "AUTH_REQUIRED": "1",
        "AUTH_TOKEN_SECRET": secret,
        "ADMIN_USERNAME": admin_username,
    }
    env_unset: list[str] = []
    if admin_password is None:
        env_unset.append("ADMIN_PASSWORD")
    else:
        env_overrides["ADMIN_PASSWORD"] = admin_password
    return create_test_app(tmp_path, env_overrides=env_overrides, env_unset=env_unset)


def _write_student_profile(
    base: Path, *, student_id: str, student_name: str, class_name: str
) -> None:
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


def test_teacher_can_reset_student_passwords_by_scope(tmp_path: Path):
    secret = "auth-teacher-reset-student-passwords-secret"
    _write_student_profile(
        tmp_path,
        student_id="S001",
        student_name="刘昊然",
        class_name="高二2403班",
    )
    _write_student_profile(
        tmp_path,
        student_id="S002",
        student_name="畅爽",
        class_name="高二2403班",
    )
    _write_student_profile(
        tmp_path,
        student_id="S003",
        student_name="武熙语",
        class_name="高二2404班",
    )
    _write_teacher_profile(
        tmp_path,
        teacher_id="teacher_alpha",
        teacher_name="张老师",
        email="alpha@example.com",
    )

    app_mod = _load_app(tmp_path, secret=secret)
    client = TestClient(app_mod.app)
    admin_headers = _auth_headers("admin_1", "admin", secret=secret)

    export_teacher_res = client.post(
        "/auth/admin/teacher/export-tokens",
        headers=admin_headers,
        json={"ids": ["teacher_alpha"]},
    )
    assert export_teacher_res.status_code == 200
    teacher_token = str(
        ((export_teacher_res.json().get("items") or [{}])[0].get("token") or "")
    )
    assert teacher_token

    teacher_login_res = client.post(
        "/auth/teacher/login",
        json={
            "candidate_id": "teacher_alpha",
            "credential_type": "token",
            "credential": teacher_token,
        },
    )
    assert teacher_login_res.status_code == 200
    teacher_access_token = str(teacher_login_res.json().get("access_token") or "")
    assert teacher_access_token
    teacher_headers = {"Authorization": f"Bearer {teacher_access_token}"}

    reset_one_res = client.post(
        "/auth/teacher/student/reset-passwords",
        headers=teacher_headers,
        json={"scope": "student", "student_id": "S001"},
    )
    assert reset_one_res.status_code == 200
    reset_one_payload = reset_one_res.json()
    assert reset_one_payload.get("ok") is True
    assert int(reset_one_payload.get("count") or 0) == 1
    first_temp_password = str(
        ((reset_one_payload.get("items") or [{}])[0].get("temp_password") or "")
    )
    assert first_temp_password

    first_student_login = client.post(
        "/auth/student/login",
        json={
            "candidate_id": "S001",
            "credential_type": "password",
            "credential": first_temp_password,
        },
    )
    assert first_student_login.status_code == 200
    assert first_student_login.json().get("ok") is True
    first_student_access_token = str(first_student_login.json().get("access_token") or "")
    assert first_student_access_token

    reset_class_res = client.post(
        "/auth/teacher/student/reset-passwords",
        headers=teacher_headers,
        json={
            "scope": "class",
            "class_name": "高二2403班",
            "new_password": "ClassPwd123",
        },
    )
    assert reset_class_res.status_code == 200
    reset_class_payload = reset_class_res.json()
    assert reset_class_payload.get("ok") is True
    class_items = reset_class_payload.get("items") or []
    class_ids = {str(item.get("student_id") or "") for item in class_items}
    assert class_ids == {"S001", "S002"}
    assert all(str(item.get("temp_password") or "") == "ClassPwd123" for item in class_items)

    revoked_after_class_reset = client.get(
        "/student/history/sessions",
        headers={"Authorization": f"Bearer {first_student_access_token}"},
        params={"student_id": "S001"},
    )
    assert revoked_after_class_reset.status_code == 401
    assert revoked_after_class_reset.json().get("detail") == "token_revoked"

    for sid in ("S001", "S002"):
        class_login_res = client.post(
            "/auth/student/login",
            json={
                "candidate_id": sid,
                "credential_type": "password",
                "credential": "ClassPwd123",
            },
        )
        assert class_login_res.status_code == 200
        assert class_login_res.json().get("ok") is True

    reset_all_res = client.post(
        "/auth/teacher/student/reset-passwords",
        headers=teacher_headers,
        json={"scope": "all"},
    )
    assert reset_all_res.status_code == 200
    reset_all_payload = reset_all_res.json()
    assert reset_all_payload.get("ok") is True
    all_items = reset_all_payload.get("items") or []
    all_ids = {str(item.get("student_id") or "") for item in all_items}
    assert all_ids == {"S001", "S002", "S003"}
    assert all(str(item.get("temp_password") or "").strip() for item in all_items)


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
    assert disabled_login.json().get("error") == "invalid_credential"

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
