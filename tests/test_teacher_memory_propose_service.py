from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.teacher_memory_propose_service import TeacherMemoryProposeDeps, teacher_memory_propose


class TeacherMemoryProposeServiceTest(unittest.TestCase):
    def test_manual_mode_only_persists_proposal(self):
        with TemporaryDirectory() as td:
            root = Path(td)

            deps = TeacherMemoryProposeDeps(
                ensure_teacher_workspace=lambda teacher_id: None,
                proposal_path=lambda teacher_id, proposal_id: root / f"{proposal_id}.json",
                atomic_write_json=lambda path, data: path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8"),
                uuid_hex=lambda: "abc123def4569999",
                now_iso=lambda: "2026-02-07T11:00:00",
                priority_score=lambda **kwargs: 88,
                record_ttl_days=lambda record: 30,
                record_expire_at=lambda record: None,
                auto_apply_enabled=False,
                auto_apply_targets={"MEMORY"},
                apply=lambda teacher_id, proposal_id, approve: {"error": "should_not_call"},
            )

            result = teacher_memory_propose(
                "teacher_1",
                "MEMORY",
                "偏好",
                "以后输出更精简。",
                deps=deps,
                source="manual",
            )
            self.assertTrue(result.get("ok"))
            self.assertEqual(result.get("proposal_id"), "tmem_abc123def456")
            proposal = result.get("proposal") or {}
            self.assertEqual(proposal.get("status"), "proposed")

            path = root / "tmem_abc123def456.json"
            self.assertTrue(path.exists())

    def test_auto_apply_rejects_disallowed_target(self):
        with TemporaryDirectory() as td:
            root = Path(td)

            deps = TeacherMemoryProposeDeps(
                ensure_teacher_workspace=lambda teacher_id: None,
                proposal_path=lambda teacher_id, proposal_id: root / f"{proposal_id}.json",
                atomic_write_json=lambda path, data: path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8"),
                uuid_hex=lambda: "fff1112223334444",
                now_iso=lambda: "2026-02-07T11:10:00",
                priority_score=lambda **kwargs: 60,
                record_ttl_days=lambda record: 7,
                record_expire_at=lambda record: None,
                auto_apply_enabled=True,
                auto_apply_targets={"MEMORY"},
                apply=lambda teacher_id, proposal_id, approve: {"error": "should_not_call"},
            )

            result = teacher_memory_propose(
                "teacher_1",
                "DAILY",
                "临时偏好",
                "今天先给摘要。",
                deps=deps,
                source="auto_intent",
            )
            self.assertFalse(result.get("ok"))
            self.assertEqual(result.get("status"), "rejected")
            self.assertEqual(result.get("error"), "target_not_allowed_for_auto_apply")

            saved = json.loads((root / "tmem_fff111222333.json").read_text(encoding="utf-8"))
            self.assertEqual(saved.get("status"), "rejected")
            self.assertEqual(saved.get("reject_reason"), "target_not_allowed_for_auto_apply")

    def test_auto_apply_failure_marks_record_rejected(self):
        with TemporaryDirectory() as td:
            root = Path(td)

            deps = TeacherMemoryProposeDeps(
                ensure_teacher_workspace=lambda teacher_id: None,
                proposal_path=lambda teacher_id, proposal_id: root / f"{proposal_id}.json",
                atomic_write_json=lambda path, data: path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8"),
                uuid_hex=lambda: "1002003004005006",
                now_iso=lambda: "2026-02-07T11:20:00",
                priority_score=lambda **kwargs: 75,
                record_ttl_days=lambda record: 30,
                record_expire_at=lambda record: None,
                auto_apply_enabled=True,
                auto_apply_targets={"MEMORY"},
                apply=lambda teacher_id, proposal_id, approve: {"error": "sensitive_content_blocked"},
            )

            result = teacher_memory_propose(
                "teacher_1",
                "MEMORY",
                "偏好",
                "涉及敏感内容",
                deps=deps,
                source="manual",
            )
            self.assertFalse(result.get("ok"))
            self.assertEqual(result.get("status"), "rejected")
            self.assertEqual(result.get("error"), "sensitive_content_blocked")

            saved = json.loads((root / "tmem_100200300400.json").read_text(encoding="utf-8"))
            self.assertEqual(saved.get("status"), "rejected")
            self.assertEqual(saved.get("reject_reason"), "sensitive_content_blocked")

    def test_auto_apply_success_returns_final_record(self):
        with TemporaryDirectory() as td:
            root = Path(td)

            def apply_and_mark(teacher_id: str, proposal_id: str, approve: bool):  # type: ignore[no-untyped-def]
                path = root / f"{proposal_id}.json"
                data = json.loads(path.read_text(encoding="utf-8"))
                data["status"] = "applied"
                data["applied_at"] = "2026-02-07T11:30:00"
                path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                return {"ok": True, "status": "applied"}

            deps = TeacherMemoryProposeDeps(
                ensure_teacher_workspace=lambda teacher_id: None,
                proposal_path=lambda teacher_id, proposal_id: root / f"{proposal_id}.json",
                atomic_write_json=lambda path, data: path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8"),
                uuid_hex=lambda: "999aaa888bbb7777",
                now_iso=lambda: "2026-02-07T11:25:00",
                priority_score=lambda **kwargs: 65,
                record_ttl_days=lambda record: 14,
                record_expire_at=lambda record: None,
                auto_apply_enabled=True,
                auto_apply_targets={"MEMORY"},
                apply=apply_and_mark,
            )

            result = teacher_memory_propose(
                "teacher_1",
                "MEMORY",
                "偏好",
                "以后先给结论。",
                deps=deps,
                source="auto_intent",
            )
            self.assertTrue(result.get("ok"))
            self.assertTrue(result.get("auto_applied"))
            self.assertEqual(result.get("status"), "applied")
            proposal = result.get("proposal") or {}
            self.assertEqual(proposal.get("status"), "applied")


if __name__ == "__main__":
    unittest.main()
