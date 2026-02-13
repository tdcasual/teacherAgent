import importlib
import json
import os
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Dict, Optional

from fastapi.testclient import TestClient
from services.api.auth_service import mint_test_token


def load_app(
    tmp_dir: Path,
    *,
    auth_required: Optional[str] = None,
    auth_secret: Optional[str] = None,
):
    os.environ["DATA_DIR"] = str(tmp_dir / "data")
    os.environ["UPLOADS_DIR"] = str(tmp_dir / "uploads")
    os.environ["DIAG_LOG"] = "0"
    if auth_required is None:
        os.environ.pop("AUTH_REQUIRED", None)
    else:
        os.environ["AUTH_REQUIRED"] = auth_required
    if auth_secret is None:
        os.environ.pop("AUTH_TOKEN_SECRET", None)
    else:
        os.environ["AUTH_TOKEN_SECRET"] = auth_secret
    import services.api.app as app_mod

    importlib.reload(app_mod)
    return app_mod


def _auth_headers(*, actor_id: str, role: str, secret: str) -> Dict[str, str]:
    now = int(time.time())
    token = mint_test_token(
        {"sub": actor_id, "role": role, "exp": now + 3600},
        secret=secret,
    )
    return {"Authorization": f"Bearer {token}"}


class ChartExecToolTest(unittest.TestCase):
    def test_chart_exec_dispatch_uses_chart_api_service_deps(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            sentinel = object()
            captured = {}

            def fake_impl(args, *, deps):  # type: ignore[no-untyped-def]
                captured["args"] = dict(args)
                captured["deps"] = deps
                return {"ok": True}

            app_mod._chart_exec_api_impl = fake_impl  # type: ignore[attr-defined]
            app_mod._chart_api_deps = lambda: sentinel  # type: ignore[attr-defined]

            res = app_mod.tool_dispatch("chart.exec", {"python_code": "print('hi')"}, role="teacher")
            self.assertTrue(res.get("ok"))
            self.assertEqual((captured.get("args") or {}).get("python_code"), "print('hi')")
            self.assertIs(captured.get("deps"), sentinel)

    def test_chart_exec_dispatch_calls_executor_for_teacher(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            called = {}

            def fake_execute(args, app_root, uploads_dir):  # type: ignore[no-untyped-def]
                called["args"] = args
                called["app_root"] = app_root
                called["uploads_dir"] = uploads_dir
                return {"ok": True, "run_id": "chr_test", "image_url": "/charts/chr_test/main.png"}

            app_mod.execute_chart_exec = fake_execute  # type: ignore[attr-defined]
            res = app_mod.tool_dispatch("chart.exec", {"python_code": "print('hi')"}, role="teacher")
            self.assertTrue(res.get("ok"))
            self.assertEqual(called.get("args", {}).get("python_code"), "print('hi')")
            self.assertTrue(str(called.get("uploads_dir", "")).endswith("uploads"))

    def test_chart_image_endpoint_serves_saved_file(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            app_mod = load_app(tmp)
            client = TestClient(app_mod.app)

            chart_path = tmp / "uploads" / "charts" / "chr_test123" / "main.png"
            chart_path.parent.mkdir(parents=True, exist_ok=True)
            chart_path.write_bytes(b"png-bytes")

            res = client.get("/charts/chr_test123/main.png")
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.content, b"png-bytes")

            miss = client.get("/charts/not_found/main.png")
            self.assertEqual(miss.status_code, 404)

    def test_chart_run_meta_endpoint_serves_json(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            app_mod = load_app(tmp)
            client = TestClient(app_mod.app)

            meta_path = tmp / "uploads" / "chart_runs" / "chr_test123" / "meta.json"
            meta_path.parent.mkdir(parents=True, exist_ok=True)
            meta_payload = {"run_id": "chr_test123", "ok": True}
            meta_path.write_text(json.dumps(meta_payload, ensure_ascii=False), encoding="utf-8")

            res = client.get("/chart-runs/chr_test123/meta")
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.json().get("run_id"), "chr_test123")
            self.assertTrue(res.json().get("ok"))

            miss = client.get("/chart-runs/not_found/meta")
            self.assertEqual(miss.status_code, 404)

    def test_chart_exec_tool_schema_exposes_optional_execution_profile(self):
        from services.common.tool_registry import DEFAULT_TOOL_REGISTRY

        tool = DEFAULT_TOOL_REGISTRY.require("chart.exec").to_openai()
        params = tool["function"]["parameters"]["properties"]
        self.assertIn("execution_profile", params)
        execution_profile = params["execution_profile"]
        self.assertEqual(execution_profile.get("default"), "trusted")
        self.assertIn("sandboxed", execution_profile.get("enum", []))

    def test_chart_endpoints_require_auth_when_enabled(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            secret = "chart-auth-secret"
            app_mod = load_app(tmp, auth_required="1", auth_secret=secret)
            client = TestClient(app_mod.app)

            chart_path = tmp / "uploads" / "charts" / "chr_test123" / "main.png"
            chart_path.parent.mkdir(parents=True, exist_ok=True)
            chart_path.write_bytes(b"png-bytes")

            meta_path = tmp / "uploads" / "chart_runs" / "chr_test123" / "meta.json"
            meta_path.parent.mkdir(parents=True, exist_ok=True)
            meta_path.write_text(json.dumps({"run_id": "chr_test123"}), encoding="utf-8")

            self.assertEqual(client.get("/charts/chr_test123/main.png").status_code, 401)
            self.assertEqual(client.get("/chart-runs/chr_test123/meta").status_code, 401)

    def test_chart_endpoints_forbid_student_role_when_auth_enabled(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            secret = "chart-auth-secret"
            app_mod = load_app(tmp, auth_required="1", auth_secret=secret)
            client = TestClient(app_mod.app)

            chart_path = tmp / "uploads" / "charts" / "chr_test123" / "main.png"
            chart_path.parent.mkdir(parents=True, exist_ok=True)
            chart_path.write_bytes(b"png-bytes")

            meta_path = tmp / "uploads" / "chart_runs" / "chr_test123" / "meta.json"
            meta_path.parent.mkdir(parents=True, exist_ok=True)
            meta_path.write_text(json.dumps({"run_id": "chr_test123"}), encoding="utf-8")

            student_headers = _auth_headers(actor_id="student_a", role="student", secret=secret)
            teacher_headers = _auth_headers(actor_id="teacher_a", role="teacher", secret=secret)
            admin_headers = _auth_headers(actor_id="admin_a", role="admin", secret=secret)
            service_headers = _auth_headers(actor_id="svc_ops", role="service", secret=secret)

            self.assertEqual(client.get("/charts/chr_test123/main.png", headers=student_headers).status_code, 403)
            self.assertEqual(client.get("/chart-runs/chr_test123/meta", headers=student_headers).status_code, 403)
            self.assertEqual(client.get("/charts/chr_test123/main.png", headers=teacher_headers).status_code, 200)
            self.assertEqual(client.get("/chart-runs/chr_test123/meta", headers=teacher_headers).status_code, 200)
            self.assertEqual(client.get("/charts/chr_test123/main.png", headers=admin_headers).status_code, 200)
            self.assertEqual(client.get("/chart-runs/chr_test123/meta", headers=admin_headers).status_code, 200)
            self.assertEqual(client.get("/charts/chr_test123/main.png", headers=service_headers).status_code, 200)
            self.assertEqual(client.get("/chart-runs/chr_test123/meta", headers=service_headers).status_code, 200)


if __name__ == "__main__":
    unittest.main()
