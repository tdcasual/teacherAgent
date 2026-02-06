import importlib
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient


def load_app(tmp_dir: Path, *, debounce_ms: int = 500, lane_max_queue: int = 6):
    os.environ["DATA_DIR"] = str(tmp_dir / "data")
    os.environ["UPLOADS_DIR"] = str(tmp_dir / "uploads")
    os.environ["DIAG_LOG"] = "0"
    os.environ["CHAT_LANE_DEBOUNCE_MS"] = str(debounce_ms)
    os.environ["CHAT_LANE_MAX_QUEUE"] = str(lane_max_queue)
    os.environ["CHAT_WORKER_POOL_SIZE"] = "1"
    import services.api.app as app_mod

    importlib.reload(app_mod)
    return app_mod


class ChatLaneQueueTest(unittest.TestCase):
    def test_chat_start_debounce_reuses_recent_job_in_same_lane(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td), debounce_ms=3000, lane_max_queue=6)
            app_mod.start_chat_worker = lambda: None  # type: ignore[assignment]
            app_mod.CHAT_JOB_WORKER_STARTED = True  # type: ignore[attr-defined]

            payload1 = {
                "request_id": "req_lane_001",
                "role": "teacher",
                "messages": [{"role": "user", "content": "请帮我列出今天计划"}],
            }
            payload2 = {
                "request_id": "req_lane_002",
                "role": "teacher",
                "messages": [{"role": "user", "content": "请帮我列出今天计划"}],
            }

            with TestClient(app_mod.app) as client:
                res1 = client.post("/chat/start", json=payload1)
                self.assertEqual(res1.status_code, 200)
                job_id_1 = res1.json()["job_id"]
                self.assertTrue(job_id_1)

                res2 = client.post("/chat/start", json=payload2)
                self.assertEqual(res2.status_code, 200)
                data2 = res2.json()
                self.assertEqual(data2["job_id"], job_id_1)
                self.assertTrue(data2.get("debounced"))

    def test_chat_start_lane_cap_returns_429(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td), debounce_ms=0, lane_max_queue=1)
            app_mod.start_chat_worker = lambda: None  # type: ignore[assignment]
            app_mod.CHAT_JOB_WORKER_STARTED = True  # type: ignore[attr-defined]

            with TestClient(app_mod.app) as client:
                first = client.post(
                    "/chat/start",
                    json={
                        "request_id": "req_lane_cap_001",
                        "role": "student",
                        "student_id": "S001",
                        "messages": [{"role": "user", "content": "第一条"}],
                    },
                )
                self.assertEqual(first.status_code, 200)

                second = client.post(
                    "/chat/start",
                    json={
                        "request_id": "req_lane_cap_002",
                        "role": "student",
                        "student_id": "S001",
                        "messages": [{"role": "user", "content": "第二条"}],
                    },
                )
                self.assertEqual(second.status_code, 429)
                self.assertIn("排队过多", second.text)


if __name__ == "__main__":
    unittest.main()

