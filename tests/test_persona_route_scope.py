from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Dict
from unittest.mock import patch

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from services.api.routes.student_persona_routes import register_student_persona_routes
from services.api.routes.teacher_persona_routes import register_teacher_persona_routes


class _StudentPersonaCoreStub:
    def __init__(self) -> None:
        self.captured_get_student_id = ""
        self.captured_activate_student_id = ""
        self.avatar_upload_calls = 0

    def _student_persona_api_deps(self) -> object:
        return object()

    def _student_personas_get_api_impl(self, student_id: str, *, deps: Any) -> Dict[str, Any]:
        self.captured_get_student_id = student_id
        return {
            "ok": True,
            "student_id": student_id,
            "assigned": [],
            "custom": [],
            "active_persona_id": "",
        }

    def _student_persona_custom_create_api_impl(
        self, student_id: str, payload: Dict[str, Any], *, deps: Any
    ) -> Dict[str, Any]:
        return {"ok": True, "student_id": student_id, "persona": payload}

    def _student_persona_custom_update_api_impl(
        self, student_id: str, persona_id: str, payload: Dict[str, Any], *, deps: Any
    ) -> Dict[str, Any]:
        return {"ok": True, "student_id": student_id, "persona": {"persona_id": persona_id, **payload}}

    def _student_persona_activate_api_impl(
        self, student_id: str, persona_id: str, *, deps: Any
    ) -> Dict[str, Any]:
        self.captured_activate_student_id = student_id
        return {"ok": True, "student_id": student_id, "active_persona_id": persona_id}

    def _student_persona_custom_delete_api_impl(
        self, student_id: str, persona_id: str, *, deps: Any
    ) -> Dict[str, Any]:
        return {"ok": True, "student_id": student_id, "removed": True, "active_persona_id": ""}

    def _student_persona_avatar_upload_api_impl(
        self,
        student_id: str,
        persona_id: str,
        *,
        filename: str,
        content: bytes,
        deps: Any,
    ) -> Dict[str, Any]:
        self.avatar_upload_calls += 1
        return {"ok": True, "student_id": student_id, "persona_id": persona_id, "avatar_url": filename}

    def _resolve_student_persona_avatar_path_impl(
        self, student_id: str, persona_id: str, file_name: str, *, deps: Any
    ) -> Path | None:
        return None


class _TeacherPersonaCoreStub:
    def __init__(self, avatar_path: Path) -> None:
        self.avatar_path = avatar_path
        self.resolve_teacher_id_arg: Any = None
        self.captured_get_teacher_id = ""
        self.captured_avatar_teacher_id = ""
        self.avatar_upload_calls = 0

    def _teacher_persona_api_deps(self) -> object:
        return object()

    def resolve_teacher_id(self, teacher_id: Any = None) -> str:
        self.resolve_teacher_id_arg = teacher_id
        value = str(teacher_id or "").strip()
        return value or "teacher_default"

    def _teacher_personas_get_api_impl(self, teacher_id: str, *, deps: Any) -> Dict[str, Any]:
        self.captured_get_teacher_id = teacher_id
        if teacher_id != "teacher_default":
            return {"ok": False, "error": "missing_teacher_id"}
        return {"ok": True, "teacher_id": teacher_id, "personas": []}

    def _teacher_persona_create_api_impl(
        self, teacher_id: str, payload: Dict[str, Any], *, deps: Any
    ) -> Dict[str, Any]:
        return {"ok": True, "teacher_id": teacher_id, "persona": payload}

    def _teacher_persona_update_api_impl(
        self, teacher_id: str, persona_id: str, payload: Dict[str, Any], *, deps: Any
    ) -> Dict[str, Any]:
        return {"ok": True, "teacher_id": teacher_id, "persona": {"persona_id": persona_id, **payload}}

    def _teacher_persona_assign_api_impl(
        self, teacher_id: str, persona_id: str, payload: Dict[str, Any], *, deps: Any
    ) -> Dict[str, Any]:
        return {
            "ok": True,
            "teacher_id": teacher_id,
            "persona_id": persona_id,
            "student_id": str(payload.get("student_id") or ""),
            "status": str(payload.get("status") or "active"),
        }

    def _teacher_persona_visibility_api_impl(
        self, teacher_id: str, persona_id: str, payload: Dict[str, Any], *, deps: Any
    ) -> Dict[str, Any]:
        return {"ok": True, "teacher_id": teacher_id, "persona": {"persona_id": persona_id, **payload}}

    def _teacher_persona_avatar_upload_api_impl(
        self,
        teacher_id: str,
        persona_id: str,
        *,
        filename: str,
        content: bytes,
        deps: Any,
    ) -> Dict[str, Any]:
        self.avatar_upload_calls += 1
        return {"ok": True, "teacher_id": teacher_id, "persona_id": persona_id, "avatar_url": filename}

    def _resolve_teacher_persona_avatar_path_impl(
        self, teacher_id: str, persona_id: str, file_name: str, *, deps: Any
    ) -> Path | None:
        self.captured_avatar_teacher_id = teacher_id
        if teacher_id != "scoped_teacher":
            return None
        return self.avatar_path


def _build_student_persona_client(core: _StudentPersonaCoreStub) -> TestClient:
    app = FastAPI()
    router = APIRouter()
    register_student_persona_routes(router, core)
    app.include_router(router)
    return TestClient(app)


def _build_teacher_persona_client(core: _TeacherPersonaCoreStub) -> TestClient:
    app = FastAPI()
    router = APIRouter()
    register_teacher_persona_routes(router, core)
    app.include_router(router)
    return TestClient(app)


def test_teacher_persona_get_uses_resolved_teacher_id_when_missing_query_param() -> None:
    with TemporaryDirectory() as td:
        avatar_path = Path(td) / "avatar.png"
        avatar_path.write_bytes(b"avatar")
        core = _TeacherPersonaCoreStub(avatar_path)
        client = _build_teacher_persona_client(core)

        response = client.get("/teacher/personas")

        assert response.status_code == 200
        assert response.json()["teacher_id"] == "teacher_default"
        assert core.captured_get_teacher_id == "teacher_default"


def test_student_persona_get_binds_student_scope_before_service_call() -> None:
    core = _StudentPersonaCoreStub()
    client = _build_student_persona_client(core)

    with patch(
        "services.api.routes.student_persona_routes.resolve_student_scope",
        return_value="scoped_student",
        create=True,
    ):
        response = client.get("/student/personas", params={"student_id": "raw_student"})

    assert response.status_code == 200
    assert response.json()["student_id"] == "scoped_student"
    assert core.captured_get_student_id == "scoped_student"


def test_student_persona_activate_binds_student_scope_before_service_call() -> None:
    core = _StudentPersonaCoreStub()
    client = _build_student_persona_client(core)

    with patch(
        "services.api.routes.student_persona_routes.resolve_student_scope",
        return_value="scoped_student",
        create=True,
    ):
        response = client.post(
            "/student/personas/activate",
            json={"student_id": "raw_student", "persona_id": "preset_1"},
        )

    assert response.status_code == 200
    assert response.json()["student_id"] == "scoped_student"
    assert core.captured_activate_student_id == "scoped_student"


def test_teacher_persona_avatar_get_binds_teacher_scope() -> None:
    with TemporaryDirectory() as td:
        avatar_path = Path(td) / "avatar.png"
        avatar_path.write_bytes(b"avatar")
        core = _TeacherPersonaCoreStub(avatar_path)
        client = _build_teacher_persona_client(core)

        with patch(
            "services.api.routes.teacher_persona_routes.scoped_teacher_id",
            return_value="scoped_teacher",
        ):
            response = client.get("/teacher/personas/avatar/raw_teacher/pid/avatar.png")

        assert response.status_code == 200
        assert core.captured_avatar_teacher_id == "scoped_teacher"


def test_student_persona_avatar_upload_rejects_oversized_file_before_service_call() -> None:
    core = _StudentPersonaCoreStub()
    client = _build_student_persona_client(core)
    payload = b"x" * (2 * 1024 * 1024 + 1)

    response = client.post(
        "/student/personas/avatar/upload",
        data={"student_id": "S001", "persona_id": "custom_1"},
        files={"file": ("avatar.png", payload, "image/png")},
    )

    assert response.status_code == 400
    assert response.json().get("detail", {}).get("error") == "avatar_too_large"
    assert core.avatar_upload_calls == 0


def test_teacher_persona_avatar_upload_rejects_oversized_file_before_service_call() -> None:
    with TemporaryDirectory() as td:
        avatar_path = Path(td) / "avatar.png"
        avatar_path.write_bytes(b"avatar")
        core = _TeacherPersonaCoreStub(avatar_path)
        client = _build_teacher_persona_client(core)
        payload = b"x" * (2 * 1024 * 1024 + 1)

        response = client.post(
            "/teacher/personas/pid/avatar/upload",
            data={"teacher_id": "T001"},
            files={"file": ("avatar.png", payload, "image/png")},
        )

        assert response.status_code == 400
        assert response.json().get("detail", {}).get("error") == "avatar_too_large"
        assert core.avatar_upload_calls == 0
