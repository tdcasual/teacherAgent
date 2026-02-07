from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.teacher_memory_search_service import TeacherMemorySearchDeps, teacher_memory_search


class TeacherMemorySearchServiceTest(unittest.TestCase):
    def test_empty_query_returns_empty_matches(self):
        deps = TeacherMemorySearchDeps(
            ensure_teacher_workspace=lambda teacher_id: None,
            mem0_search=lambda teacher_id, query, limit: {"ok": False, "matches": []},
            search_filter_expired=True,
            load_record=lambda teacher_id, proposal_id: {},
            is_expired_record=lambda rec: False,
            diag_log=lambda *_args, **_kwargs: None,
            log_event=lambda *_args, **_kwargs: None,
            teacher_workspace_file=lambda teacher_id, name: Path("/tmp") / name,
            teacher_daily_memory_dir=lambda teacher_id: Path("/tmp"),
        )
        result = teacher_memory_search("teacher_1", "", deps=deps)
        self.assertEqual(result, {"matches": []})

    def test_mem0_hits_are_returned(self):
        events = []
        deps = TeacherMemorySearchDeps(
            ensure_teacher_workspace=lambda teacher_id: None,
            mem0_search=lambda teacher_id, query, limit: {"ok": True, "matches": [{"proposal_id": "p1", "content": "x"}]},
            search_filter_expired=True,
            load_record=lambda teacher_id, proposal_id: {"proposal_id": proposal_id},
            is_expired_record=lambda rec: False,
            diag_log=lambda *_args, **_kwargs: None,
            log_event=lambda teacher_id, event, payload: events.append((teacher_id, event, payload)),
            teacher_workspace_file=lambda teacher_id, name: Path("/tmp") / name,
            teacher_daily_memory_dir=lambda teacher_id: Path("/tmp"),
        )
        result = teacher_memory_search("teacher_1", "查找", deps=deps, limit=3)
        self.assertEqual(result.get("mode"), "mem0")
        self.assertEqual(len(result.get("matches") or []), 1)
        self.assertEqual(events[-1][1], "search")

    def test_keyword_fallback_searches_workspace_files(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            memory = root / "MEMORY.md"
            memory.write_text("第一行\n关键字命中\n第三行\n", encoding="utf-8")
            deps = TeacherMemorySearchDeps(
                ensure_teacher_workspace=lambda teacher_id: None,
                mem0_search=lambda teacher_id, query, limit: {"ok": False, "matches": []},
                search_filter_expired=True,
                load_record=lambda teacher_id, proposal_id: {},
                is_expired_record=lambda rec: False,
                diag_log=lambda *_args, **_kwargs: None,
                log_event=lambda *_args, **_kwargs: None,
                teacher_workspace_file=lambda teacher_id, name: memory if name == "MEMORY.md" else root / name,
                teacher_daily_memory_dir=lambda teacher_id: root / "memory",
            )
            result = teacher_memory_search("teacher_1", "关键字", deps=deps, limit=2)
            self.assertEqual(result.get("mode"), "keyword")
            self.assertTrue(result.get("matches"))


if __name__ == "__main__":
    unittest.main()
