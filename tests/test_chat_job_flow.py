import importlib
import json
import os
import unittest
import zipfile
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.sax.saxutils import escape

from fastapi.testclient import TestClient


def load_app(tmp_dir: Path, *, diag_log: bool = False):
    os.environ["DATA_DIR"] = str(tmp_dir / "data")
    os.environ["UPLOADS_DIR"] = str(tmp_dir / "uploads")
    os.environ["DIAG_LOG"] = "1" if diag_log else "0"
    if diag_log:
        os.environ["DIAG_LOG_PATH"] = str(tmp_dir / "tmp" / "diagnostics.log")
    import services.api.app as app_mod

    importlib.reload(app_mod)
    return app_mod


def _make_minimal_xlsx(headers, rows) -> bytes:
    def cell_inline(col: str, row_idx: int, value: str) -> str:
        return f'<c r="{col}{row_idx}" t="inlineStr"><is><t>{escape(value)}</t></is></c>'

    def cell_number(col: str, row_idx: int, value) -> str:
        return f'<c r="{col}{row_idx}"><v>{value}</v></c>'

    cols = [chr(ord("A") + i) for i in range(len(headers))]
    sheet_rows = []
    header_cells = "".join([cell_inline(cols[i], 1, str(headers[i])) for i in range(len(headers))])
    sheet_rows.append(f'<row r="1">{header_cells}</row>')
    for r_i, data in enumerate(rows, start=2):
        cells = []
        for c_i, val in enumerate(data):
            col = cols[c_i]
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                cells.append(cell_number(col, r_i, val))
            else:
                cells.append(cell_inline(col, r_i, str(val)))
        sheet_rows.append(f'<row r="{r_i}">{"".join(cells)}</row>')

    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetData>'
        + ''.join(sheet_rows)
        + '</sheetData>'
        '</worksheet>'
    )
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets>'
        '<sheet name="Sheet1" sheetId="1" r:id="rId1"/>'
        '</sheets>'
        '</workbook>'
    )
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/>'
        '</Relationships>'
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/>'
        '</Relationships>'
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '</Types>'
    )

    out = BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", root_rels)
        z.writestr("xl/workbook.xml", workbook_xml)
        z.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        z.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    return out.getvalue()


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

    def _seed_total_mode_exam_with_subject_scores_file(
        self,
        tmp: Path,
        exam_id: str = "EX20260209_9b92e1",
    ) -> None:
        self._seed_total_mode_exam(tmp, exam_id=exam_id, score_mode="total")
        exam_dir = tmp / "data" / "exams" / exam_id
        scores_dir = exam_dir / "scores"
        scores_dir.mkdir(parents=True, exist_ok=True)
        xlsx = _make_minimal_xlsx(
            headers=["考号", "考生姓名", "总分", "科目", "分数", "科目", "分数"],
            rows=[
                ["S001", "张三", 500, "物理", 88, "化学", 80],
                ["S002", "李四", 420, "物理", 72.5, "化学", 68],
            ],
        )
        (scores_dir / "scores.xlsx").write_bytes(xlsx)


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
                self.assertIn("单科成绩说明", reply_text)
                self.assertIn("score_mode: \"total\"", reply_text)
                self.assertIn("不能把总分当作物理单科成绩", reply_text)
                self.assertEqual(calls["run_agent"], 0)

    def test_chat_job_total_mode_matching_single_subject_guard_logs_and_no_agent_call(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            self._seed_total_mode_exam(
                tmp,
                exam_id="EX20260209_9b92e1",
                score_mode="total",
                paper_filename="2025-2026学年高二上学期2月期末物理试题.pdf",
            )
            app_mod = load_app(tmp, diag_log=True)
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
                        "request_id": "req_total_subject_guard_with_logs_001",
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
                self.assertEqual(calls["run_agent"], 0)

            log_path = tmp / "tmp" / "diagnostics.log"
            self.assertTrue(log_path.exists())
            log_text = log_path.read_text(encoding="utf-8")
            self.assertIn('"event": "skill.resolve"', log_text)
            self.assertIn('"event": "teacher_chat.in"', log_text)
            self.assertIn('"event": "teacher_preflight.subject_total_guard"', log_text)
            self.assertNotIn('"event": "teacher_preflight.subject_total_allow_single_subject"', log_text)

    def test_chat_job_total_mode_with_subject_scores_file_allows_agent_and_logs_auto_extract(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            (tmp / "tmp").mkdir(parents=True, exist_ok=True)
            self._seed_total_mode_exam_with_subject_scores_file(tmp, exam_id="EX20260209_9b92e1")
            app_mod = load_app(tmp, diag_log=True)
            from services.api.workers import chat_worker_service

            chat_worker_service.start_chat_worker = lambda **_: None
            app_mod.CHAT_JOB_WORKER_STARTED = True  # type: ignore[attr-defined]

            diag_events = []
            original_diag_log = app_mod.diag_log

            def _capture_diag(event, payload=None):
                diag_events.append((str(event), payload or {}))
                try:
                    original_diag_log(event, payload or {})
                except Exception:
                    pass

            app_mod.diag_log = _capture_diag  # type: ignore[attr-defined]

            calls = {"run_agent": 0}

            def fake_run_agent(messages, role_hint=None, extra_system=None, skill_id=None, teacher_id=None, agent_id=None):
                calls["run_agent"] += 1
                return {"reply": "physics_subject_score_reply"}

            app_mod.run_agent = fake_run_agent  # type: ignore[attr-defined]

            with TestClient(app_mod.app) as client:
                start = client.post(
                    "/chat/start",
                    json={
                        "request_id": "req_total_subject_auto_extract_001",
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
                self.assertEqual(str(payload.get("reply") or ""), "physics_subject_score_reply")
                self.assertEqual(calls["run_agent"], 1)

            event_names = [event for event, _ in diag_events]
            self.assertIn("skill.resolve", event_names)
            self.assertIn("teacher_chat.in", event_names)
            self.assertIn("teacher_preflight.subject_total_auto_extract_subject", event_names)
            self.assertNotIn("teacher_preflight.subject_total_guard", event_names)

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
