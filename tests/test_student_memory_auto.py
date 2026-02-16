from __future__ import annotations

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


def build_student_job(
    job_id: str,
    request_id: str,
    *,
    teacher_id: str,
    student_id: str,
    text: str,
) -> dict:
    return {
        "job_id": job_id,
        "request_id": request_id,
        "session_id": "general_2026-02-15",
        "status": "queued",
        "role": "student",
        "teacher_id": teacher_id,
        "request": {
            "messages": [{"role": "user", "content": text}],
            "role": "student",
            "teacher_id": teacher_id,
            "student_id": student_id,
            "assignment_id": None,
            "assignment_date": "2026-02-15",
        },
    }


class StudentMemoryAutoTest(unittest.TestCase):
    def test_student_turn_auto_creates_controlled_proposal(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            app_mod.run_agent = lambda *args, **kwargs: {"reply": "收到，后续我会按你说的方式回答。"}  # type: ignore[attr-defined]

            teacher_id = app_mod.resolve_teacher_id("teacher_a")
            student_id = "S001"
            record = build_student_job(
                "cjob_student_auto_001",
                "req_student_auto_001",
                teacher_id=teacher_id,
                student_id=student_id,
                text="以后请先给结论，再给步骤解释。",
            )
            app_mod.write_chat_job(record["job_id"], record, overwrite=True)
            app_mod.process_chat_job(record["job_id"])

            with TestClient(app_mod.app) as client:
                listed = client.get(
                    "/teacher/student-memory/proposals",
                    params={"teacher_id": teacher_id, "student_id": student_id, "status": "proposed"},
                )
                self.assertEqual(listed.status_code, 200)
                proposals = listed.json().get("proposals") or []
                auto_items = [p for p in proposals if p.get("source") == "auto_student_infer"]
                self.assertTrue(auto_items)
                self.assertEqual(auto_items[0].get("memory_type"), "learning_preference")
                self.assertEqual(auto_items[0].get("status"), "proposed")

    def test_student_turn_without_teacher_scope_skips_auto_proposal(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            app_mod.run_agent = lambda *args, **kwargs: {"reply": "收到。"}  # type: ignore[attr-defined]

            student_id = "S001"
            record = build_student_job(
                "cjob_student_auto_002",
                "req_student_auto_002",
                teacher_id="",
                student_id=student_id,
                text="以后请先给结论，再给步骤解释。",
            )
            app_mod.write_chat_job(record["job_id"], record, overwrite=True)
            app_mod.process_chat_job(record["job_id"])

            default_teacher = app_mod.resolve_teacher_id(None)
            with TestClient(app_mod.app) as client:
                listed = client.get(
                    "/teacher/student-memory/proposals",
                    params={"teacher_id": default_teacher, "student_id": student_id, "status": "proposed"},
                )
                self.assertEqual(listed.status_code, 200)
                proposals = listed.json().get("proposals") or []
                self.assertFalse(any(p.get("source") == "auto_student_infer" for p in proposals))

    def test_student_turn_auto_respects_daily_quota(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            app_mod.run_agent = lambda *args, **kwargs: {"reply": "收到。"}  # type: ignore[attr-defined]

            teacher_id = app_mod.resolve_teacher_id("teacher_a")
            student_id = "S001"
            for idx in range(1, 8):
                text = f"以后请先给结论，再给步骤解释。第{idx}次偏好说明"
                record = build_student_job(
                    f"cjob_student_auto_quota_{idx:03d}",
                    f"req_student_auto_quota_{idx:03d}",
                    teacher_id=teacher_id,
                    student_id=student_id,
                    text=text,
                )
                app_mod.write_chat_job(record["job_id"], record, overwrite=True)
                app_mod.process_chat_job(record["job_id"])

            with TestClient(app_mod.app) as client:
                listed = client.get(
                    "/teacher/student-memory/proposals",
                    params={"teacher_id": teacher_id, "student_id": student_id, "status": "proposed"},
                )
                self.assertEqual(listed.status_code, 200)
                proposals = listed.json().get("proposals") or []
                auto_items = [p for p in proposals if p.get("source") == "auto_student_infer"]
                self.assertEqual(len(auto_items), 6)
                contents = {str(item.get("content") or "") for item in auto_items}
                self.assertNotIn("以后请先给结论，再给步骤解释。第7次偏好说明", contents)

    def test_student_turn_auto_blocked_content_records_event_without_proposal(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            app_mod.run_agent = lambda *args, **kwargs: {"reply": "收到。"}  # type: ignore[attr-defined]

            teacher_id = app_mod.resolve_teacher_id("teacher_a")
            student_id = "S001"
            record = build_student_job(
                "cjob_student_auto_block_001",
                "req_student_auto_block_001",
                teacher_id=teacher_id,
                student_id=student_id,
                text="以后请先给结论，我这次考了95分。",
            )
            app_mod.write_chat_job(record["job_id"], record, overwrite=True)
            app_mod.process_chat_job(record["job_id"])

            job_saved = app_mod.load_chat_job(record["job_id"])
            self.assertEqual(job_saved.get("status"), "done")

            with TestClient(app_mod.app) as client:
                listed = client.get(
                    "/teacher/student-memory/proposals",
                    params={"teacher_id": teacher_id, "student_id": student_id, "status": "proposed"},
                )
                self.assertEqual(listed.status_code, 200)
                proposals = listed.json().get("proposals") or []
                self.assertFalse(any(p.get("source") == "auto_student_infer" for p in proposals))

            log_path = app_mod.teacher_workspace_dir(teacher_id) / "telemetry" / "student_memory_events.jsonl"
            self.assertTrue(log_path.exists())
            events = [
                json.loads(line)
                for line in log_path.read_text(encoding="utf-8").splitlines()
                if str(line).strip()
            ]
            blocked = [e for e in events if e.get("event") == "proposal_blocked"]
            self.assertTrue(blocked)
            self.assertEqual(blocked[-1].get("student_id"), student_id)
            self.assertEqual(blocked[-1].get("error"), "content_blocked")


if __name__ == "__main__":
    unittest.main()
