from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from services.api.auth_service import AuthPrincipal, reset_current_principal, set_current_principal
from services.api.routes.student_practice_routes import register_student_practice_routes
from tests.test_student_practice_service import _write_assignment, _write_bank, _write_homework


def _core(root: Path) -> SimpleNamespace:
    async def save_upload_file(upload, dest: Path) -> int:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"x")
        return 1

    return SimpleNamespace(
        DATA_DIR=root,
        APP_ROOT=root,
        STUDENT_SUBMISSIONS_DIR=root / "student_submissions",
        UPLOADS_DIR=root / "uploads",
        GRADE_COUNT_CONF_THRESHOLD=0.6,
        run_script=lambda _args: "ok",
        diag_log=lambda _event, _payload: None,
        sanitize_filename=lambda name: Path(str(name or "")).name,
        save_upload_file=save_upload_file,
        resolve_assignment_dir=lambda aid: root / "assignments" / aid,
        load_assignment_meta=lambda folder: json.loads((Path(folder) / "meta.json").read_text(encoding="utf-8")),
    )


def _client(root: Path) -> TestClient:
    app = FastAPI()
    router = APIRouter()
    register_student_practice_routes(router, _core(root))
    app.include_router(router)
    return TestClient(app)


def test_practice_recommend_ignores_foreign_student_id_and_uses_principal(monkeypatch) -> None:
    monkeypatch.setattr(
        "services.api.routes.student_practice_routes.authorize_student_submit_assignment",
        lambda *_a, **_k: None,
    )
    with TemporaryDirectory() as td:
        root = Path(td)
        _write_assignment(root, "HW_1")
        _write_homework(root, "HW_1", "S1")
        _write_bank(root)
        client = _client(root)

        missing = client.post("/student/assignment/HW_1/practice")
        assert missing.status_code == 400
        assert missing.json()["detail"] == "principal_required"

        token = set_current_principal(AuthPrincipal(actor_id="S1", role="student"))
        try:
            res = client.post("/student/assignment/HW_1/practice?student_id=S2")
        finally:
            reset_current_principal(token)
        assert res.status_code == 200, res.text
        payload = res.json()
        assert payload["ok"] is True
        practice_id = payload["practice_id"]
        assert practice_id.startswith("practice_")
        assert (root / "student_submissions" / "HW_1" / "S1" / practice_id).is_dir()
        assert not (root / "student_submissions" / "HW_1" / "S2").exists()
        for question in payload.get("questions") or []:
            assert "answer_ref" not in question
            assert "answer_text" not in question


def test_practice_list_requires_principal_and_ignores_foreign_student_id(monkeypatch) -> None:
    monkeypatch.setattr(
        "services.api.routes.student_practice_routes.authorize_student_submit_assignment",
        lambda *_a, **_k: None,
    )
    with TemporaryDirectory() as td:
        root = Path(td)
        _write_assignment(root, "HW_1")
        _write_homework(root, "HW_1", "S1")
        _write_bank(root)
        client = _client(root)

        missing = client.get("/student/assignment/HW_1/practice")
        assert missing.status_code == 400
        assert missing.json()["detail"] == "principal_required"

        token = set_current_principal(AuthPrincipal(actor_id="S1", role="student"))
        try:
            client.post("/student/assignment/HW_1/practice")
            res = client.get("/student/assignment/HW_1/practice?student_id=S2")
        finally:
            reset_current_principal(token)
        assert res.status_code == 200, res.text
        payload = res.json()
        assert payload["ok"] is True
        assert payload["practices"]
        for practice in payload["practices"]:
            for question in practice.get("questions") or []:
                assert "answer_ref" not in question
                assert "answer_text" not in question
                assert "expected" not in question


def test_practice_submit_rejects_invalid_practice_id(monkeypatch) -> None:
    monkeypatch.setattr(
        "services.api.routes.student_practice_routes.authorize_student_submit_assignment",
        lambda *_a, **_k: None,
    )
    with TemporaryDirectory() as td:
        root = Path(td)
        _write_assignment(root, "HW_1")
        _write_homework(root, "HW_1", "S1")
        client = _client(root)
        token = set_current_principal(AuthPrincipal(actor_id="S1", role="student"))
        files = {"files": ("a.pdf", b"x", "application/pdf")}
        try:
            dotted = client.post(
                "/student/assignment/HW_1/practice/%2e%2e/submit",
                files=files,
            )
            missing = client.post(
                "/student/assignment/HW_1/practice/not_practice/submit",
                files=files,
            )
        finally:
            reset_current_principal(token)
        assert dotted.status_code in {400, 404}
        if dotted.status_code == 400:
            assert dotted.json()["detail"] == "invalid_practice_id"
        assert missing.status_code == 404
