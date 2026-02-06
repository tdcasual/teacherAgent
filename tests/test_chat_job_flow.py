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

            def fake_run_agent(messages, role_hint=None, extra_system=None, skill_id=None, teacher_id=None):
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

    def test_chat_start_teacher_uses_teacher_specific_routing(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            app_mod = load_app(tmp)
            app_mod.start_chat_worker = lambda: None  # type: ignore[assignment]
            app_mod.CHAT_JOB_WORKER_STARTED = True  # type: ignore[attr-defined]

            class _FakeGatewayResp:
                def __init__(self, text: str):
                    self._text = text

                def as_chat_completion(self):
                    return {"choices": [{"message": {"content": self._text}}]}

            calls = []

            def fake_generate(req, provider=None, mode=None, model=None, allow_fallback=True):
                calls.append(
                    {
                        "provider": provider,
                        "mode": mode,
                        "model": model,
                        "allow_fallback": allow_fallback,
                    }
                )
                return _FakeGatewayResp(f"model:{model or ''}")

            app_mod.LLM_GATEWAY.generate = fake_generate  # type: ignore[attr-defined]

            with TestClient(app_mod.app) as client:
                for teacher_id, model_name in (("teacher_alpha", "model-alpha"), ("teacher_beta", "model-beta")):
                    config = {
                        "enabled": True,
                        "channels": [{"id": "chat_main", "target": {"provider": "openai", "mode": "openai-chat", "model": model_name}}],
                        "rules": [
                            {
                                "id": "chat_rule",
                                "priority": 100,
                                "match": {"roles": ["teacher"], "kinds": ["chat.agent"]},
                                "route": {"channel_id": "chat_main"},
                            }
                        ],
                    }
                    create = client.post(
                        "/teacher/llm-routing/proposals",
                        json={"teacher_id": teacher_id, "note": f"seed-{teacher_id}", "config": config},
                    )
                    self.assertEqual(create.status_code, 200)
                    proposal_id = create.json().get("proposal_id")
                    self.assertTrue(proposal_id)
                    review = client.post(
                        f"/teacher/llm-routing/proposals/{proposal_id}/review",
                        json={"teacher_id": teacher_id, "approve": True},
                    )
                    self.assertEqual(review.status_code, 200)

                for teacher_id, request_id, expected_model in (
                    ("teacher_alpha", "req_teacher_alpha_001", "model-alpha"),
                    ("teacher_beta", "req_teacher_beta_001", "model-beta"),
                ):
                    start = client.post(
                        "/chat/start",
                        json={
                            "request_id": request_id,
                            "role": "teacher",
                            "teacher_id": teacher_id,
                            "messages": [{"role": "user", "content": f"hello-{teacher_id}"}],
                        },
                    )
                    self.assertEqual(start.status_code, 200)
                    job_id = start.json()["job_id"]
                    app_mod.process_chat_job(job_id)
                    status = client.get("/chat/status", params={"job_id": job_id})
                    self.assertEqual(status.status_code, 200)
                    payload = status.json()
                    self.assertEqual(payload.get("status"), "done")
                    self.assertIn(expected_model, payload.get("reply") or "")

            routed_models = [str(item.get("model") or "") for item in calls if item.get("allow_fallback") is False]
            self.assertIn("model-alpha", routed_models)
            self.assertIn("model-beta", routed_models)


if __name__ == "__main__":
    unittest.main()
