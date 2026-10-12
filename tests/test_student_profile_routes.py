from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterator

from fastapi.testclient import TestClient

from services.api.assignment.store import connect, ensure, upsert_assignment
from services.api.auth_registry_service import build_auth_registry_store
from services.api.auth_service import AuthPrincipal, reset_current_principal, set_current_principal
from tests.helpers.app_factory import create_test_app


@contextmanager
def _principal(role: str, actor_id: str) -> Iterator[None]:
    token = set_current_principal(AuthPrincipal(actor_id=actor_id, role=role))
    try:
        yield
    finally:
        reset_current_principal(token)


def _load_app(tmp: Path):
    return create_test_app(tmp)


def _stub_profile_get(app_mod: object) -> None:
    core = app_mod.get_core()  # type: ignore[attr-defined]
    core.student_profile_get = lambda student_id: {"student_id": student_id, "ok": True}


def _seed_roster(
    data_dir: Path,
    *,
    teacher_id: str = "t_zhang",
    student_id: str = "S1",
    class_name: str = "1班",
    enroll: bool = True,
):
    store = build_auth_registry_store(data_dir=data_dir)
    store._ensure_teacher_auth(
        teacher_id=teacher_id,
        teacher_name=teacher_id,
        email=None,
        regenerate_token=False,
    )
    store._ensure_student_auth(
        student_id=student_id,
        student_name=student_id,
        class_name=class_name,
        regenerate_token=False,
    )
    roster = store.add_roster(teacher_id=teacher_id, subject_id="physics", class_name=class_name)
    assert roster.get("ok") is True, roster
    if enroll:
        enrolled = store.enroll(
            student_id=student_id,
            subject_id="physics",
            class_name=class_name,
            teacher_id=teacher_id,
        )
        assert enrolled.get("ok") is True, enrolled
    return store


def _upsert_owned_assignment(
    data_dir: Path,
    *,
    teacher_id: str,
    student_id: str,
    assignment_id: str,
    visibility_status: str,
) -> None:
    conn = connect(data_dir)
    try:
        ensure(conn, data_dir=data_dir)
        upsert_assignment(
            conn,
            {
                "assignment_id": assignment_id,
                "teacher_id": teacher_id,
                "subject_id": "physics",
                "pack_id": "physics",
                "visibility_status": visibility_status,
                "scope": "public",
                "expected_students": [student_id],
                "completion_policy": {},
            },
            now_iso="2026-10-12T00:00:00+00:00",
        )
    finally:
        conn.close()


def test_auth_service_does_not_import_assignment_student_list_service() -> None:
    auth_text = Path("services/api/auth_service.py").read_text(encoding="utf-8")
    scope_text = Path("services/api/auth/profile_read_scope_service.py").read_text(encoding="utf-8")
    assert "assignment_student_list_service" not in auth_text
    assert "assignment_student_list_service" not in scope_text


def test_profile_get_requires_principal() -> None:
    with TemporaryDirectory() as td:
        app_mod = _load_app(Path(td))
        _stub_profile_get(app_mod)
        with TestClient(app_mod.app) as client:
            res = client.get("/student/profile/S1")
        assert res.status_code == 400
        assert res.json().get("detail") == "principal_required"


def test_profile_get_missing_bearer_is_401() -> None:
    with TemporaryDirectory() as td:
        app_mod = create_test_app(
            Path(td),
            env_overrides={
                "AUTH_REQUIRED": "1",
                "AUTH_TOKEN_SECRET": "profile-get-secret",
                "APP_ENV": "development",
            },
        )
        with TestClient(app_mod.app) as client:
            res = client.get("/student/profile/S1")
        assert res.status_code == 401
        assert res.json().get("detail") == "missing_authorization"


def test_student_cannot_read_other_profile() -> None:
    with TemporaryDirectory() as td:
        app_mod = _load_app(Path(td))
        _stub_profile_get(app_mod)
        with TestClient(app_mod.app) as client:
            with _principal("student", "S1"):
                res = client.get("/student/profile/S2")
        assert res.status_code == 403
        assert res.json().get("detail") == "forbidden_student_scope"


def test_student_can_read_self() -> None:
    with TemporaryDirectory() as td:
        app_mod = _load_app(Path(td))
        _stub_profile_get(app_mod)
        with TestClient(app_mod.app) as client:
            with _principal("student", "S1"):
                res = client.get("/student/profile/S1")
        assert res.status_code == 200, res.text
        assert res.json().get("student_id") == "S1"


def test_teacher_cannot_read_unrelated_student() -> None:
    with TemporaryDirectory() as td:
        tmp = Path(td)
        app_mod = _load_app(tmp)
        _stub_profile_get(app_mod)
        data_dir = tmp / "data"
        _seed_roster(data_dir, teacher_id="t_zhang", student_id="S1")
        _seed_roster(data_dir, teacher_id="t_other", student_id="S9", class_name="2班")
        with TestClient(app_mod.app) as client:
            with _principal("teacher", "t_other"):
                res = client.get("/student/profile/S1")
        assert res.status_code == 403
        assert res.json().get("detail") == "forbidden_student_scope"


def test_teacher_can_read_enrolled_student() -> None:
    with TemporaryDirectory() as td:
        tmp = Path(td)
        app_mod = _load_app(tmp)
        _stub_profile_get(app_mod)
        _seed_roster(tmp / "data", teacher_id="t_zhang", student_id="S1")
        with TestClient(app_mod.app) as client:
            with _principal("teacher", "t_zhang"):
                res = client.get("/student/profile/S1")
        assert res.status_code == 200, res.text
        assert res.json().get("student_id") == "S1"


def test_teacher_can_read_snapshot_student_after_unenroll() -> None:
    with TemporaryDirectory() as td:
        tmp = Path(td)
        data_dir = tmp / "data"
        app_mod = _load_app(tmp)
        _stub_profile_get(app_mod)
        store = _seed_roster(data_dir, teacher_id="t_zhang", student_id="S1")
        _upsert_owned_assignment(
            data_dir,
            teacher_id="t_zhang",
            student_id="S1",
            assignment_id="HW_SNAP",
            visibility_status="archived",
        )
        unenrolled = store.unenroll(student_id="S1", subject_id="physics", class_name="1班")
        assert unenrolled.get("ok") is True, unenrolled
        with TestClient(app_mod.app) as client:
            with _principal("teacher", "t_zhang"):
                res = client.get("/student/profile/S1")
        assert res.status_code == 200, res.text
        assert res.json().get("student_id") == "S1"


def test_teacher_draft_snapshot_does_not_grant_profile_read() -> None:
    with TemporaryDirectory() as td:
        tmp = Path(td)
        data_dir = tmp / "data"
        app_mod = _load_app(tmp)
        _stub_profile_get(app_mod)
        store = _seed_roster(data_dir, teacher_id="t_zhang", student_id="S1")
        _upsert_owned_assignment(
            data_dir,
            teacher_id="t_zhang",
            student_id="S1",
            assignment_id="HW_DRAFT",
            visibility_status="draft",
        )
        store.unenroll(student_id="S1", subject_id="physics", class_name="1班")
        with TestClient(app_mod.app) as client:
            with _principal("teacher", "t_zhang"):
                res = client.get("/student/profile/S1")
        assert res.status_code == 403
        assert res.json().get("detail") == "forbidden_student_scope"


def test_admin_can_read_any() -> None:
    with TemporaryDirectory() as td:
        app_mod = _load_app(Path(td))
        _stub_profile_get(app_mod)
        with TestClient(app_mod.app) as client:
            with _principal("admin", "admin"):
                res = client.get("/student/profile/S99")
        assert res.status_code == 200, res.text
        assert res.json().get("student_id") == "S99"


def test_teacher_http_update_still_403() -> None:
    with TemporaryDirectory() as td:
        tmp = Path(td)
        app_mod = _load_app(tmp)
        _seed_roster(tmp / "data", teacher_id="t_zhang", student_id="S1")
        with TestClient(app_mod.app) as client:
            with _principal("teacher", "t_zhang"):
                res = client.post(
                    "/student/profile/update",
                    data={"student_id": "S1", "next_focus": "受力分析"},
                )
        assert res.status_code == 403
        assert res.json().get("detail") == "forbidden"
