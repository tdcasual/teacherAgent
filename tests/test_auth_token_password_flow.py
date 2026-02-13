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


def _load_app(tmp_path: Path, *, secret: str):
    import os

    os.environ["DATA_DIR"] = str(tmp_path / "data")
    os.environ["UPLOADS_DIR"] = str(tmp_path / "uploads")
    os.environ["DIAG_LOG"] = "0"
    os.environ["MASTER_KEY_DEV_DEFAULT"] = "dev-key"
    os.environ["AUTH_REQUIRED"] = "1"
    os.environ["AUTH_TOKEN_SECRET"] = secret

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
