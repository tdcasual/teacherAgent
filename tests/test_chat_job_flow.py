import importlib
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


class ChatJobFlowTest(unittest.TestCase):
    def test_chat_start_is_idempotent_and_status_eventually_done(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            app_mod = load_app(tmp)
            app_mod.start_chat_worker = lambda: None  # type: ignore[assignment]
            app_mod.CHAT_JOB_WORKER_STARTED = True  # type: ignore[attr-defined]

            def fake_run_agent(messages, role_hint=None, extra_system=None, skill_id=None):
                last_user = ""
                for m in reversed(messages or []):
                    if m.get("role") == "user":
                        last_user = str(m.get("content") or "")
                        break
                return {"reply": f"echo:{role_hint}:{last_user}"}

            app_mod.run_agent = fake_run_agent  # type: ignore[attr-defined]

            with TestClient(app_mod.app) as client:
                payload = {
                    "request_id": "req_test_001",
                    "role": "teacher",
                    "messages": [{"role": "user", "content": "hello"}],
                }
                res1 = client.post("/chat/start", json=payload)
                self.assertEqual(res1.status_code, 200)
                job_id_1 = res1.json()["job_id"]
                self.assertTrue(job_id_1)

                res2 = client.post("/chat/start", json=payload)
                self.assertEqual(res2.status_code, 200)
                job_id_2 = res2.json()["job_id"]
                self.assertEqual(job_id_1, job_id_2)

                # Deterministic: process job synchronously.
                app_mod.process_chat_job(job_id_1)

                res_status = client.get("/chat/status", params={"job_id": job_id_1})
                self.assertEqual(res_status.status_code, 200)
                data = res_status.json()
                self.assertEqual(data["status"], "done")
                self.assertIn("echo:teacher:hello", data.get("reply", ""))

    def test_chat_status_missing_job(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            app_mod = load_app(tmp)
            app_mod.start_chat_worker = lambda: None  # type: ignore[assignment]
            app_mod.CHAT_JOB_WORKER_STARTED = True  # type: ignore[attr-defined]
            with TestClient(app_mod.app) as client:
                res = client.get("/chat/status", params={"job_id": "cjob_missing_001"})
                self.assertEqual(res.status_code, 404)


if __name__ == "__main__":
    unittest.main()
