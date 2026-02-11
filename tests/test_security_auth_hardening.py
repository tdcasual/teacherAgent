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

from fastapi.testclient import TestClient

from services.api.auth_service import mint_test_token


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


if __name__ == "__main__":
    unittest.main()
