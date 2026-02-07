from __future__ import annotations

import json
import re
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.teacher_memory_auto_service import (
    TeacherMemoryAutoDeps,
    teacher_memory_auto_flush_from_session,
    teacher_memory_auto_propose_from_turn,
)


class TeacherMemoryAutoServiceTest(unittest.TestCase):
    def _deps(self, *, session_path: Path):
        logged = []
        marks = []

        deps = TeacherMemoryAutoDeps(
            auto_enabled=True,
            auto_min_content_chars=8,
            auto_infer_min_priority=50,
            auto_flush_enabled=True,
            session_compact_enabled=True,
            session_compact_max_messages=4,
            memory_flush_margin_messages=1,
            memory_flush_max_source_chars=500,
            durable_intent_patterns=[re.compile(r"记住")],
            temporary_hint_patterns=[re.compile(r"今天")],
            norm_text=lambda text: re.sub(r"\s+", "", str(text or "")),
            auto_infer_candidate=lambda teacher_id, session_id, user_text: None,
            auto_quota_reached=lambda teacher_id: False,
            stable_hash=lambda *parts: "hash_key",
            priority_score=lambda **kwargs: 80,
            log_event=lambda teacher_id, event, payload: logged.append((event, payload)),
            find_duplicate=lambda teacher_id, **kwargs: None,
            memory_propose=lambda teacher_id, **kwargs: {"ok": True, "proposal_id": "p1", "status": "applied"},
            session_compaction_cycle_no=lambda teacher_id, session_id: 1,
            session_index_item=lambda teacher_id, session_id: {"memory_flush_cycle": 0},
            teacher_session_file=lambda teacher_id, session_id: session_path,
            compact_transcript=lambda records, max_chars: "摘要",
            mark_session_memory_flush=lambda teacher_id, session_id, cycle_no: marks.append((teacher_id, session_id, cycle_no)),
        )
        return deps, logged, marks

    def test_auto_propose_disabled_short_circuit(self):
        with TemporaryDirectory() as td:
            deps, _, _ = self._deps(session_path=Path(td) / "session.jsonl")
            deps = TeacherMemoryAutoDeps(**{**deps.__dict__, "auto_enabled": False})
            result = teacher_memory_auto_propose_from_turn(
                "teacher_1",
                "main",
                "请记住以后先给结论。",
                "",
                deps=deps,
            )
            self.assertEqual(result.get("reason"), "disabled")

    def test_auto_propose_low_priority_infer_is_skipped(self):
        with TemporaryDirectory() as td:
            deps, logged, _ = self._deps(session_path=Path(td) / "session.jsonl")
            deps = TeacherMemoryAutoDeps(
                **{
                    **deps.__dict__,
                    "durable_intent_patterns": [],
                    "auto_infer_candidate": lambda teacher_id, session_id, user_text: {
                        "target": "MEMORY",
                        "title": "自动记忆",
                        "content": "后续输出简洁",
                        "trigger": "implicit_repeated_preference",
                        "similar_hits": 2,
                    },
                    "priority_score": lambda **kwargs: 10,
                }
            )
            result = teacher_memory_auto_propose_from_turn(
                "teacher_1",
                "main",
                "后续输出都简洁一点",
                "",
                deps=deps,
            )
            self.assertFalse(result.get("ok"))
            self.assertEqual(result.get("reason"), "low_priority")
            self.assertEqual(logged[-1][0], "auto_infer_skipped")

    def test_auto_flush_below_threshold(self):
        with TemporaryDirectory() as td:
            session_path = Path(td) / "session.jsonl"
            session_path.write_text(
                json.dumps({"role": "user", "content": "u1"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            deps, _, _ = self._deps(session_path=session_path)
            result = teacher_memory_auto_flush_from_session("teacher_1", "main", deps=deps)
            self.assertEqual(result.get("reason"), "below_threshold")

    def test_auto_flush_success_marks_cycle(self):
        with TemporaryDirectory() as td:
            session_path = Path(td) / "session.jsonl"
            lines = [
                {"role": "user", "content": "u1"},
                {"role": "assistant", "content": "a1"},
                {"role": "user", "content": "u2"},
                {"role": "assistant", "content": "a2"},
            ]
            session_path.write_text("\n".join(json.dumps(line, ensure_ascii=False) for line in lines) + "\n", encoding="utf-8")
            deps, _, marks = self._deps(session_path=session_path)
            result = teacher_memory_auto_flush_from_session("teacher_1", "main", deps=deps)
            self.assertTrue(result.get("ok"))
            self.assertTrue(result.get("created"))
            self.assertEqual(marks[-1], ("teacher_1", "main", 1))


if __name__ == "__main__":
    unittest.main()
