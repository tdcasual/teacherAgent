import importlib
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


def load_app(
    tmp_dir: Path,
    *,
    compact_max: int = 160,
    flush_margin: int = 24,
    infer_min_priority: int = 58,
):
    os.environ["DATA_DIR"] = str(tmp_dir / "data")
    os.environ["UPLOADS_DIR"] = str(tmp_dir / "uploads")
    os.environ["DIAG_LOG"] = "0"

    os.environ["TEACHER_MEMORY_AUTO_ENABLED"] = "1"
    os.environ["TEACHER_MEMORY_AUTO_MIN_CONTENT_CHARS"] = "8"
    os.environ["TEACHER_MEMORY_AUTO_MAX_PROPOSALS_PER_DAY"] = "20"
    os.environ["TEACHER_MEMORY_FLUSH_ENABLED"] = "1"
    os.environ["TEACHER_MEMORY_FLUSH_MARGIN_MESSAGES"] = str(flush_margin)
    os.environ["TEACHER_MEMORY_FLUSH_MAX_SOURCE_CHARS"] = "1200"
    os.environ["TEACHER_MEMORY_AUTO_APPLY_ENABLED"] = "1"
    os.environ["TEACHER_MEMORY_AUTO_INFER_ENABLED"] = "1"
    os.environ["TEACHER_MEMORY_AUTO_INFER_MIN_REPEATS"] = "2"
    os.environ["TEACHER_MEMORY_AUTO_INFER_LOOKBACK_TURNS"] = "20"
    os.environ["TEACHER_MEMORY_AUTO_INFER_MIN_PRIORITY"] = str(infer_min_priority)

    os.environ["TEACHER_SESSION_COMPACT_ENABLED"] = "1"
    os.environ["TEACHER_SESSION_COMPACT_MAIN_ONLY"] = "1"
    os.environ["TEACHER_SESSION_COMPACT_MAX_MESSAGES"] = str(compact_max)
    os.environ["TEACHER_SESSION_COMPACT_KEEP_TAIL"] = str(max(2, compact_max // 2))
    os.environ["TEACHER_SESSION_COMPACT_MIN_INTERVAL_SEC"] = "0"

    import services.api.app as app_mod

    importlib.reload(app_mod)
    return app_mod


def build_teacher_job(job_id: str, request_id: str, teacher_id: str, text: str) -> dict:
    return {
        "job_id": job_id,
        "request_id": request_id,
        "session_id": "main",
        "status": "queued",
        "role": "teacher",
        "teacher_id": teacher_id,
        "request": {
            "messages": [{"role": "user", "content": text}],
            "role": "teacher",
            "teacher_id": teacher_id,
        },
    }


class TeacherAutoMemoryTest(unittest.TestCase):
    def test_explicit_preference_creates_auto_intent_proposal(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            app_mod.run_agent = lambda *args, **kwargs: {"reply": "好的，我会按这个格式执行。"}  # type: ignore[attr-defined]

            teacher_id = app_mod.resolve_teacher_id("teacher")
            record = build_teacher_job(
                "cjob_auto_memory_001",
                "req_auto_memory_001",
                teacher_id,
                "请记住：以后默认输出三段式总结，先结论再行动项。",
            )
            app_mod.write_chat_job(record["job_id"], record, overwrite=True)
            app_mod.process_chat_job(record["job_id"])

            listed = app_mod.teacher_memory_list_proposals(teacher_id, status="applied", limit=50)
            proposals = listed.get("proposals") or []
            auto_items = [p for p in proposals if p.get("source") == "auto_intent"]
            self.assertTrue(auto_items)
            self.assertEqual(auto_items[0].get("status"), "applied")
            self.assertEqual(auto_items[0].get("target"), "MEMORY")
            self.assertIn("以后默认输出三段式总结", str(auto_items[0].get("content") or ""))

    def test_auto_intent_is_deduplicated(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            app_mod.run_agent = lambda *args, **kwargs: {"reply": "收到。"}  # type: ignore[attr-defined]

            teacher_id = app_mod.resolve_teacher_id("teacher")
            text = "请记住：以后默认输出三段式总结，先结论再行动项。"

            rec1 = build_teacher_job("cjob_auto_memory_101", "req_auto_memory_101", teacher_id, text)
            app_mod.write_chat_job(rec1["job_id"], rec1, overwrite=True)
            app_mod.process_chat_job(rec1["job_id"])

            rec2 = build_teacher_job("cjob_auto_memory_102", "req_auto_memory_102", teacher_id, text)
            app_mod.write_chat_job(rec2["job_id"], rec2, overwrite=True)
            app_mod.process_chat_job(rec2["job_id"])

            listed = app_mod.teacher_memory_list_proposals(teacher_id, status="applied", limit=100)
            proposals = listed.get("proposals") or []
            auto_items = [p for p in proposals if p.get("source") == "auto_intent"]
            self.assertEqual(len(auto_items), 1)

    def test_near_compaction_creates_auto_flush_proposal(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td), compact_max=8, flush_margin=2)
            app_mod.run_agent = lambda *args, **kwargs: {"reply": "继续执行。"}  # type: ignore[attr-defined]

            teacher_id = app_mod.resolve_teacher_id("teacher")
            session_id = "main"
            for i in range(3):
                app_mod.append_teacher_session_message(teacher_id, session_id, "user", f"旧问题{i}")
                app_mod.append_teacher_session_message(teacher_id, session_id, "assistant", f"旧回答{i}")

            rec = build_teacher_job(
                "cjob_auto_memory_201",
                "req_auto_memory_201",
                teacher_id,
                "继续把这个方案拆成执行清单。",
            )
            app_mod.write_chat_job(rec["job_id"], rec, overwrite=True)
            app_mod.process_chat_job(rec["job_id"])

            listed = app_mod.teacher_memory_list_proposals(teacher_id, status="applied", limit=100)
            proposals = listed.get("proposals") or []
            flush_items = [p for p in proposals if p.get("source") == "auto_flush"]
            self.assertTrue(flush_items)
            self.assertEqual(flush_items[0].get("target"), "DAILY")

    def test_repeated_preference_without_keyword_can_auto_infer(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            app_mod.run_agent = lambda *args, **kwargs: {"reply": "已按你要求输出。"}  # type: ignore[attr-defined]

            teacher_id = app_mod.resolve_teacher_id("teacher")
            text = "后续输出都采用三段结构：结论、依据、行动项。"

            rec1 = build_teacher_job("cjob_auto_memory_301", "req_auto_memory_301", teacher_id, text)
            app_mod.write_chat_job(rec1["job_id"], rec1, overwrite=True)
            app_mod.process_chat_job(rec1["job_id"])

            rec2 = build_teacher_job("cjob_auto_memory_302", "req_auto_memory_302", teacher_id, text)
            app_mod.write_chat_job(rec2["job_id"], rec2, overwrite=True)
            app_mod.process_chat_job(rec2["job_id"])

            listed = app_mod.teacher_memory_list_proposals(teacher_id, status="applied", limit=100)
            proposals = listed.get("proposals") or []
            infer_items = [p for p in proposals if p.get("source") == "auto_infer"]
            self.assertTrue(infer_items)
            self.assertEqual(infer_items[0].get("target"), "MEMORY")

    def test_low_priority_auto_infer_is_skipped(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td), infer_min_priority=95)
            app_mod.run_agent = lambda *args, **kwargs: {"reply": "收到。"}  # type: ignore[attr-defined]

            teacher_id = app_mod.resolve_teacher_id("teacher")
            text = "后续输出尽量简短一点。"

            rec1 = build_teacher_job("cjob_auto_memory_401", "req_auto_memory_401", teacher_id, text)
            app_mod.write_chat_job(rec1["job_id"], rec1, overwrite=True)
            app_mod.process_chat_job(rec1["job_id"])

            rec2 = build_teacher_job("cjob_auto_memory_402", "req_auto_memory_402", teacher_id, text)
            app_mod.write_chat_job(rec2["job_id"], rec2, overwrite=True)
            app_mod.process_chat_job(rec2["job_id"])

            listed = app_mod.teacher_memory_list_proposals(teacher_id, status="applied", limit=100)
            proposals = listed.get("proposals") or []
            infer_items = [p for p in proposals if p.get("source") == "auto_infer"]
            self.assertFalse(infer_items)


if __name__ == "__main__":
    unittest.main()
