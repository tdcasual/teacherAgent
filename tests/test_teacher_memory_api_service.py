import unittest

from services.api.teacher_memory_api_service import (
    TeacherMemoryApiDeps,
    list_proposals_api,
    review_proposal_api,
)


class TeacherMemoryApiServiceTest(unittest.TestCase):
    def test_list_proposals_api_delegates(self):
        deps = TeacherMemoryApiDeps(
            resolve_teacher_id=lambda teacher_id=None: teacher_id or "teacher",
            teacher_memory_list_proposals=lambda teacher_id, status=None, limit=20: {
                "ok": True,
                "teacher_id": teacher_id,
                "status": status,
                "limit": limit,
            },
            teacher_memory_apply=lambda teacher_id, proposal_id, approve=True: {
                "ok": True,
                "teacher_id": teacher_id,
                "proposal_id": proposal_id,
                "status": "applied" if approve else "rejected",
            },
        )
        payload = list_proposals_api("t1", status="proposed", limit=5, deps=deps)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["teacher_id"], "t1")

    def test_review_proposal_api_delegates(self):
        deps = TeacherMemoryApiDeps(
            resolve_teacher_id=lambda teacher_id=None: teacher_id or "teacher",
            teacher_memory_list_proposals=lambda teacher_id, status=None, limit=20: {"ok": True},
            teacher_memory_apply=lambda teacher_id, proposal_id, approve=True: {
                "ok": True,
                "teacher_id": teacher_id,
                "proposal_id": proposal_id,
                "status": "applied" if approve else "rejected",
            },
        )
        payload = review_proposal_api("p1", teacher_id="t2", approve=False, deps=deps)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["teacher_id"], "t2")
        self.assertEqual(payload["proposal_id"], "p1")
        self.assertEqual(payload["status"], "rejected")


if __name__ == "__main__":
    unittest.main()
