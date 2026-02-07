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


class ChatRouteFlowTest(unittest.TestCase):
    def test_chat_route_delegates_to_compute_chat_reply_sync(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            captured = {}

            def fake_compute(req, session_id="main", teacher_id_override=None):  # type: ignore[no-untyped-def]
                captured["role"] = getattr(req, "role", None)
                captured["msg_count"] = len(getattr(req, "messages", []) or [])
                return "delegated reply", "teacher", "hello"

            app_mod._compute_chat_reply_sync = fake_compute  # type: ignore[attr-defined]

            with TestClient(app_mod.app) as client:
                res = client.post(
                    "/chat",
                    json={
                        "role": "teacher",
                        "messages": [{"role": "user", "content": "请帮我布置作业"}],
                    },
                )

            self.assertEqual(res.status_code, 200)
            payload = res.json() or {}
            self.assertEqual(payload.get("reply"), "delegated reply")
            self.assertEqual(payload.get("role"), "teacher")
            self.assertEqual(captured.get("role"), "teacher")
            self.assertEqual(captured.get("msg_count"), 1)

    def test_student_blocked_reply_does_not_trigger_profile_update(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            calls = {"profile": 0, "enqueue": 0}

            def fake_compute(req, session_id="main", teacher_id_override=None):  # type: ignore[no-untyped-def]
                return "正在生成上一条回复，请稍候再试。", "student", "你好"

            def fake_profile_update(_payload):  # type: ignore[no-untyped-def]
                calls["profile"] += 1

            def fake_enqueue(_payload):  # type: ignore[no-untyped-def]
                calls["enqueue"] += 1

            app_mod._compute_chat_reply_sync = fake_compute  # type: ignore[attr-defined]
            app_mod.student_profile_update = fake_profile_update  # type: ignore[attr-defined]
            app_mod.enqueue_profile_update = fake_enqueue  # type: ignore[attr-defined]
            app_mod.PROFILE_UPDATE_ASYNC = False  # type: ignore[attr-defined]

            with TestClient(app_mod.app) as client:
                res = client.post(
                    "/chat",
                    json={
                        "role": "student",
                        "student_id": "S1",
                        "messages": [{"role": "user", "content": "开始今天作业"}],
                    },
                )

            self.assertEqual(res.status_code, 200)
            payload = res.json() or {}
            self.assertEqual(payload.get("reply"), "正在生成上一条回复，请稍候再试。")
            self.assertEqual(payload.get("role"), "student")
            self.assertEqual(calls["profile"], 0)
            self.assertEqual(calls["enqueue"], 0)


if __name__ == "__main__":
    unittest.main()
