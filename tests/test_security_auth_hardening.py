from __future__ import annotations

import importlib
import json
import os
import socket
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from fastapi.testclient import TestClient

from services.api.auth_service import mint_test_token, validate_auth_secret_policy


def _auth_headers(actor_id: str, role: str, *, secret: str, tenant_id: str = ""):
    now = int(time.time())
    claims = {
        "sub": actor_id,
        "role": role,
        "exp": now + 3600,
    }
    if tenant_id:
        claims["tenant_id"] = tenant_id
    token = mint_test_token(claims, secret=secret)
    return {"Authorization": f"Bearer {token}"}


def load_app(tmp_dir: Path, *, secret: str = "test-secret"):
    os.environ["DATA_DIR"] = str(tmp_dir / "data")
    os.environ["UPLOADS_DIR"] = str(tmp_dir / "uploads")
    os.environ["DIAG_LOG"] = "0"
    os.environ["MASTER_KEY_DEV_DEFAULT"] = "dev-key"
    os.environ["AUTH_REQUIRED"] = "1"
    os.environ["AUTH_TOKEN_SECRET"] = secret
    import services.api.app as app_mod

    importlib.reload(app_mod)
    return app_mod


def test_auth_required_true_without_secret_raises_startup_error(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_REQUIRED", "1")
    monkeypatch.delenv("AUTH_TOKEN_SECRET", raising=False)
    monkeypatch.setenv("APP_ENV", "production")

    with pytest.raises(RuntimeError, match="AUTH_TOKEN_SECRET"):
        validate_auth_secret_policy()


class _ProbeHandler(BaseHTTPRequestHandler):
    hits = []

    def do_GET(self):  # noqa: N802
        _ProbeHandler.hits.append(self.path)
        body = json.dumps({"data": [{"id": "mock-model"}]}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):  # noqa: A003
        return


class SecurityAuthHardeningTest(unittest.TestCase):
    SECRET = "hardening-secret"
    _ENV_KEYS = [
        "DATA_DIR",
        "UPLOADS_DIR",
        "DIAG_LOG",
        "MASTER_KEY_DEV_DEFAULT",
        "AUTH_REQUIRED",
        "AUTH_TOKEN_SECRET",
        "TENANT_ADMIN_KEY",
        "TENANT_DB_PATH",
    ]

    def setUp(self):
        self._env_backup = {key: os.environ.get(key) for key in self._ENV_KEYS}

    def tearDown(self):
        for key, value in self._env_backup.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_teacher_provider_registry_forbids_cross_teacher_access(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td), secret=self.SECRET)
            client = TestClient(app_mod.app)

            attacker_headers = _auth_headers("teacher_attacker", "teacher", secret=self.SECRET)
            res = client.post(
                "/teacher/provider-registry/providers",
                headers=attacker_headers,
                json={
                    "teacher_id": "teacher_victim",
                    "provider_id": "tprv_x",
                    "display_name": "X",
                    "base_url": "https://proxy.example.com/v1",
                    "api_key": "sk-abc-123456",
                    "default_model": "gpt-4.1-mini",
                    "enabled": True,
                },
            )
            self.assertEqual(res.status_code, 403)

    def test_chat_status_enforces_job_owner(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td), secret=self.SECRET)
            client = TestClient(app_mod.app)

            teacher_a = _auth_headers("teacher_a", "teacher", secret=self.SECRET)
            teacher_b = _auth_headers("teacher_b", "teacher", secret=self.SECRET)

            start = client.post(
                "/chat/start",
                headers=teacher_a,
                json={
                    "request_id": "sec-req-001",
                    "role": "teacher",
                    "teacher_id": "teacher_a",
                    "messages": [{"role": "user", "content": "hello"}],
                },
            )
            self.assertEqual(start.status_code, 200)
            job_id = start.json().get("job_id")
            self.assertTrue(job_id)

            denied = client.get("/chat/status", headers=teacher_b, params={"job_id": job_id})
            self.assertEqual(denied.status_code, 403)

    def test_tenant_dispatcher_requires_matching_tenant_claim(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            os.environ["TENANT_ADMIN_KEY"] = "k"
            os.environ["TENANT_DB_PATH"] = str(tmp / "tenants.sqlite3")
            app_mod = load_app(tmp, secret=self.SECRET)
            client = TestClient(app_mod.app)

            upsert = client.put(
                "/admin/tenants/t1",
                headers={"X-Admin-Key": "k"},
                json={"data_dir": str(tmp / "t1_data"), "uploads_dir": str(tmp / "t1_up")},
            )
            self.assertEqual(upsert.status_code, 200)

            bad_headers = _auth_headers("teacher_a", "teacher", secret=self.SECRET, tenant_id="t2")
            denied = client.get("/t/t1/health", headers=bad_headers)
            self.assertEqual(denied.status_code, 403)

    def test_probe_models_blocks_private_loopback_target(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td), secret=self.SECRET)
            client = TestClient(app_mod.app)
            teacher_headers = _auth_headers("teacher_safe", "teacher", secret=self.SECRET)

            with socket.socket() as s:
                s.bind(("127.0.0.1", 0))
                _, port = s.getsockname()

            server = HTTPServer(("127.0.0.1", port), _ProbeHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            _ProbeHandler.hits = []
            try:
                create = client.post(
                    "/teacher/provider-registry/providers",
                    headers=teacher_headers,
                    json={
                        "provider_id": "tprv_loop",
                        "display_name": "loop",
                        "base_url": f"http://127.0.0.1:{port}",
                        "api_key": "sk-loop-123456",
                        "default_model": "mock-model",
                        "enabled": True,
                    },
                )
                self.assertEqual(create.status_code, 200)

                probe = client.post(
                    "/teacher/provider-registry/providers/tprv_loop/probe-models",
                    headers=teacher_headers,
                    json={},
                )
                self.assertEqual(probe.status_code, 400)
                detail = probe.json().get("detail") or {}
                self.assertEqual(detail.get("error"), "unsafe_probe_target")
                self.assertEqual(_ProbeHandler.hits, [])
            finally:
                server.shutdown()
                server.server_close()

    def test_student_history_forbids_cross_student_access(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td), secret=self.SECRET)
            client = TestClient(app_mod.app)
            student_headers = _auth_headers("student_a", "student", secret=self.SECRET)

            denied = client.get(
                "/student/history/sessions",
                headers=student_headers,
                params={"student_id": "student_b"},
            )
            self.assertEqual(denied.status_code, 403)
            self.assertEqual(denied.json().get("detail"), "forbidden_student_scope")

    def test_student_profile_update_forbids_cross_student_access(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td), secret=self.SECRET)
            client = TestClient(app_mod.app)
            student_headers = _auth_headers("student_a", "student", secret=self.SECRET)

            denied = client.post(
                "/student/profile/update",
                headers=student_headers,
                data={"student_id": "student_b", "next_focus": "kinematics"},
            )
            self.assertEqual(denied.status_code, 403)
            self.assertEqual(denied.json().get("detail"), "forbidden_student_scope")

    def test_student_submit_forbids_cross_student_access(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td), secret=self.SECRET)
            client = TestClient(app_mod.app)
            student_headers = _auth_headers("student_a", "student", secret=self.SECRET)

            denied = client.post(
                "/student/submit",
                headers=student_headers,
                data={"student_id": "student_b", "auto_assignment": "false"},
                files={"files": ("answer.txt", b"hello", "text/plain")},
            )
            self.assertEqual(denied.status_code, 403)
            self.assertEqual(denied.json().get("detail"), "forbidden_student_scope")

    def test_assignment_download_enforces_student_scope(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            assignment_dir = root / "data" / "assignments" / "HW_SEC_1"
            source_dir = assignment_dir / "source"
            source_dir.mkdir(parents=True, exist_ok=True)
            (source_dir / "paper.txt").write_text("secret paper", encoding="utf-8")
            (assignment_dir / "meta.json").write_text(
                json.dumps(
                    {
                        "assignment_id": "HW_SEC_1",
                        "scope": "student",
                        "student_ids": ["student_b"],
                        "source_files": ["paper.txt"],
                        "delivery_mode": "txt",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            app_mod = load_app(root, secret=self.SECRET)
            client = TestClient(app_mod.app)
            attacker_headers = _auth_headers("student_a", "student", secret=self.SECRET)

            denied = client.get(
                "/assignment/HW_SEC_1/download",
                headers=attacker_headers,
                params={"file": "paper.txt"},
            )
            self.assertEqual(denied.status_code, 403)
            self.assertEqual(denied.json().get("detail"), "forbidden_assignment_scope")

    def test_assignment_detail_enforces_student_scope(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            assignment_dir = root / "data" / "assignments" / "HW_SEC_2"
            assignment_dir.mkdir(parents=True, exist_ok=True)
            (assignment_dir / "meta.json").write_text(
                json.dumps(
                    {
                        "assignment_id": "HW_SEC_2",
                        "scope": "student",
                        "student_ids": ["student_b"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            app_mod = load_app(root, secret=self.SECRET)
            client = TestClient(app_mod.app)
            attacker_headers = _auth_headers("student_a", "student", secret=self.SECRET)

            denied = client.get("/assignment/HW_SEC_2", headers=attacker_headers)
            self.assertEqual(denied.status_code, 403)
            self.assertEqual(denied.json().get("detail"), "forbidden_assignment_scope")

    def test_student_import_forbids_student_role(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            staging = root / "data" / "staging"
            staging.mkdir(parents=True, exist_ok=True)
            (staging / "responses.csv").write_text(
                "student_id,student_name,class_name,exam_id\nS1,Alice,C1,EX1\n",
                encoding="utf-8",
            )

            app_mod = load_app(root, secret=self.SECRET)
            client = TestClient(app_mod.app)
            student_headers = _auth_headers("student_a", "student", secret=self.SECRET)

            denied = client.post(
                "/student/import",
                headers=student_headers,
                json={"source": "responses"},
            )
            self.assertEqual(denied.status_code, 403)
            self.assertEqual(denied.json().get("detail"), "forbidden")

    def test_student_import_rejects_outside_file_path(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            outside = root / "outside.csv"
            outside.write_text(
                "student_id,student_name,class_name,exam_id\nS1,Alice,C1,EX1\n",
                encoding="utf-8",
            )

            app_mod = load_app(root, secret=self.SECRET)
            client = TestClient(app_mod.app)
            teacher_headers = _auth_headers("teacher_a", "teacher", secret=self.SECRET)

            blocked = client.post(
                "/student/import",
                headers=teacher_headers,
                json={"source": "responses", "file_path": str(outside)},
            )
            self.assertEqual(blocked.status_code, 400)
            self.assertEqual(blocked.json().get("detail"), "responses file not found")

    def test_teacher_skills_routes_forbid_student_role(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td), secret=self.SECRET)
            client = TestClient(app_mod.app)
            student_headers = _auth_headers("student_a", "student", secret=self.SECRET)

            denied_preview = client.post(
                "/teacher/skills/preview",
                headers=student_headers,
                json={"github_url": "https://github.com/example/repo"},
            )
            self.assertEqual(denied_preview.status_code, 403)
            self.assertEqual(denied_preview.json().get("detail"), "forbidden")

            denied_create = client.post(
                "/teacher/skills",
                headers=student_headers,
                json={
                    "title": "Blocked Skill",
                    "description": "Should be denied for student role",
                    "keywords": [],
                    "examples": [],
                    "allowed_roles": ["teacher"],
                },
            )
            self.assertEqual(denied_create.status_code, 403)
            self.assertEqual(denied_create.json().get("detail"), "forbidden")

    def test_assignment_exam_teacher_routes_forbid_student_role(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td), secret=self.SECRET)
            client = TestClient(app_mod.app)
            student_headers = _auth_headers("student_a", "student", secret=self.SECRET)

            denied_assignments = client.get("/assignments", headers=student_headers)
            self.assertEqual(denied_assignments.status_code, 403)
            self.assertEqual(denied_assignments.json().get("detail"), "forbidden")

            denied_exams = client.get("/exams", headers=student_headers)
            self.assertEqual(denied_exams.status_code, 403)
            self.assertEqual(denied_exams.json().get("detail"), "forbidden")

    def test_assignment_today_enforces_student_scope(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td), secret=self.SECRET)
            client = TestClient(app_mod.app)

            teacher_headers = _auth_headers("teacher_a", "teacher", secret=self.SECRET)
            denied_teacher = client.get(
                "/assignment/today",
                headers=teacher_headers,
                params={"student_id": "student_a"},
            )
            self.assertEqual(denied_teacher.status_code, 403)
            self.assertEqual(denied_teacher.json().get("detail"), "forbidden")

            student_headers = _auth_headers("student_a", "student", secret=self.SECRET)
            denied_cross_student = client.get(
                "/assignment/today",
                headers=student_headers,
                params={"student_id": "student_b"},
            )
            self.assertEqual(denied_cross_student.status_code, 403)
            self.assertEqual(denied_cross_student.json().get("detail"), "forbidden_student_scope")

    def test_assignment_upload_job_owner_binding_blocks_cross_teacher_access(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td), secret=self.SECRET)
            client = TestClient(app_mod.app)

            teacher_a = _auth_headers("teacher_a", "teacher", secret=self.SECRET)
            teacher_b = _auth_headers("teacher_b", "teacher", secret=self.SECRET)

            start = client.post(
                "/assignment/upload/start",
                headers=teacher_a,
                data={"assignment_id": "HW_SEC_1"},
                files=[("files", ("paper.txt", b"q1", "text/plain"))],
            )
            self.assertEqual(start.status_code, 200)
            job_id = str(start.json().get("job_id") or "")
            self.assertTrue(job_id)

            denied_status = client.get(
                "/assignment/upload/status",
                headers=teacher_b,
                params={"job_id": job_id},
            )
            self.assertEqual(denied_status.status_code, 403)
            self.assertEqual(denied_status.json().get("detail"), "forbidden_upload_job")

            denied_confirm = client.post(
                "/assignment/upload/confirm",
                headers=teacher_b,
                json={"job_id": job_id},
            )
            self.assertEqual(denied_confirm.status_code, 403)
            self.assertEqual(denied_confirm.json().get("detail"), "forbidden_upload_job")

    def test_exam_upload_job_owner_binding_blocks_cross_teacher_access(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td), secret=self.SECRET)
            client = TestClient(app_mod.app)

            teacher_a = _auth_headers("teacher_a", "teacher", secret=self.SECRET)
            teacher_b = _auth_headers("teacher_b", "teacher", secret=self.SECRET)

            start = client.post(
                "/exam/upload/start",
                headers=teacher_a,
                data={"exam_id": "EX_SEC_1"},
                files=[
                    ("paper_files", ("paper.txt", b"paper", "text/plain")),
                    ("score_files", ("scores.csv", b"student,score\nA,90\n", "text/csv")),
                ],
            )
            self.assertEqual(start.status_code, 200)
            job_id = str(start.json().get("job_id") or "")
            self.assertTrue(job_id)

            denied_status = client.get(
                "/exam/upload/status",
                headers=teacher_b,
                params={"job_id": job_id},
            )
            self.assertEqual(denied_status.status_code, 403)
            self.assertEqual(denied_status.json().get("detail"), "forbidden_upload_job")

            denied_confirm = client.post(
                "/exam/upload/confirm",
                headers=teacher_b,
                json={"job_id": job_id},
            )
            self.assertEqual(denied_confirm.status_code, 403)
            self.assertEqual(denied_confirm.json().get("detail"), "forbidden_upload_job")


if __name__ == "__main__":
    unittest.main()
