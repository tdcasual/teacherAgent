import importlib
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient


def load_app(tmp_dir: Path, *, auto_apply_enabled: bool = True):
    os.environ["DATA_DIR"] = str(tmp_dir / "data")
    os.environ["UPLOADS_DIR"] = str(tmp_dir / "uploads")
    os.environ["DIAG_LOG"] = "0"
    os.environ["TEACHER_MEMORY_AUTO_APPLY_ENABLED"] = "1" if auto_apply_enabled else "0"
    import services.api.app as app_mod

    importlib.reload(app_mod)
    return app_mod


class TeacherMemoryProposalsApiTest(unittest.TestCase):
    def test_proposals_endpoint_uses_teacher_memory_api_deps(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td), auto_apply_enabled=False)
            sentinel = object()
            captured = {}

            def fake_list(teacher_id, *, status, limit, deps):  # type: ignore[no-untyped-def]
                captured["teacher_id"] = teacher_id
                captured["status"] = status
                captured["limit"] = limit
                captured["deps"] = deps
                return {"ok": True, "proposals": []}

            app_mod._list_teacher_memory_proposals_api_impl = fake_list  # type: ignore[attr-defined]
            app_mod._teacher_memory_api_deps = lambda: sentinel  # type: ignore[attr-defined]

            with TestClient(app_mod.app) as client:
                listed = client.get(
                    "/teacher/memory/proposals",
                    params={"teacher_id": "teacher_x", "status": "proposed", "limit": 7},
                )
                self.assertEqual(listed.status_code, 200)
                self.assertEqual(captured.get("teacher_id"), "teacher_x")
                self.assertEqual(captured.get("status"), "proposed")
                self.assertEqual(captured.get("limit"), 7)
                self.assertIs(captured.get("deps"), sentinel)

    def test_review_endpoint_uses_teacher_memory_api_deps(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td), auto_apply_enabled=False)
            sentinel = object()
            captured = {}

            def fake_review(proposal_id, *, teacher_id, approve, deps):  # type: ignore[no-untyped-def]
                captured["proposal_id"] = proposal_id
                captured["teacher_id"] = teacher_id
                captured["approve"] = approve
                captured["deps"] = deps
                return {"ok": True, "status": "applied"}

            app_mod._review_teacher_memory_proposal_api_impl = fake_review  # type: ignore[attr-defined]
            app_mod._teacher_memory_api_deps = lambda: sentinel  # type: ignore[attr-defined]

            with TestClient(app_mod.app) as client:
                review = client.post(
                    "/teacher/memory/proposals/p123/review",
                    json={"teacher_id": "teacher_y", "approve": True},
                )
                self.assertEqual(review.status_code, 200)
                self.assertEqual(captured.get("proposal_id"), "p123")
                self.assertEqual(captured.get("teacher_id"), "teacher_y")
                self.assertTrue(captured.get("approve"))
                self.assertIs(captured.get("deps"), sentinel)

    def test_list_and_review_proposals_when_manual_mode(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td), auto_apply_enabled=False)
            teacher_id = app_mod.resolve_teacher_id("teacher")
            prop = app_mod.teacher_memory_propose(
                teacher_id,
                target="MEMORY",
                title="偏好A",
                content="以后输出更精简。",
            )
            proposal_id = prop["proposal_id"]

            with TestClient(app_mod.app) as client:
                listed = client.get("/teacher/memory/proposals", params={"teacher_id": teacher_id, "status": "proposed"})
                self.assertEqual(listed.status_code, 200)
                data = listed.json()
                self.assertTrue(data.get("ok"))
                self.assertTrue(any(p.get("proposal_id") == proposal_id for p in data.get("proposals") or []))

                review = client.post(
                    f"/teacher/memory/proposals/{proposal_id}/review",
                    json={"teacher_id": teacher_id, "approve": False},
                )
                self.assertEqual(review.status_code, 200)
                self.assertEqual(review.json().get("status"), "rejected")

                listed_rejected = client.get(
                    "/teacher/memory/proposals",
                    params={"teacher_id": teacher_id, "status": "rejected"},
                )
                self.assertEqual(listed_rejected.status_code, 200)
                self.assertTrue(any(p.get("proposal_id") == proposal_id for p in listed_rejected.json().get("proposals") or []))

    def test_default_auto_apply_lists_applied(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td), auto_apply_enabled=True)
            teacher_id = app_mod.resolve_teacher_id("teacher")
            prop = app_mod.teacher_memory_propose(
                teacher_id,
                target="MEMORY",
                title="偏好B",
                content="默认按结论-行动项格式输出。",
            )
            proposal_id = prop["proposal_id"]
            self.assertEqual(prop.get("status"), "applied")

            with TestClient(app_mod.app) as client:
                listed = client.get("/teacher/memory/proposals", params={"teacher_id": teacher_id, "status": "applied"})
                self.assertEqual(listed.status_code, 200)
                data = listed.json()
                self.assertTrue(data.get("ok"))
                self.assertTrue(any(p.get("proposal_id") == proposal_id for p in data.get("proposals") or []))

                review = client.post(
                    f"/teacher/memory/proposals/{proposal_id}/review",
                    json={"teacher_id": teacher_id, "approve": True},
                )
                self.assertEqual(review.status_code, 200)
                self.assertEqual(review.json().get("status"), "applied")

    def test_invalid_status_returns_400(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            with TestClient(app_mod.app) as client:
                res = client.get("/teacher/memory/proposals", params={"status": "bad_status"})
                self.assertEqual(res.status_code, 400)


if __name__ == "__main__":
    unittest.main()
