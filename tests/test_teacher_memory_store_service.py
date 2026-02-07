from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.teacher_memory_store_service import (
    TeacherMemoryStoreDeps,
    teacher_memory_active_applied_records,
    teacher_memory_load_events,
    teacher_memory_log_event,
)


class TeacherMemoryStoreServiceTest(unittest.TestCase):
    def _deps(self, root: Path):
        return TeacherMemoryStoreDeps(
            teacher_workspace_dir=lambda teacher_id: root / teacher_id,
            proposal_path=lambda teacher_id, proposal_id: root / teacher_id / "proposals" / f"{proposal_id}.json",
            recent_proposals=lambda teacher_id, limit: [],
            is_expired_record=lambda rec, now: False,
            rank_score=lambda rec: float(rec.get("priority_score") or 0),
            now_iso=lambda: "2026-02-07T12:30:00",
        )

    def test_log_and_load_events(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            deps = self._deps(root)
            teacher_memory_log_event("teacher_1", "search", {"hits": 2}, deps=deps)
            events = teacher_memory_load_events("teacher_1", deps=deps, limit=10)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].get("event"), "search")

    def test_active_applied_records_filters_status(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            deps = TeacherMemoryStoreDeps(
                teacher_workspace_dir=lambda teacher_id: root / teacher_id,
                proposal_path=lambda teacher_id, proposal_id: root / teacher_id / "proposals" / f"{proposal_id}.json",
                recent_proposals=lambda teacher_id, limit: [
                    {"proposal_id": "p1", "status": "applied", "target": "MEMORY", "priority_score": 80},
                    {"proposal_id": "p2", "status": "proposed", "target": "MEMORY", "priority_score": 90},
                ],
                is_expired_record=lambda rec, now: False,
                rank_score=lambda rec: float(rec.get("priority_score") or 0),
                now_iso=lambda: "2026-02-07T12:30:00",
            )
            items = teacher_memory_active_applied_records("teacher_1", deps=deps, target="MEMORY", limit=10)
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].get("proposal_id"), "p1")


if __name__ == "__main__":
    unittest.main()
