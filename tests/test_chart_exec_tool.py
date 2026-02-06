import importlib
import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient


def load_app(tmp_dir: Path):
    os.environ["DATA_DIR"] = str(tmp_dir / "data")
    os.environ["UPLOADS_DIR"] = str(tmp_dir / "uploads")
    os.environ["DIAG_LOG"] = "0"
    import services.api.app as app_mod

    importlib.reload(app_mod)
    return app_mod


class ChartExecToolTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
