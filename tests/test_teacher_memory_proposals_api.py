import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from tests.helpers.app_factory import create_test_app


def load_app(tmp_dir: Path, *, auto_apply_enabled: bool | None = None):
    env_overrides = {}
    env_unset: list[str] = []
    if auto_apply_enabled is not None:
        env_overrides["TEACHER_MEMORY_AUTO_APPLY_ENABLED"] = "1" if auto_apply_enabled else "0"
    else:
        env_unset.append("TEACHER_MEMORY_AUTO_APPLY_ENABLED")
    return create_test_app(
        tmp_dir,
        env_overrides=env_overrides,
        env_unset=env_unset,
        reset_modules=True,
    )


class TeacherMemoryProposalsApiTest(unittest.TestCase):
    def test_proposals_endpoint_uses_teacher_memory_list_proposals(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td), auto_apply_enabled=False)
            captured = {}

            def fake_list(teacher_id, *, status, limit):  # type: ignore[no-untyped-def]
                captured["teacher_id"] = teacher_id
                captured["status"] = status
                captured["limit"] = limit
                return {"ok": True, "proposals": []}

            app_mod.get_core().teacher_memory_list_proposals = fake_list  # type: ignore[attr-defined]

            with TestClient(app_mod.app) as client:
                listed = client.get(
                    "/teacher/memory/proposals",
                    params={"teacher_id": "teacher_x", "status": "proposed", "limit": 7},
                )
                self.assertEqual(listed.status_code, 200)
                self.assertEqual(captured.get("teacher_id"), "teacher_x")
                self.assertEqual(captured.get("status"), "proposed")
                self.assertEqual(captured.get("limit"), 7)

    def test_review_endpoint_uses_teacher_memory_apply(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td), auto_apply_enabled=False)
            captured = {}

            def fake_review(teacher_id, proposal_id, approve=True):  # type: ignore[no-untyped-def]
                captured["proposal_id"] = proposal_id
                captured["teacher_id"] = teacher_id
                captured["approve"] = approve
                return {"ok": True, "status": "applied"}

            app_mod.get_core().teacher_memory_apply = fake_review  # type: ignore[attr-defined]

            with TestClient(app_mod.app) as client:
                review = client.post(
                    "/teacher/memory/proposals/p123/review",
                    json={"teacher_id": "teacher_y", "approve": True},
                )
                self.assertEqual(review.status_code, 200)
                self.assertEqual(captured.get("proposal_id"), "p123")
                self.assertEqual(captured.get("teacher_id"), "teacher_y")
                self.assertTrue(captured.get("approve"))

    def test_delete_endpoint_uses_teacher_memory_delete_proposal(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td), auto_apply_enabled=False)
            captured = {}

            def fake_delete(teacher_id, proposal_id):  # type: ignore[no-untyped-def]
                captured["proposal_id"] = proposal_id
                captured["teacher_id"] = teacher_id
                return {"ok": True, "status": "deleted"}

            app_mod.get_core().teacher_memory_delete_proposal = fake_delete  # type: ignore[attr-defined]

            with TestClient(app_mod.app) as client:
                deleted = client.delete(
                    "/teacher/memory/proposals/p123",
                    params={"teacher_id": "teacher_y"},
                )
                self.assertEqual(deleted.status_code, 200)
                self.assertEqual(captured.get("proposal_id"), "p123")
                self.assertEqual(captured.get("teacher_id"), "teacher_y")

    def test_list_and_review_proposals_when_manual_mode(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td), auto_apply_enabled=False)
            teacher_id = app_mod.get_core().resolve_teacher_id("teacher")
            prop = app_mod.get_core().teacher_memory_propose(
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
                proposal = next(p for p in data.get("proposals") or [] if p.get("proposal_id") == proposal_id)
                self.assertEqual((proposal.get("provenance") or {}).get("layer"), "memory_proposal")
                self.assertEqual((proposal.get("provenance") or {}).get("source"), "manual")

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

    def test_default_mode_keeps_proposal_unapplied_and_exposes_provenance(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td), auto_apply_enabled=None)
            teacher_id = app_mod.get_core().resolve_teacher_id("teacher")
            prop = app_mod.get_core().teacher_memory_propose(
                teacher_id,
                target="MEMORY",
                title="偏好默认安全",
                content="默认先给结论。",
            )
            proposal_id = prop["proposal_id"]
            self.assertEqual((prop.get("proposal") or {}).get("status"), "proposed")

            with TestClient(app_mod.app) as client:
                listed = client.get("/teacher/memory/proposals", params={"teacher_id": teacher_id, "status": "proposed"})
                self.assertEqual(listed.status_code, 200)
                proposals = listed.json().get("proposals") or []
                proposal = next(p for p in proposals if p.get("proposal_id") == proposal_id)
                self.assertEqual(proposal.get("status"), "proposed")
                self.assertEqual((proposal.get("provenance") or {}).get("layer"), "memory_proposal")
                self.assertEqual((proposal.get("provenance") or {}).get("source"), "manual")

    def test_default_auto_apply_lists_applied(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td), auto_apply_enabled=True)
            teacher_id = app_mod.get_core().resolve_teacher_id("teacher")
            prop = app_mod.get_core().teacher_memory_propose(
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

    def test_delete_applied_proposal_hides_it_from_list(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td), auto_apply_enabled=True)
            teacher_id = app_mod.get_core().resolve_teacher_id("teacher")
            prop = app_mod.get_core().teacher_memory_propose(
                teacher_id,
                target="MEMORY",
                title="偏好C",
                content="请先给结论再给步骤。",
            )
            proposal_id = prop["proposal_id"]
            self.assertEqual(prop.get("status"), "applied")

            with TestClient(app_mod.app) as client:
                before = client.get("/teacher/memory/proposals", params={"teacher_id": teacher_id, "status": "applied"})
                self.assertEqual(before.status_code, 200)
                self.assertTrue(any(p.get("proposal_id") == proposal_id for p in before.json().get("proposals") or []))

                deleted = client.delete(
                    f"/teacher/memory/proposals/{proposal_id}",
                    params={"teacher_id": teacher_id},
                )
                self.assertEqual(deleted.status_code, 200)
                self.assertEqual(deleted.json().get("status"), "deleted")
                memory_path = app_mod.get_core().teacher_workspace_file(teacher_id, "MEMORY.md")
                memory_text = memory_path.read_text(encoding="utf-8")
                self.assertNotIn(f"- entry_id: {proposal_id}", memory_text)
                self.assertNotIn("请先给结论再给步骤。", memory_text)

                after = client.get("/teacher/memory/proposals", params={"teacher_id": teacher_id, "status": "applied"})
                self.assertEqual(after.status_code, 200)
                self.assertFalse(any(p.get("proposal_id") == proposal_id for p in after.json().get("proposals") or []))

    def test_invalid_status_returns_400(self):
        with TemporaryDirectory() as td:
            app_mod = load_app(Path(td))
            with TestClient(app_mod.app) as client:
                res = client.get("/teacher/memory/proposals", params={"status": "bad_status"})
                self.assertEqual(res.status_code, 400)


if __name__ == "__main__":
    unittest.main()
