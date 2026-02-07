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


class StudentHistoryFlowTest(unittest.TestCase):
    def test_student_profile_route_uses_profile_api_deps(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            app_mod = load_app(tmp)
            with TestClient(app_mod.app) as client:
                sentinel = object()
                captured = {}

                def _fake_impl(student_id: str, *, deps):
                    captured["student_id"] = student_id
                    captured["deps"] = deps
                    return {"student_id": student_id}

                app_mod._get_profile_api_impl = _fake_impl
                app_mod._student_profile_api_deps = lambda: sentinel

                res = client.get("/student/profile/S1")
                self.assertEqual(res.status_code, 200)
                self.assertEqual(captured.get("student_id"), "S1")
                self.assertIs(captured.get("deps"), sentinel)

    def test_student_chat_writes_history_and_lists_sessions(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            app_mod = load_app(tmp)
            app_mod.start_chat_worker = lambda: None  # type: ignore[assignment]
            app_mod.CHAT_JOB_WORKER_STARTED = True  # type: ignore[attr-defined]

            app_mod.run_agent = lambda *args, **kwargs: {"reply": "stub-reply"}  # type: ignore[assignment]

            with TestClient(app_mod.app) as client:
                start = client.post(
                    "/chat/start",
                    json={
                        "request_id": "req_hist_001",
                        "role": "student",
                        "student_id": "S001",
                        "session_id": "general_2026-02-05",
                        "assignment_date": "2026-02-05",
                        "messages": [{"role": "user", "content": "请讲一下牛顿第二定律"}],
                    },
                )
                self.assertEqual(start.status_code, 200)
                job_id = start.json()["job_id"]

                # User turn should be persisted at /chat/start to avoid session switching refresh gaps.
                hist_before_done = client.get(
                    "/student/history/session",
                    params={
                        "student_id": "S001",
                        "session_id": "general_2026-02-05",
                        "cursor": -1,
                        "limit": 10,
                        "direction": "backward",
                    },
                )
                self.assertEqual(hist_before_done.status_code, 200)
                msgs_before_done = hist_before_done.json().get("messages") or []
                self.assertEqual(len(msgs_before_done), 1)
                self.assertEqual(msgs_before_done[0]["role"], "user")

                app_mod.process_chat_job(job_id)

                sessions = client.get("/student/history/sessions", params={"student_id": "S001"})
                self.assertEqual(sessions.status_code, 200)
                data = sessions.json()
                self.assertTrue(data["ok"])
                self.assertEqual(data["student_id"], "S001")
                self.assertTrue(any(s.get("session_id") == "general_2026-02-05" for s in data.get("sessions") or []))
                item = next(s for s in data["sessions"] if s.get("session_id") == "general_2026-02-05")
                self.assertGreaterEqual(int(item.get("message_count") or 0), 2)

                hist = client.get(
                    "/student/history/session",
                    params={
                        "student_id": "S001",
                        "session_id": "general_2026-02-05",
                        "cursor": -1,
                        "limit": 10,
                        "direction": "backward",
                    },
                )
                self.assertEqual(hist.status_code, 200)
                hdata = hist.json()
                self.assertTrue(hdata["ok"])
                msgs = hdata.get("messages") or []
                self.assertEqual(len(msgs), 2)
                self.assertEqual(msgs[0]["role"], "user")
                self.assertEqual(msgs[1]["role"], "assistant")
                self.assertIn("stub-reply", msgs[1]["content"])


if __name__ == "__main__":
    unittest.main()
