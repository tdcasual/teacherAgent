from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.teacher_context_service import (
    TeacherContextDeps,
    build_teacher_context,
    teacher_memory_context_text,
    teacher_session_summary_text,
)


class TeacherContextServiceTest(unittest.TestCase):
    def test_build_teacher_context_includes_profile_memory_and_summary(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            user_path = root / "USER.md"
            user_path.write_text("name: T", encoding="utf-8")
            events = []

            deps = TeacherContextDeps(
                ensure_teacher_workspace=lambda teacher_id: None,
                teacher_read_text=lambda path, max_chars=2000: path.read_text(encoding="utf-8"),
                teacher_workspace_file=lambda teacher_id, name: user_path if name == "USER.md" else root / name,
                teacher_memory_context_text=lambda teacher_id, max_chars=4000: "memory-note",
                include_session_summary=True,
                session_summary_max_chars=200,
                teacher_session_summary_text=lambda teacher_id, session_id, max_chars: "session-summary",
                teacher_memory_log_event=lambda teacher_id, event, payload: events.append((teacher_id, event, payload)),
            )

            text = build_teacher_context("teacher_x", deps=deps, query="q1", session_id="main")

            self.assertIn("【Teacher Profile】", text)
            self.assertIn("【Long-Term Memory】", text)
            self.assertIn("【Session Summary】", text)
            self.assertEqual(events[-1][1], "context_injected")


    def test_teacher_session_summary_text_reads_first_summary_record(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            session_path = root / "main.jsonl"
            session_path.write_text(
                '\n'.join([
                    '{"kind":"session_summary","content":"这是本次课堂总结"}',
                    '{"kind":"message","role":"user","content":"后续内容"}',
                ]),
                encoding="utf-8",
            )
            text = teacher_session_summary_text(
                "teacher_x",
                "main",
                200,
                teacher_session_file=lambda teacher_id, session_id: session_path,
            )
            self.assertEqual(text, "这是本次课堂总结")

    def test_teacher_memory_context_text_prefers_ranked_active_records_before_markdown_fallback(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            memory_path = root / "MEMORY.md"
            memory_path.write_text("fallback-memory", encoding="utf-8")
            records = [
                {"content": "第二重要", "source": "auto_intent", "score": 2},
                {"content": "最重要", "source": "manual", "score": 9},
            ]
            text = teacher_memory_context_text(
                "teacher_x",
                4000,
                teacher_memory_active_applied_records=lambda teacher_id, target="MEMORY", limit=20: records,
                teacher_read_text=lambda path, max_chars=4000: path.read_text(encoding="utf-8")[:max_chars],
                teacher_workspace_file=lambda teacher_id, name: memory_path,
                teacher_memory_rank_score=lambda rec: rec.get("score", 0),
                teacher_memory_context_max_entries=10,
            )
            self.assertIn("[manual|9] 最重要", text)
            self.assertIn("[auto_intent|2] 第二重要", text)
            self.assertNotIn("fallback-memory", text)


if __name__ == "__main__":
    unittest.main()
