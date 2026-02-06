import importlib
import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


def load_app(tmp_dir: Path):
    os.environ["DATA_DIR"] = str(tmp_dir / "data")
    os.environ["UPLOADS_DIR"] = str(tmp_dir / "uploads")
    os.environ["DIAG_LOG"] = "0"
    os.environ["TEACHER_SESSION_COMPACT_ENABLED"] = "1"
    os.environ["TEACHER_SESSION_COMPACT_MAIN_ONLY"] = "1"
    os.environ["TEACHER_SESSION_COMPACT_MAX_MESSAGES"] = "20"
    os.environ["TEACHER_SESSION_COMPACT_KEEP_TAIL"] = "10"
    os.environ["TEACHER_SESSION_COMPACT_MIN_INTERVAL_SEC"] = "0"
    import services.api.app as app_mod

    importlib.reload(app_mod)
    return app_mod


class TeacherSessionCompactionTest(unittest.TestCase):
    def test_process_chat_job_triggers_teacher_main_compaction(self):
        with TemporaryDirectory() as td:
            tmp = Path(td)
            app_mod = load_app(tmp)
            app_mod.run_agent = lambda *args, **kwargs: {"reply": "stub-reply"}  # type: ignore[assignment]

            teacher_id = app_mod.resolve_teacher_id("teacher")
            session_id = "main"
            for i in range(12):
                app_mod.append_teacher_session_message(teacher_id, session_id, "user", f"旧用户消息{i}")
                app_mod.append_teacher_session_message(teacher_id, session_id, "assistant", f"旧助手消息{i}")

            job_id = "cjob_compact_001"
            record = {
                "job_id": job_id,
                "request_id": "req_compact_001",
                "session_id": session_id,
                "status": "queued",
                "role": "teacher",
                "teacher_id": teacher_id,
                "request": {
                    "messages": [{"role": "user", "content": "新问题"}],
                    "role": "teacher",
                    "teacher_id": teacher_id,
                },
            }
            app_mod.write_chat_job(job_id, record, overwrite=True)
            app_mod.process_chat_job(job_id)

            path = app_mod.teacher_session_file(teacher_id, session_id)
            lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
            self.assertTrue(lines)
            records = [json.loads(ln) for ln in lines]

            summary = next((r for r in records if r.get("kind") == "session_summary"), None)
            self.assertIsNotNone(summary)
            self.assertTrue(summary.get("synthetic"))
            self.assertIn("会话压缩摘要", str(summary.get("content") or ""))

            dialog = [r for r in records if r.get("role") in {"user", "assistant"} and not r.get("synthetic")]
            self.assertLessEqual(len(dialog), 10)


if __name__ == "__main__":
    unittest.main()
