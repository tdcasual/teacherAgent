from __future__ import annotations

import importlib
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient


def load_app(tmp_dir: Path):
    os.environ["DATA_DIR"] = str(tmp_dir / "data")
    os.environ["UPLOADS_DIR"] = str(tmp_dir / "uploads")
    os.environ["DIAG_LOG"] = "0"
    import services.api.app as app_mod

    importlib.reload(app_mod)
    return app_mod


class StudentMemoryProposalsApiTest(unittest.TestCase):
    def test_create_list_review_delete(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            teacher_id = app_mod.resolve_teacher_id("teacher_a")

            with TestClient(app_mod.app) as client:
                created = client.post(
                    "/teacher/student-memory/proposals",
                    json={
                        "teacher_id": teacher_id,
                        "student_id": "S001",
                        "memory_type": "learning_preference",
                        "content": "学生偏好先看结论，再看过程推导。",
                        "evidence_refs": ["session:main"],
                    },
                )
                self.assertEqual(created.status_code, 200)
                payload = created.json()
                self.assertTrue(payload.get("ok"))
                self.assertEqual(payload.get("status"), "proposed")
                proposal_id = str(payload.get("proposal_id") or "")
                self.assertTrue(proposal_id)

                listed = client.get(
                    "/teacher/student-memory/proposals",
                    params={"teacher_id": teacher_id, "student_id": "S001", "status": "proposed"},
                )
                self.assertEqual(listed.status_code, 200)
                self.assertTrue(any(p.get("proposal_id") == proposal_id for p in listed.json().get("proposals") or []))

                reviewed = client.post(
                    f"/teacher/student-memory/proposals/{proposal_id}/review",
                    json={"teacher_id": teacher_id, "approve": True},
                )
                self.assertEqual(reviewed.status_code, 200)
                self.assertEqual(reviewed.json().get("status"), "applied")

                deleted = client.delete(
                    f"/teacher/student-memory/proposals/{proposal_id}",
                    params={"teacher_id": teacher_id},
                )
                self.assertEqual(deleted.status_code, 200)
                self.assertEqual(deleted.json().get("status"), "deleted")

                listed_after = client.get(
                    "/teacher/student-memory/proposals",
                    params={"teacher_id": teacher_id, "student_id": "S001"},
                )
                self.assertEqual(listed_after.status_code, 200)
                self.assertFalse(any(p.get("proposal_id") == proposal_id for p in listed_after.json().get("proposals") or []))

    def test_blocked_content_returns_400(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            teacher_id = app_mod.resolve_teacher_id("teacher_a")

            with TestClient(app_mod.app) as client:
                blocked = client.post(
                    "/teacher/student-memory/proposals",
                    json={
                        "teacher_id": teacher_id,
                        "student_id": "S001",
                        "memory_type": "learning_preference",
                        "content": "该生本次得分98分，班级第2名。",
                    },
                )
                self.assertEqual(blocked.status_code, 400)

    def test_invalid_memory_type_returns_400(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            teacher_id = app_mod.resolve_teacher_id("teacher_a")

            with TestClient(app_mod.app) as client:
                invalid = client.post(
                    "/teacher/student-memory/proposals",
                    json={
                        "teacher_id": teacher_id,
                        "student_id": "S001",
                        "memory_type": "score_detail",
                        "content": "学生偏好图示。",
                    },
                )
                self.assertEqual(invalid.status_code, 400)


if __name__ == "__main__":
    unittest.main()
