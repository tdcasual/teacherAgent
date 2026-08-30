from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from services.api.auth_registry_service import AuthRegistryStore
from services.api.auth_service import mint_test_token
from tests.helpers.app_factory import create_test_app


@pytest.fixture(autouse=True)
def _restore_auth_required() -> None:
    previous = os.environ.get("AUTH_REQUIRED")
    yield
    if previous is None:
        os.environ.pop("AUTH_REQUIRED", None)
    else:
        os.environ["AUTH_REQUIRED"] = previous


def _auth_headers(actor_id: str, role: str, *, secret: str) -> dict[str, str]:
    now = int(time.time())
    claims = {"sub": actor_id, "role": role, "exp": now + 3600}
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
            "ADMIN_USERNAME": "admin",
        },
        env_unset=["ADMIN_PASSWORD"],
    )


def _store(tmp_path: Path) -> AuthRegistryStore:
    data_dir = tmp_path / "data"
    return AuthRegistryStore(db_path=data_dir / "auth" / "auth_registry.sqlite3", data_dir=data_dir)


def _seed_teacher_student(tmp_path: Path) -> AuthRegistryStore:
    store = _store(tmp_path)
    store._ensure_teacher_auth(
        teacher_id="t_zhang", teacher_name="张老师", email=None, regenerate_token=False
    )
    store._ensure_teacher_auth(
        teacher_id="t_liwei", teacher_name="李老师", email=None, regenerate_token=False
    )
    store._ensure_student_auth(
        student_id="S001", student_name="刘昊然", class_name="高二2403班", regenerate_token=False
    )
    return store


def test_admin_identity_routes_require_admin_and_unique_owner(tmp_path: Path) -> None:
    secret = "identity-admin-secret"
    _seed_teacher_student(tmp_path)
    app_mod = _load_app(tmp_path, secret=secret)
    client = TestClient(app_mod.app)
    admin = _auth_headers("admin", "admin", secret=secret)
    teacher = _auth_headers("t_zhang", "teacher", secret=secret)

    denied = client.post(
        "/auth/admin/roster",
        headers=teacher,
        json={"teacher_id": "t_zhang", "subject_id": "physics", "class_name": "高二2403班"},
    )
    assert denied.status_code == 403

    unauth = client.post(
        "/auth/admin/roster",
        json={"teacher_id": "t_zhang", "subject_id": "physics", "class_name": "高二2403班"},
    )
    assert unauth.status_code == 401

    first = client.post(
        "/auth/admin/roster",
        headers=admin,
        json={"teacher_id": "t_zhang", "subject_id": "physics", "class_name": "高二2403班"},
    )
    assert first.status_code == 200
    assert first.json().get("ok") is True

    conflict = client.post(
        "/auth/admin/roster",
        headers=admin,
        json={"teacher_id": "t_liwei", "subject_id": "physics", "class_name": "高二2403班"},
    )
    assert conflict.status_code == 409
    assert conflict.json().get("detail") == "class_already_owned"

    enroll = client.post(
        "/auth/admin/enrollments/enroll",
        headers=admin,
        json={
            "student_id": "S001",
            "subject_id": "physics",
            "class_name": "高二2403班",
            "teacher_id": "t_zhang",
        },
    )
    assert enroll.status_code == 200
    assert enroll.json().get("ok") is True

    blocked = client.delete(
        "/auth/admin/roster",
        headers=admin,
        params={
            "teacher_id": "t_zhang",
            "subject_id": "physics",
            "class_name": "高二2403班",
        },
    )
    assert blocked.status_code == 409
    assert blocked.json().get("detail") == "enrollments_remain"


def test_teacher_roster_is_self_scoped_not_admin_query(tmp_path: Path) -> None:
    secret = "identity-teacher-roster-secret"
    store = _seed_teacher_student(tmp_path)
    store.add_roster(teacher_id="t_zhang", subject_id="physics", class_name="高二2403班")
    store.add_roster(teacher_id="t_liwei", subject_id="physics", class_name="高二2404班")
    app_mod = _load_app(tmp_path, secret=secret)
    client = TestClient(app_mod.app)
    teacher = _auth_headers("t_zhang", "teacher", secret=secret)
    admin = _auth_headers("admin", "admin", secret=secret)

    mine = client.get("/teacher/roster", headers=teacher)
    assert mine.status_code == 200
    items = mine.json().get("items") or []
    assert {item["teacher_id"] for item in items} == {"t_zhang"}
    assert {item["class_name"] for item in items} == {"高二2403班"}

    idor = client.get("/auth/admin/roster", headers=teacher, params={"teacher_id": "t_liwei"})
    assert idor.status_code == 403

    admin_list = client.get("/auth/admin/roster", headers=admin, params={"teacher_id": "t_liwei"})
    assert admin_list.status_code == 200
    assert {item["teacher_id"] for item in admin_list.json().get("items") or []} == {"t_liwei"}


def test_password_reset_scope_all_admin_only(tmp_path: Path) -> None:
    secret = "identity-reset-all-secret"
    store = _seed_teacher_student(tmp_path)
    store._ensure_student_auth(
        student_id="S002", student_name="畅爽", class_name="高二2403班", regenerate_token=False
    )
    store.add_roster(teacher_id="t_zhang", subject_id="physics", class_name="高二2403班")
    store.enroll_class(teacher_id="t_zhang", subject_id="physics", class_name="高二2403班")
    app_mod = _load_app(tmp_path, secret=secret)
    client = TestClient(app_mod.app)
    teacher = _auth_headers("t_zhang", "teacher", secret=secret)
    admin = _auth_headers("admin", "admin", secret=secret)

    denied = client.post(
        "/auth/teacher/student/reset-passwords",
        headers=teacher,
        json={"scope": "all"},
    )
    assert denied.status_code == 403
    assert denied.json().get("detail") == "forbidden"

    class_reset = client.post(
        "/auth/teacher/student/reset-passwords",
        headers=teacher,
        json={"scope": "class", "class_name": "高二2403班", "new_password": "ClassPwd123"},
    )
    assert class_reset.status_code == 200
    assert {item["student_id"] for item in class_reset.json().get("items") or []} == {"S001", "S002"}

    allowed = client.post(
        "/auth/teacher/student/reset-passwords",
        headers=admin,
        json={"scope": "all"},
    )
    assert allowed.status_code == 200
    assert allowed.json().get("ok") is True

    store._ensure_student_auth(
        student_id="S999", student_name="外人", class_name="高二2404班", regenerate_token=False
    )
    outsider = client.post(
        "/auth/teacher/student/reset-passwords",
        headers=teacher,
        json={"scope": "student", "student_id": "S999"},
    )
    assert outsider.status_code == 403
    assert outsider.json().get("detail") == "forbidden"
    admin_one = client.post(
        "/auth/teacher/student/reset-passwords",
        headers=admin,
        json={"scope": "student", "student_id": "S999", "new_password": "AdminPwd123"},
    )
    assert admin_one.status_code == 200
    assert admin_one.json().get("ok") is True


def test_recompute_roster_overwrites_snapshot(tmp_path: Path) -> None:
    secret = "identity-recompute-secret"
    store = _seed_teacher_student(tmp_path)
    store.add_roster(teacher_id="t_zhang", subject_id="physics", class_name="高二2403班")
    store.enroll(student_id="S001", subject_id="physics", class_name="高二2403班")
    assignment_dir = tmp_path / "data" / "assignments" / "HW-1"
    assignment_dir.mkdir(parents=True)
    (assignment_dir / "meta.json").write_text(
        json.dumps(
            {
                "assignment_id": "HW-1",
                "teacher_id": "t_zhang",
                "subject_id": "physics",
                "scope": "class",
                "class_name": "高二2403班",
                "expected_students": ["OLD"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    app_mod = _load_app(tmp_path, secret=secret)
    client = TestClient(app_mod.app)
    teacher = _auth_headers("t_zhang", "teacher", secret=secret)
    other = _auth_headers("t_liwei", "teacher", secret=secret)

    forbidden = client.post("/assignment/HW-1/recompute-roster", headers=other)
    assert forbidden.status_code == 403

    ok = client.post("/assignment/HW-1/recompute-roster", headers=teacher)
    assert ok.status_code == 200
    payload = ok.json()
    assert payload.get("expected_students") == ["S001"]
    saved = json.loads((assignment_dir / "meta.json").read_text(encoding="utf-8"))
    assert saved.get("expected_students") == ["S001"]
