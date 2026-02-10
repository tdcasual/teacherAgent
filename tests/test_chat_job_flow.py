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


class ChatJobFlowTest(unittest.TestCase):
    def _seed_total_mode_exam(
        self,
        tmp: Path,
        exam_id: str = "EX20260209_9b92e1",
        score_mode: str = "total",
        paper_filename: str = "",
    ) -> None:
        data_dir = tmp / "data"
        exam_dir = data_dir / "exams" / exam_id
        exam_dir.mkdir(parents=True, exist_ok=True)

        is_total_mode = str(score_mode or "").strip().lower() == "total"
        qid = "TOTAL" if is_total_mode else "SUBJECT_PHYSICS"
        raw_label = "TOTAL" if is_total_mode else "物理"

        responses_path = exam_dir / "responses_scored.csv"
        responses_path.write_text(
            "\n".join(
                [
                    "exam_id,student_id,student_name,class_name,question_id,question_no,sub_no,raw_label,raw_value,raw_answer,score,is_correct",
                    f"{exam_id},S001,张三,2403,{qid},,,{raw_label},88.0,,88.0,",
                    f"{exam_id},S002,李四,2403,{qid},,,{raw_label},72.5,,72.5,",
                ]
            ),
            encoding="utf-8",
        )

        questions_path = exam_dir / "questions.csv"
        questions_path.write_text(
            f"question_id,question_no,sub_no,order,max_score,stem_ref\n{qid},,,1,,\n",
            encoding="utf-8",
        )

        if paper_filename:
            paper_dir = exam_dir / "paper"
            paper_dir.mkdir(parents=True, exist_ok=True)
            (paper_dir / paper_filename).write_bytes(b"%PDF-1.4\n")

        manifest = {
            "exam_id": exam_id,
            "generated_at": "2026-02-10T22:24:17",
            "meta": {"date": "2026-01-03", "class_name": "2403,2404", "language": "zh", "score_mode": score_mode},
            "files": {
                "responses_scored": str(responses_path.resolve()),
                "questions": str(questions_path.resolve()),
            },
            "counts": {"students": 2, "responses": 2, "questions": 1},
        }
        (exam_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


    def test_chat_start_is_idempotent_and_status_eventually_done(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            app_mod = load_app(tmp)
            from services.api.workers import chat_worker_service

            chat_worker_service.start_chat_worker = lambda **_: None
            app_mod.CHAT_JOB_WORKER_STARTED = True  # type: ignore[attr-defined]
            app_mod.teacher_assignment_preflight = lambda _req: None  # type: ignore[attr-defined]
            captured = {"skill_id": None}

            def fake_run_agent(messages, role_hint=None, extra_system=None, skill_id=None, teacher_id=None, agent_id=None):
                last_user = ""
                for m in reversed(messages or []):
                    if m.get("role") == "user":
                        last_user = str(m.get("content") or "")
                        break
                captured["skill_id"] = skill_id
                return {"reply": f"echo:{role_hint}:{last_user}"}

            app_mod.run_agent = fake_run_agent  # type: ignore[attr-defined]

            with TestClient(app_mod.app) as client:
                payload = {
                    "request_id": "req_test_001",
                    "role": "teacher",
                    "messages": [{"role": "user", "content": "请帮我生成作业，作业ID A2403_2026-02-04，每个知识点 5 题"}],
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
                self.assertIn("echo:teacher:", data.get("reply", ""))
                self.assertEqual(data.get("skill_id_requested"), "")
                self.assertEqual(data.get("skill_id_effective"), "physics-homework-generator")
                self.assertEqual(captured["skill_id"], "physics-homework-generator")

    def test_chat_status_missing_job(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            app_mod = load_app(tmp)
            from services.api.workers import chat_worker_service

            chat_worker_service.start_chat_worker = lambda **_: None
            app_mod.CHAT_JOB_WORKER_STARTED = True  # type: ignore[attr-defined]
            with TestClient(app_mod.app) as client:
                res = client.get("/chat/status", params={"job_id": "cjob_missing_001"})
                self.assertEqual(res.status_code, 404)

    def test_chat_start_teacher_uses_teacher_specific_routing(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            app_mod = load_app(tmp)
            from services.api.workers import chat_worker_service

            chat_worker_service.start_chat_worker = lambda **_: None
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
                        "match": {"roles": ["teacher"], "kinds": ["chat.skill"]},
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

    def test_chat_start_rejects_agent_id_payload(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            app_mod = load_app(tmp)
            from services.api.workers import chat_worker_service

            chat_worker_service.start_chat_worker = lambda **_: None
            app_mod.CHAT_JOB_WORKER_STARTED = True  # type: ignore[attr-defined]

            with TestClient(app_mod.app) as client:
                payload = {
                    "request_id": "req_agent_id_001",
                    "role": "teacher",
                    "agent_id": "opencode",
                    "messages": [{"role": "user", "content": "hello"}],
                }
                res = client.post("/chat/start", json=payload)
                self.assertEqual(res.status_code, 400)

    def test_chat_job_total_mode_subject_request_is_guarded_end_to_end(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            self._seed_total_mode_exam(tmp, exam_id="EX20260209_9b92e1")
            app_mod = load_app(tmp)
            from services.api.workers import chat_worker_service

            chat_worker_service.start_chat_worker = lambda **_: None
            app_mod.CHAT_JOB_WORKER_STARTED = True  # type: ignore[attr-defined]

            calls = {"run_agent": 0}

            def fake_run_agent(messages, role_hint=None, extra_system=None, skill_id=None, teacher_id=None, agent_id=None):
                calls["run_agent"] += 1
                return {"reply": "should_not_reach_llm_path"}

            app_mod.run_agent = fake_run_agent  # type: ignore[attr-defined]

            with TestClient(app_mod.app) as client:
                start = client.post(
                    "/chat/start",
                    json={
                        "request_id": "req_total_subject_guard_001",
                        "role": "teacher",
                        "teacher_id": "teacher",
                        "messages": [{"role": "user", "content": "分析EX20260209_9b92e1的物理成绩"}],
                    },
                )
                self.assertEqual(start.status_code, 200)
                job_id = str(start.json().get("job_id") or "")
                self.assertTrue(job_id)

                app_mod.process_chat_job(job_id)

                status = client.get("/chat/status", params={"job_id": job_id})
                self.assertEqual(status.status_code, 200)
                payload = status.json()
                self.assertEqual(payload.get("status"), "done")
                reply_text = str(payload.get("reply") or "")
                self.assertIn("单科成绩说明", reply_text)
                self.assertIn("score_mode: \"total\"", reply_text)
                self.assertIn("不能把总分当作物理单科成绩", reply_text)
                self.assertEqual(calls["run_agent"], 0)

    def test_chat_job_total_mode_matching_single_subject_allows_agent_end_to_end(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            self._seed_total_mode_exam(
                tmp,
                exam_id="EX20260209_9b92e1",
                score_mode="total",
                paper_filename="2025-2026学年高二上学期2月期末物理试题.pdf",
            )
            app_mod = load_app(tmp)
            from services.api.workers import chat_worker_service

            chat_worker_service.start_chat_worker = lambda **_: None
            app_mod.CHAT_JOB_WORKER_STARTED = True  # type: ignore[attr-defined]

            calls = {"run_agent": 0}

            def fake_run_agent(messages, role_hint=None, extra_system=None, skill_id=None, teacher_id=None, agent_id=None):
                calls["run_agent"] += 1
                return {"reply": "physics_total_mode_analysis"}

            app_mod.run_agent = fake_run_agent  # type: ignore[attr-defined]

            with TestClient(app_mod.app) as client:
                start = client.post(
                    "/chat/start",
                    json={
                        "request_id": "req_total_subject_allow_single_001",
                        "role": "teacher",
                        "teacher_id": "teacher",
                        "messages": [{"role": "user", "content": "分析EX20260209_9b92e1的物理成绩"}],
                    },
                )
                self.assertEqual(start.status_code, 200)
                job_id = str(start.json().get("job_id") or "")
                self.assertTrue(job_id)

                app_mod.process_chat_job(job_id)

                status = client.get("/chat/status", params={"job_id": job_id})
                self.assertEqual(status.status_code, 200)
                payload = status.json()
                self.assertEqual(payload.get("status"), "done")
                reply_text = str(payload.get("reply") or "")
                self.assertEqual(reply_text, "physics_total_mode_analysis")
                self.assertEqual(calls["run_agent"], 1)

    def test_chat_job_total_mode_chemistry_request_is_guarded_end_to_end(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            self._seed_total_mode_exam(tmp, exam_id="EX20260209_9b92e1")
            app_mod = load_app(tmp)
            from services.api.workers import chat_worker_service

            chat_worker_service.start_chat_worker = lambda **_: None
            app_mod.CHAT_JOB_WORKER_STARTED = True  # type: ignore[attr-defined]

            calls = {"run_agent": 0}

            def fake_run_agent(messages, role_hint=None, extra_system=None, skill_id=None, teacher_id=None, agent_id=None):
                calls["run_agent"] += 1
                return {"reply": "should_not_reach_llm_path"}

            app_mod.run_agent = fake_run_agent  # type: ignore[attr-defined]

            with TestClient(app_mod.app) as client:
                start = client.post(
                    "/chat/start",
                    json={
                        "request_id": "req_total_subject_guard_chem_001",
                        "role": "teacher",
                        "teacher_id": "teacher",
                        "messages": [{"role": "user", "content": "分析EX20260209_9b92e1的化学成绩"}],
                    },
                )
                self.assertEqual(start.status_code, 200)
                job_id = str(start.json().get("job_id") or "")
                self.assertTrue(job_id)

                app_mod.process_chat_job(job_id)

                status = client.get("/chat/status", params={"job_id": job_id})
                self.assertEqual(status.status_code, 200)
                payload = status.json()
                self.assertEqual(payload.get("status"), "done")
                reply_text = str(payload.get("reply") or "")
                self.assertIn("单科成绩说明", reply_text)
                self.assertIn("score_mode: \"total\"", reply_text)
                self.assertIn("不能把总分", reply_text)
                self.assertEqual(calls["run_agent"], 0)

    def test_chat_job_total_mode_english_subject_score_request_is_guarded_end_to_end(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            self._seed_total_mode_exam(tmp, exam_id="EX20260209_9b92e1")
            app_mod = load_app(tmp)
            from services.api.workers import chat_worker_service

            chat_worker_service.start_chat_worker = lambda **_: None
            app_mod.CHAT_JOB_WORKER_STARTED = True  # type: ignore[attr-defined]

            calls = {"run_agent": 0}

            def fake_run_agent(messages, role_hint=None, extra_system=None, skill_id=None, teacher_id=None, agent_id=None):
                calls["run_agent"] += 1
                return {"reply": "should_not_reach_llm_path"}

            app_mod.run_agent = fake_run_agent  # type: ignore[attr-defined]

            with TestClient(app_mod.app) as client:
                start = client.post(
                    "/chat/start",
                    json={
                        "request_id": "req_total_subject_guard_en_001",
                        "role": "teacher",
                        "teacher_id": "teacher",
                        "messages": [{"role": "user", "content": "Analyze EX20260209_9b92e1 subject score"}],
                    },
                )
                self.assertEqual(start.status_code, 200)
                job_id = str(start.json().get("job_id") or "")
                self.assertTrue(job_id)

                app_mod.process_chat_job(job_id)

                status = client.get("/chat/status", params={"job_id": job_id})
                self.assertEqual(status.status_code, 200)
                payload = status.json()
                self.assertEqual(payload.get("status"), "done")
                reply_text = str(payload.get("reply") or "")
                self.assertIn("单科成绩说明", reply_text)
                self.assertIn("score_mode: \"total\"", reply_text)
                self.assertIn("不能把总分", reply_text)
                self.assertEqual(calls["run_agent"], 0)

    def test_chat_job_subject_mode_english_subject_score_request_allows_agent(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            self._seed_total_mode_exam(tmp, exam_id="EX20260209_9b92e1", score_mode="subject")
            app_mod = load_app(tmp)
            from services.api.workers import chat_worker_service

            chat_worker_service.start_chat_worker = lambda **_: None
            app_mod.CHAT_JOB_WORKER_STARTED = True  # type: ignore[attr-defined]

            calls = {"run_agent": 0}

            def fake_run_agent(messages, role_hint=None, extra_system=None, skill_id=None, teacher_id=None, agent_id=None):
                calls["run_agent"] += 1
                return {"reply": "normal_subject_mode_reply"}

            app_mod.run_agent = fake_run_agent  # type: ignore[attr-defined]

            with TestClient(app_mod.app) as client:
                start = client.post(
                    "/chat/start",
                    json={
                        "request_id": "req_subject_mode_allow_en_001",
                        "role": "teacher",
                        "teacher_id": "teacher",
                        "messages": [{"role": "user", "content": "Analyze EX20260209_9b92e1 subject score"}],
                    },
                )
                self.assertEqual(start.status_code, 200)
                job_id = str(start.json().get("job_id") or "")
                self.assertTrue(job_id)

                app_mod.process_chat_job(job_id)

                status = client.get("/chat/status", params={"job_id": job_id})
                self.assertEqual(status.status_code, 200)
                payload = status.json()
                self.assertEqual(payload.get("status"), "done")
                reply_text = str(payload.get("reply") or "")
                self.assertEqual(reply_text, "normal_subject_mode_reply")
                self.assertEqual(calls["run_agent"], 1)


if __name__ == "__main__":
    unittest.main()
