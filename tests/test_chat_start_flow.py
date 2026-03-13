import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient

from tests.helpers.app_factory import create_test_app


def load_app(tmp_dir: Path):
    return create_test_app(tmp_dir, reset_modules=True)


class ChatStartFlowTest(unittest.TestCase):
    def test_chat_start_route_uses_chat_deps(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            sentinel = object()
            captured = {}

            def fake_start(req, *, deps):  # type: ignore[no-untyped-def]
                captured["request_id"] = getattr(req, "request_id", "")
                captured["deps"] = deps
                return {"ok": True, "job_id": "cjob_fake", "status": "queued"}

            with (
                patch(
                    "services.api.wiring.chat_wiring._start_chat_orchestration_impl",
                    fake_start,
                ),
                patch(
                    "services.api.wiring.chat_wiring._chat_start_deps",
                    lambda _core=None: sentinel,
                ),
            ):
                with TestClient(app_mod.app) as client:
                    res = client.post(
                        "/chat/start",
                        json={
                            "request_id": "req_chat_start_001",
                            "role": "teacher",
                            "messages": [{"role": "user", "content": "hello"}],
                        },
                    )
                    self.assertEqual(res.status_code, 200)
                    self.assertEqual((res.json() or {}).get("job_id"), "cjob_fake")
                    self.assertEqual(captured.get("request_id"), "req_chat_start_001")
                    self.assertIs(captured.get("deps"), sentinel)

    def test_chat_start_rejects_unknown_agent_id_field_and_does_not_create_job_or_request_map(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            app_mod = load_app(tmp)
            request_id = "req_chat_start_agent_forbidden_001"

            self.assertIsNone(app_mod.get_core().get_chat_job_id_by_request(request_id))

            with TestClient(app_mod.app) as client:
                res = client.post(
                    "/chat/start",
                    json={
                        "request_id": request_id,
                        "role": "teacher",
                        "agent_id": "opencode",
                        "messages": [{"role": "user", "content": "hello"}],
                    },
                )

            self.assertEqual(res.status_code, 422)
            self.assertIsNone(app_mod.get_core().get_chat_job_id_by_request(request_id))

            chat_job_dir = tmp / "uploads" / "chat_jobs"
            if chat_job_dir.exists():
                self.assertEqual(list(chat_job_dir.glob("*/job.json")), [])


if __name__ == "__main__":
    unittest.main()
