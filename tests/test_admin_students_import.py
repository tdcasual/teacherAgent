from __future__ import annotations

import hashlib
import io
import os
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from services.api.auth.student_provision_service import allocate_student_id, parse_roster_csv
from services.api.auth_service import mint_test_token
from services.api.core_utils import normalize
from tests.helpers.app_factory import create_test_app

SECRET = "admin-students-import-secret"


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


def _csv_file(text: str, *, name: str = "roster.csv") -> dict[str, tuple[str, bytes, str]]:
    return {"file": (name, text.encode("utf-8"), "text/csv")}


def _expected_student_id(student_name: str, class_name: str) -> str:
    seed = f"{normalize(class_name)}|{normalize(student_name)}"
    return "s_" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]


def _connect_auth(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "data" / "auth" / "auth_registry.sqlite3"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def test_allocate_student_id_stable_hash_and_provided() -> None:
    generated, err = allocate_student_id(student_name="张三", class_name="高二1班", student_id="")
    assert err is None
    assert generated == _expected_student_id("张三", "高二1班")
    provided, err = allocate_student_id(student_name="张三", class_name="高二1班", student_id="S001")
    assert err is None
    assert provided == "S001"
    _, invalid = allocate_student_id(student_name="张三", class_name="高二1班", student_id="../escape")
    assert invalid == "invalid_student_id"


def test_parse_roster_csv_rejects_unknown_column() -> None:
    result = parse_roster_csv("student_name,class_name,email\n张三,高二1班,a@example.com\n")
    assert result.get("ok") is False
    assert result.get("error") == "unknown_column"


def test_import_auth_off_without_bearer_is_401(tmp_path: Path) -> None:
    app_mod = _auth_off_app(tmp_path)
    client = TestClient(app_mod.app)
    res = client.post("/auth/admin/students/import", files=_csv_file("student_name,class_name\n张三,高二1班\n"))
    assert res.status_code == 401
    assert res.json().get("detail") == "missing_authorization"
    assert res.json().get("detail") != "admin_local"


def test_legacy_student_import_is_410(tmp_path: Path) -> None:
    app_mod = _auth_on_app(tmp_path)
    client = TestClient(app_mod.app)
    headers = _admin_headers()
    gone = client.post("/student/import", headers=headers, json={"source": "responses"})
    assert gone.status_code == 410
    assert gone.json().get("detail") == "gone"


def test_import_creates_student_auth_only_and_does_not_enroll(tmp_path: Path) -> None:
    app_mod = _auth_on_app(tmp_path)
    client = TestClient(app_mod.app)
    headers = _admin_headers()
    csv_text = "student_name,class_name\n张三,高二1班\n李四,高二1班\n"
    res = client.post("/auth/admin/students/import", headers=headers, files=_csv_file(csv_text))
    assert res.status_code == 200
    payload = res.json()
    assert payload.get("ok") is True
    assert payload.get("created") == 2
    assert payload.get("updated") == 0
    items = payload.get("items") or []
    assert len(items) == 2
    by_name = {str(item.get("student_name")): item for item in items}
    zhang_id = _expected_student_id("张三", "高二1班")
    li_id = _expected_student_id("李四", "高二1班")
    assert by_name["张三"]["student_id"] == zhang_id
    assert by_name["李四"]["student_id"] == li_id
    zhang_password = str(by_name["张三"].get("temp_password") or "")
    assert zhang_password

    with _connect_auth(tmp_path) as conn:
        auth_count = conn.execute("SELECT COUNT(*) AS n FROM student_auth").fetchone()["n"]
        enroll_count = conn.execute("SELECT COUNT(*) AS n FROM student_enrollments").fetchone()["n"]
    assert auth_count == 2
    assert enroll_count == 0

    login = client.post(
        "/auth/student/login",
        json={"candidate_id": zhang_id, "credential_type": "password", "credential": zhang_password},
    )
    assert login.status_code == 200
    assert login.json().get("ok") is True


def test_import_extra_column_is_400_and_writes_nothing(tmp_path: Path) -> None:
    app_mod = _auth_on_app(tmp_path)
    client = TestClient(app_mod.app)
    headers = _admin_headers()
    csv_text = "student_name,class_name,email\n张三,高二1班,a@example.com\n"
    res = client.post("/auth/admin/students/import", headers=headers, files=_csv_file(csv_text))
    assert res.status_code == 400
    assert res.json().get("detail") == "unknown_column"
    with _connect_auth(tmp_path) as conn:
        assert conn.execute("SELECT COUNT(*) AS n FROM student_auth").fetchone()["n"] == 0


def test_import_is_all_or_nothing_on_bad_row(tmp_path: Path) -> None:
    app_mod = _auth_on_app(tmp_path)
    client = TestClient(app_mod.app)
    headers = _admin_headers()
    csv_text = "student_name,class_name\n张三,高二1班\n,高二1班\n"
    res = client.post("/auth/admin/students/import", headers=headers, files=_csv_file(csv_text))
    assert res.status_code == 400
    assert res.json().get("detail") == "missing_student_name"
    with _connect_auth(tmp_path) as conn:
        assert conn.execute("SELECT COUNT(*) AS n FROM student_auth").fetchone()["n"] == 0


def test_reimport_does_not_rotate_password_unless_flagged(tmp_path: Path) -> None:
    app_mod = _auth_on_app(tmp_path)
    client = TestClient(app_mod.app)
    headers = _admin_headers()
    csv_text = "student_name,class_name,student_id\n张三,高二1班,S001\n"
    first = client.post("/auth/admin/students/import", headers=headers, files=_csv_file(csv_text))
    assert first.status_code == 200
    original = str((first.json().get("items") or [{}])[0].get("temp_password") or "")
    assert original

    again = client.post("/auth/admin/students/import", headers=headers, files=_csv_file(csv_text))
    assert again.status_code == 200
    assert again.json().get("updated") == 1
    assert again.json().get("created") == 0
    again_item = (again.json().get("items") or [{}])[0]
    assert not str(again_item.get("temp_password") or "")

    still_works = client.post(
        "/auth/student/login",
        json={"candidate_id": "S001", "credential_type": "password", "credential": original},
    )
    assert still_works.json().get("ok") is True

    reset = client.post(
        "/auth/admin/students/import",
        headers=headers,
        files=_csv_file(csv_text),
        data={"reset_passwords": "true"},
    )
    assert reset.status_code == 200
    new_password = str((reset.json().get("items") or [{}])[0].get("temp_password") or "")
    assert new_password
    assert new_password != original
    old_denied = client.post(
        "/auth/student/login",
        json={"candidate_id": "S001", "credential_type": "password", "credential": original},
    )
    assert old_denied.json().get("ok") is not True
    new_ok = client.post(
        "/auth/student/login",
        json={"candidate_id": "S001", "credential_type": "password", "credential": new_password},
    )
    assert new_ok.json().get("ok") is True


def test_same_class_name_without_ids_merges(tmp_path: Path) -> None:
    app_mod = _auth_on_app(tmp_path)
    client = TestClient(app_mod.app)
    headers = _admin_headers()
    csv_text = "student_name,class_name\n张三,高二1班\n张三,高二1班\n"
    res = client.post("/auth/admin/students/import", headers=headers, files=_csv_file(csv_text))
    assert res.status_code == 200
    assert res.json().get("created") == 1
    with _connect_auth(tmp_path) as conn:
        assert conn.execute("SELECT COUNT(*) AS n FROM student_auth").fetchone()["n"] == 1


def test_import_accepts_utf8_bom(tmp_path: Path) -> None:
    app_mod = _auth_on_app(tmp_path)
    client = TestClient(app_mod.app)
    headers = _admin_headers()
    raw = "\ufeffstudent_name,class_name\n张三,高二1班\n".encode("utf-8-sig")
    res = client.post(
        "/auth/admin/students/import",
        headers=headers,
        files={"file": ("roster.csv", io.BytesIO(raw), "text/csv")},
    )
    assert res.status_code == 200
    assert res.json().get("created") == 1


def test_import_then_enroll_class_is_separate(tmp_path: Path) -> None:
    app_mod = _auth_on_app(tmp_path)
    client = TestClient(app_mod.app)
    headers = _admin_headers()
    created = client.post(
        "/auth/admin/teacher/create",
        headers=headers,
        json={"teacher_name": "张老师", "teacher_id": "t_zhang01"},
    )
    assert created.status_code == 201
    imported = client.post(
        "/auth/admin/students/import",
        headers=headers,
        files=_csv_file("student_name,class_name\n张三,高二1班\n"),
    )
    assert imported.status_code == 200
    with _connect_auth(tmp_path) as conn:
        assert conn.execute("SELECT COUNT(*) AS n FROM student_enrollments").fetchone()["n"] == 0

    roster = client.post(
        "/auth/admin/roster",
        headers=headers,
        json={"teacher_id": "t_zhang01", "subject_id": "physics", "class_name": "高二1班"},
    )
    assert roster.status_code == 200
    enroll = client.post(
        "/auth/admin/enrollments/enroll-class",
        headers=headers,
        json={"teacher_id": "t_zhang01", "subject_id": "physics", "class_name": "高二1班"},
    )
    assert enroll.status_code == 200
    assert enroll.json().get("ok") is True
    with _connect_auth(tmp_path) as conn:
        assert conn.execute("SELECT COUNT(*) AS n FROM student_enrollments").fetchone()["n"] == 1
