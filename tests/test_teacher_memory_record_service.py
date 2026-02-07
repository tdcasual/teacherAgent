from __future__ import annotations

import json
import re
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.teacher_memory_record_service import (
    TeacherMemoryRecordDeps,
    teacher_memory_auto_quota_reached,
    teacher_memory_find_duplicate,
    teacher_memory_recent_proposals,
)


class TeacherMemoryRecordServiceTest(unittest.TestCase):
    def _deps(self, root: Path):
        return TeacherMemoryRecordDeps(
            ensure_teacher_workspace=lambda teacher_id: (root / teacher_id / "proposals").mkdir(parents=True, exist_ok=True),
            teacher_workspace_dir=lambda teacher_id: root / teacher_id,
            teacher_session_file=lambda teacher_id, session_id: root / teacher_id / f"{session_id}.jsonl",
            load_teacher_sessions_index=lambda teacher_id: [],
            save_teacher_sessions_index=lambda teacher_id, items: None,
            session_index_max_items=500,
            now_iso=lambda: "2026-02-07T12:00:00",
            norm_text=lambda text: re.sub(r"\s+", "", str(text or "")).lower(),
            loose_match=lambda a, b: a == b,
            conflicts=lambda a, b: False,
            auto_infer_enabled=True,
            auto_infer_min_chars=8,
            auto_infer_block_patterns=[],
            temporary_hint_patterns=[],
            auto_infer_stable_patterns=[],
            auto_infer_lookback_turns=20,
            auto_infer_min_repeats=2,
            auto_max_proposals_per_day=2,
            proposal_path=lambda teacher_id, proposal_id: root / teacher_id / "proposals" / f"{proposal_id}.json",
            atomic_write_json=lambda path, data: path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8"),
        )

    def test_recent_proposals_and_duplicate_detection(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            deps = self._deps(root)
            proposal_dir = root / "teacher_1" / "proposals"
            proposal_dir.mkdir(parents=True, exist_ok=True)
            (proposal_dir / "p1.json").write_text(
                json.dumps({"proposal_id": "p1", "status": "applied", "target": "MEMORY", "content": "abc"}, ensure_ascii=False),
                encoding="utf-8",
            )
            proposals = teacher_memory_recent_proposals("teacher_1", deps=deps, limit=10)
            self.assertEqual(len(proposals), 1)

            dup = teacher_memory_find_duplicate(
                "teacher_1",
                target="MEMORY",
                content="abc",
                dedupe_key="key1",
                deps=deps,
            )
            self.assertIsNotNone(dup)

    def test_auto_quota_reached_counts_auto_records(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            deps = self._deps(root)
            proposal_dir = root / "teacher_2" / "proposals"
            proposal_dir.mkdir(parents=True, exist_ok=True)
            today_prefix = "2026-02-07"
            for idx in range(2):
                (proposal_dir / f"p{idx}.json").write_text(
                    json.dumps(
                        {
                            "proposal_id": f"p{idx}",
                            "status": "applied",
                            "source": "auto_intent",
                            "created_at": f"{today_prefix}T10:0{idx}:00",
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
            reached = teacher_memory_auto_quota_reached("teacher_2", deps=deps)
            self.assertTrue(reached)


if __name__ == "__main__":
    unittest.main()
