from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.teacher_context_service import TeacherContextDeps, build_teacher_context


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


if __name__ == "__main__":
    unittest.main()
