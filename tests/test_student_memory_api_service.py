from __future__ import annotations

import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.student_memory_api_service import (
    StudentMemoryApiDeps,
    create_proposal_api,
    delete_proposal_api,
    list_proposals_api,
    review_proposal_api,
    student_memory_auto_propose_from_turn_api,
)


class StudentMemoryApiServiceTest(unittest.TestCase):
    def test_create_list_review_delete_flow(self):
        with TemporaryDirectory() as td:
            root = Path(td)

            deps = StudentMemoryApiDeps(
                resolve_teacher_id=lambda teacher_id=None: str(teacher_id or "teacher"),
                teacher_workspace_dir=lambda teacher_id: root / "teacher_workspaces" / str(teacher_id),
                now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
            )

            created = create_proposal_api(
                teacher_id="teacher_a",
                student_id="S001",
                memory_type="learning_preference",
                content="学生偏好先给结论，再分步讲解。",
                evidence_refs=["session:main"],
                source="manual",
                deps=deps,
            )
            self.assertTrue(created.get("ok"))
            self.assertEqual(created.get("status"), "proposed")
            proposal_id = str(created.get("proposal_id") or "")
            self.assertTrue(proposal_id)

            listed = list_proposals_api(
                teacher_id="teacher_a",
                student_id="S001",
                status="proposed",
                limit=20,
                deps=deps,
            )
            self.assertTrue(listed.get("ok"))
            self.assertTrue(any(p.get("proposal_id") == proposal_id for p in listed.get("proposals") or []))

            reviewed = review_proposal_api(
                proposal_id,
                teacher_id="teacher_a",
                approve=True,
                deps=deps,
            )
            self.assertTrue(reviewed.get("ok"))
            self.assertEqual(reviewed.get("status"), "applied")

            deleted = delete_proposal_api(
                proposal_id,
                teacher_id="teacher_a",
                deps=deps,
            )
            self.assertTrue(deleted.get("ok"))
            self.assertEqual(deleted.get("status"), "deleted")

            listed_after = list_proposals_api(
                teacher_id="teacher_a",
                student_id="S001",
                status=None,
                limit=20,
                deps=deps,
            )
            self.assertTrue(listed_after.get("ok"))
            self.assertFalse(any(p.get("proposal_id") == proposal_id for p in listed_after.get("proposals") or []))

    def test_teacher_scope_isolated(self):
        with TemporaryDirectory() as td:
            root = Path(td)

            deps = StudentMemoryApiDeps(
                resolve_teacher_id=lambda teacher_id=None: str(teacher_id or "teacher"),
                teacher_workspace_dir=lambda teacher_id: root / "teacher_workspaces" / str(teacher_id),
                now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
            )

            created = create_proposal_api(
                teacher_id="teacher_a",
                student_id="S001",
                memory_type="stable_misconception",
                content="学生常把位移和路程混淆，且已在多次会话中重复出现。",
                evidence_refs=["session:s1"],
                source="manual",
                deps=deps,
            )
            self.assertTrue(created.get("ok"))

            listed_other = list_proposals_api(
                teacher_id="teacher_b",
                student_id="S001",
                status=None,
                limit=20,
                deps=deps,
            )
            self.assertTrue(listed_other.get("ok"))
            self.assertEqual(listed_other.get("proposals"), [])

    def test_create_rejects_blocked_content(self):
        with TemporaryDirectory() as td:
            root = Path(td)

            deps = StudentMemoryApiDeps(
                resolve_teacher_id=lambda teacher_id=None: str(teacher_id or "teacher"),
                teacher_workspace_dir=lambda teacher_id: root / "teacher_workspaces" / str(teacher_id),
                now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
            )

            blocked = create_proposal_api(
                teacher_id="teacher_a",
                student_id="S001",
                memory_type="learning_preference",
                content="本次考试95分，班级第3名，建议记入长期记忆。",
                evidence_refs=["session:s2"],
                source="manual",
                deps=deps,
            )
            self.assertFalse(blocked.get("ok"))
            self.assertEqual(blocked.get("error"), "content_blocked")
            self.assertTrue(blocked.get("risk_flags"))

    def test_create_rejects_score_with_trailing_punctuation(self):
        with TemporaryDirectory() as td:
            root = Path(td)

            deps = StudentMemoryApiDeps(
                resolve_teacher_id=lambda teacher_id=None: str(teacher_id or "teacher"),
                teacher_workspace_dir=lambda teacher_id: root / "teacher_workspaces" / str(teacher_id),
                now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
            )

            blocked = create_proposal_api(
                teacher_id="teacher_a",
                student_id="S001",
                memory_type="learning_preference",
                content="以后请先给结论，我这次考了95分。",
                evidence_refs=["session:s3"],
                source="manual",
                deps=deps,
            )
            self.assertFalse(blocked.get("ok"))
            self.assertEqual(blocked.get("error"), "content_blocked")

    def test_auto_propose_creates_and_deduplicates(self):
        with TemporaryDirectory() as td:
            root = Path(td)

            deps = StudentMemoryApiDeps(
                resolve_teacher_id=lambda teacher_id=None: str(teacher_id or "teacher"),
                teacher_workspace_dir=lambda teacher_id: root / "teacher_workspaces" / str(teacher_id),
                now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
            )

            created = student_memory_auto_propose_from_turn_api(
                teacher_id="teacher_a",
                student_id="S001",
                session_id="general_2026-02-15",
                user_text="以后请先给结论，再分步解释。",
                assistant_text="收到。",
                request_id="req_001",
                deps=deps,
            )
            self.assertTrue(created.get("ok"))
            self.assertTrue(created.get("created"))
            self.assertEqual(created.get("memory_type"), "learning_preference")

            duplicated = student_memory_auto_propose_from_turn_api(
                teacher_id="teacher_a",
                student_id="S001",
                session_id="general_2026-02-15",
                user_text="以后请先给结论，再分步解释。",
                assistant_text="收到。",
                request_id="req_002",
                deps=deps,
            )
            self.assertTrue(duplicated.get("ok"))
            self.assertFalse(duplicated.get("created"))
            self.assertEqual(duplicated.get("reason"), "duplicate")


if __name__ == "__main__":
    unittest.main()
