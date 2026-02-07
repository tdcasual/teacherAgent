from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.teacher_memory_apply_service import TeacherMemoryApplyDeps, teacher_memory_apply


class TeacherMemoryApplyServiceTest(unittest.TestCase):
    def test_reject_path_marks_proposal_rejected(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            proposal_path = root / "p1.json"
            proposal_path.write_text(
                json.dumps({"proposal_id": "p1", "status": "proposed", "target": "MEMORY", "content": "x"}, ensure_ascii=False),
                encoding="utf-8",
            )
            events = []

            deps = TeacherMemoryApplyDeps(
                proposal_path=lambda teacher_id, proposal_id: proposal_path,
                atomic_write_json=lambda path, data: path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8"),
                now_iso=lambda: "2026-02-07T10:00:00",
                log_event=lambda teacher_id, event, payload: events.append((event, payload)),
                is_sensitive=lambda content: False,
                auto_apply_strict=True,
                teacher_daily_memory_path=lambda teacher_id: root / "daily.md",
                teacher_workspace_file=lambda teacher_id, name: root / name,
                find_conflicting_applied=lambda teacher_id, proposal_id, target, content: [],
                record_ttl_days=lambda record: 30,
                record_expire_at=lambda record: None,
                is_expired_record=lambda record: False,
                mark_superseded=lambda teacher_id, proposal_ids, by_proposal_id: None,
                diag_log=lambda *_args, **_kwargs: None,
                mem0_should_index_target=lambda target: False,
                mem0_index_entry=lambda teacher_id, text, metadata: {"ok": True},
            )

            result = teacher_memory_apply("teacher_1", "p1", deps=deps, approve=False)
            self.assertTrue(result.get("ok"))
            self.assertEqual(result.get("status"), "rejected")
            saved = json.loads(proposal_path.read_text(encoding="utf-8"))
            self.assertEqual(saved.get("status"), "rejected")
            self.assertEqual(events[-1][0], "proposal_rejected")


if __name__ == "__main__":
    unittest.main()
