from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.teacher_session_compaction_service import (
    TeacherSessionCompactionDeps,
    maybe_compact_teacher_session,
)


class TeacherSessionCompactionServiceTest(unittest.TestCase):
    def test_maybe_compact_teacher_session_compacts_when_over_threshold(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            session_path = root / "session.jsonl"
            records = [
                {"role": "user", "content": "u1"},
                {"role": "assistant", "content": "a1"},
                {"role": "user", "content": "u2"},
                {"role": "assistant", "content": "a2"},
                {"role": "user", "content": "u3"},
            ]
            session_path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n", encoding="utf-8")
            marker = {"compacted": None}

            def write_records(path, new_records):
                path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in new_records) + "\n", encoding="utf-8")

            deps = TeacherSessionCompactionDeps(
                compact_enabled=True,
                compact_main_only=False,
                compact_max_messages=2,
                compact_keep_tail=1,
                chat_max_messages_teacher=20,
                teacher_compact_allowed=lambda teacher_id, session_id: True,
                teacher_session_file=lambda teacher_id, session_id: session_path,
                teacher_compact_summary=lambda head, old_summary: "summary-text",
                write_teacher_session_records=write_records,
                mark_teacher_session_compacted=lambda teacher_id, session_id, compacted_messages, new_message_count: marker.__setitem__(
                    "compacted",
                    (compacted_messages, new_message_count),
                ),
                diag_log=lambda *_args, **_kwargs: None,
            )

            result = maybe_compact_teacher_session("teacher_1", "main", deps=deps)
            self.assertTrue(result.get("ok"))
            self.assertEqual(marker["compacted"], (4, 2))

    def test_maybe_compact_teacher_session_respects_disabled_flag(self):
        deps = TeacherSessionCompactionDeps(
            compact_enabled=False,
            compact_main_only=False,
            compact_max_messages=2,
            compact_keep_tail=1,
            chat_max_messages_teacher=20,
            teacher_compact_allowed=lambda teacher_id, session_id: True,
            teacher_session_file=lambda teacher_id, session_id: Path("/tmp/missing"),
            teacher_compact_summary=lambda head, old_summary: "",
            write_teacher_session_records=lambda path, records: None,
            mark_teacher_session_compacted=lambda teacher_id, session_id, compacted_messages, new_message_count: None,
            diag_log=lambda *_args, **_kwargs: None,
        )
        result = maybe_compact_teacher_session("teacher_1", "main", deps=deps)
        self.assertEqual(result.get("reason"), "disabled")


if __name__ == "__main__":
    unittest.main()
