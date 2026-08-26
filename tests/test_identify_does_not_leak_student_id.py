from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from services.api.auth_service import mint_test_token
from tests.helpers.app_factory import create_test_app


def _auth_headers(actor_id: str, role: str, *, secret: str) -> dict[str, str]:
    now = int(time.time())
    claims = {
        "sub": actor_id,
        "role": role,
        "exp": now + 3600,
    }
    if role == "admin":
        claims["tv"] = 1
    token = mint_test_token(claims, secret=secret)
    return {"Authorization": f"Bearer {token}"}


def _load_app(tmp_path: Path, *, secret: str):
    return create_test_app(
        tmp_path,
        env_overrides={
            "MASTER_KEY_DEV_DEFAULT": "dev-key",
            "AUTH_REQUIRED": "1",
            "AUTH_TOKEN_SECRET": secret,
        },
    )


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


def _collect_keys(payload: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(payload, dict):
        keys.update(str(key) for key in payload.keys())
        for value in payload.values():
            keys.update(_collect_keys(value))
    elif isinstance(payload, list):
        for item in payload:
            keys.update(_collect_keys(item))
    return keys


def _assert_opaque_candidate_id(candidate_id: str, *, durable_id: str) -> None:
    assert candidate_id.startswith("cid_")
    assert len(candidate_id) == len("cid_") + 32
    assert candidate_id != durable_id
    assert durable_id not in candidate_id


def test_identify_does_not_leak_student_id(tmp_path: Path):
    secret = "identify-no-leak-secret"
    _write_student_profile(
        tmp_path,
        student_id="S001",
        student_name="刘昊然",
        class_name="高二2403班",
    )
    _write_student_profile(
        tmp_path,
        student_id="S002",
        student_name="刘昊然",
        class_name="高二2404班",
    )

    app_mod = _load_app(tmp_path, secret=secret)
    client = TestClient(app_mod.app)
    admin_headers = _auth_headers("admin", "admin", secret=secret)

    ambiguous = client.post("/auth/student/identify", json={"name": "刘昊然"})
    assert ambiguous.status_code == 200
    ambiguous_payload = ambiguous.json()
    assert ambiguous_payload.get("ok") is False
    assert ambiguous_payload.get("error") == "multiple"
    assert "student_id" not in _collect_keys(ambiguous_payload)
    assert "S001" not in json.dumps(ambiguous_payload, ensure_ascii=False)
    assert "S002" not in json.dumps(ambiguous_payload, ensure_ascii=False)
    for item in ambiguous_payload.get("candidates") or []:
        _assert_opaque_candidate_id(str(item.get("candidate_id") or ""), durable_id="S001")
        student = item.get("student") or {}
        assert set(student.keys()) <= {"student_name", "class_name"}

    identify_res = client.post(
        "/auth/student/identify",
        json={"name": "刘昊然", "class_name": "高二2403班"},
    )
    assert identify_res.status_code == 200
    identify_payload = identify_res.json()
    assert identify_payload.get("ok") is True
    assert "student_id" not in _collect_keys(identify_payload)
    assert "S001" not in json.dumps(identify_payload, ensure_ascii=False)
    candidate_id = str(identify_payload.get("candidate_id") or "")
    _assert_opaque_candidate_id(candidate_id, durable_id="S001")
    student = identify_payload.get("student") or {}
    assert student.get("student_name") == "刘昊然"
    assert student.get("class_name") == "高二2403班"
    assert set(student.keys()) <= {"student_name", "class_name"}

    reset_res = client.post(
        "/auth/teacher/student/reset-passwords",
        headers=admin_headers,
        json={"scope": "student", "student_id": candidate_id, "new_password": "A1b2c3d4"},
    )
    assert reset_res.status_code == 200
    assert reset_res.json().get("ok") is True

    login_res = client.post(
        "/auth/student/login",
        json={
            "candidate_id": candidate_id,
            "credential_type": "password",
            "credential": "A1b2c3d4",
        },
    )
    assert login_res.status_code == 200
    login_payload = login_res.json()
    assert login_payload.get("ok") is True
    assert login_payload.get("subject_id") == "S001"
    assert (login_payload.get("student") or {}).get("student_id") == "S001"
    access_token = str(login_payload.get("access_token") or "")
    assert access_token

    protected = client.get(
        "/student/history/sessions",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"student_id": "S001"},
    )
    assert protected.status_code == 200


def test_identify_teacher_does_not_leak_teacher_id(tmp_path: Path):
    secret = "identify-teacher-no-leak-secret"
    _write_teacher_profile(
        tmp_path,
        teacher_id="teacher_alpha",
        teacher_name="张老师",
        email="alpha@example.com",
    )

    app_mod = _load_app(tmp_path, secret=secret)
    client = TestClient(app_mod.app)
    admin_headers = _auth_headers("admin", "admin", secret=secret)

    export_res = client.post(
        "/auth/admin/teacher/export-tokens",
        headers=admin_headers,
        json={"ids": ["teacher_alpha"]},
    )
    assert export_res.status_code == 200
    token = str((export_res.json().get("items") or [{}])[0].get("token") or "")
    assert token

    identify_res = client.post(
        "/auth/teacher/identify",
        json={"name": "张老师", "email": "alpha@example.com"},
    )
    assert identify_res.status_code == 200
    identify_payload = identify_res.json()
    assert identify_payload.get("ok") is True
    assert "teacher_id" not in _collect_keys(identify_payload)
    assert "teacher_alpha" not in json.dumps(identify_payload, ensure_ascii=False)
    candidate_id = str(identify_payload.get("candidate_id") or "")
    _assert_opaque_candidate_id(candidate_id, durable_id="teacher_alpha")
    teacher = identify_payload.get("teacher") or {}
    assert teacher.get("teacher_name") == "张老师"
    assert set(teacher.keys()) <= {"teacher_name", "email"}

    login_res = client.post(
        "/auth/teacher/login",
        json={
            "candidate_id": candidate_id,
            "credential_type": "token",
            "credential": token,
        },
    )
    assert login_res.status_code == 200
    login_payload = login_res.json()
    assert login_payload.get("ok") is True
    assert login_payload.get("subject_id") == "teacher_alpha"


def test_student_verify_requires_teacher_and_omits_student_id(tmp_path: Path):
    secret = "student-verify-auth-secret"
    _write_student_profile(
        tmp_path,
        student_id="S001",
        student_name="刘昊然",
        class_name="高二2403班",
    )

    app_mod = _load_app(tmp_path, secret=secret)
    client = TestClient(app_mod.app)
    body = {"name": "刘昊然", "class_name": "高二2403班"}

    unauth = client.post("/student/verify", json=body)
    assert unauth.status_code == 401

    student_res = client.post(
        "/student/verify",
        headers=_auth_headers("S001", "student", secret=secret),
        json=body,
    )
    assert student_res.status_code == 403

    teacher_res = client.post(
        "/student/verify",
        headers=_auth_headers("teacher_alpha", "teacher", secret=secret),
        json=body,
    )
    assert teacher_res.status_code == 200
    payload = teacher_res.json()
    assert payload.get("ok") is True
    assert "student_id" not in _collect_keys(payload)
    assert "S001" not in json.dumps(payload, ensure_ascii=False)
    _assert_opaque_candidate_id(str(payload.get("candidate_id") or ""), durable_id="S001")
    student = payload.get("student") or {}
    assert student.get("student_name") == "刘昊然"
    assert student.get("class_name") == "高二2403班"
    assert set(student.keys()) <= {"student_name", "class_name"}
