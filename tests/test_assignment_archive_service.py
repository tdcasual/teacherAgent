from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.assignment_archive_service import (
    AssignmentArchiveError,
    archive_assignment,
    maybe_auto_archive,
    unarchive_assignment,
)
from services.api.auth_service import AuthPrincipal


def _write_meta(root: Path, assignment_id: str, meta: dict) -> Path:
    folder = root / "assignments" / assignment_id
    folder.mkdir(parents=True, exist_ok=True)
    payload = {"assignment_id": assignment_id, **meta}
    (folder / "meta.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return folder


def _read_meta(root: Path, assignment_id: str) -> dict:
    return json.loads((root / "assignments" / assignment_id / "meta.json").read_text(encoding="utf-8"))


def _owner() -> AuthPrincipal:
    return AuthPrincipal(actor_id="t_zhang", role="teacher")


_META = {
    "visibility_status": "published",
    "teacher_id": "t_zhang",
    "subject_id": "physics",
    "expected_students": ["S1"],
    "due_at": "2026-08-20T18:00:00",
    "archived_at": None,
}


class AssignmentArchiveServiceTests(unittest.TestCase):
    def test_owner_can_archive_and_unarchive(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            _write_meta(root, "HW_1", _META)
            archived = archive_assignment("HW_1", principal=_owner(), data_dir=root)
            self.assertEqual(archived["visibility_status"], "archived")
            meta = _read_meta(root, "HW_1")
            self.assertEqual(meta["visibility_status"], "archived")
            self.assertTrue(str(meta.get("archived_at") or "").strip())

            restored = unarchive_assignment("HW_1", principal=_owner(), data_dir=root)
            self.assertEqual(restored["visibility_status"], "published")
            meta = _read_meta(root, "HW_1")
            self.assertEqual(meta["visibility_status"], "published")
            self.assertFalse(meta.get("archived_at"))
            self.assertTrue(str(meta.get("auto_archive_exempt_until") or "").strip())

    def test_non_owner_cannot_archive(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            _write_meta(root, "HW_1", _META)
            with self.assertRaises(AssignmentArchiveError) as ctx:
                archive_assignment(
                    "HW_1",
                    principal=AuthPrincipal(actor_id="t_li", role="teacher"),
                    data_dir=root,
                )
            self.assertEqual(ctx.exception.status_code, 403)

    def test_auto_archive_when_all_submitted_and_due_passed(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            _write_meta(root, "HW_1", {**_META, "expected_students": ["S1", "S2"]})
            attempts = {
                ("HW_1", "S1"): [{"valid_submission": True, "submitted_at": "2026-08-20T10:00:00"}],
                ("HW_1", "S2"): [{"valid_submission": True, "submitted_at": "2026-08-21T10:00:00"}],
            }
            changed = maybe_auto_archive(
                "HW_1",
                data_dir=root,
                today_iso="2026-08-28",
                auto_archive_days=7,
                list_submission_attempts=lambda aid, sid: attempts.get((aid, sid), []),
            )
            self.assertTrue(changed)
            self.assertEqual(_read_meta(root, "HW_1")["visibility_status"], "archived")

    def test_auto_archive_skips_when_someone_unsubmitted(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            _write_meta(root, "HW_1", {**_META, "expected_students": ["S1", "S2"]})
            attempts = {
                ("HW_1", "S1"): [{"valid_submission": True, "submitted_at": "2026-08-20T10:00:00"}],
            }
            changed = maybe_auto_archive(
                "HW_1",
                data_dir=root,
                today_iso="2026-08-28",
                auto_archive_days=7,
                list_submission_attempts=lambda aid, sid: attempts.get((aid, sid), []),
            )
            self.assertFalse(changed)
            self.assertEqual(_read_meta(root, "HW_1")["visibility_status"], "published")

    def test_auto_archive_skips_other_teachers_assignment(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            _write_meta(root, "HW_1", {**_META, "expected_students": ["S1"]})
            attempts = {
                ("HW_1", "S1"): [{"valid_submission": True, "submitted_at": "2026-08-20T10:00:00"}],
            }
            changed = maybe_auto_archive(
                "HW_1",
                data_dir=root,
                today_iso="2026-08-28",
                auto_archive_days=7,
                owner_teacher_id="t_li",
                list_submission_attempts=lambda aid, sid: attempts.get((aid, sid), []),
            )
            self.assertFalse(changed)
            self.assertEqual(_read_meta(root, "HW_1")["visibility_status"], "published")

    def test_auto_archive_skips_exempt_after_unarchive(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            _write_meta(root, "HW_1", {**_META, "auto_archive_exempt_until": "2026-08-29"})
            attempts = {
                ("HW_1", "S1"): [{"valid_submission": True, "submitted_at": "2026-08-20T10:00:00"}],
            }
            changed = maybe_auto_archive(
                "HW_1",
                data_dir=root,
                today_iso="2026-08-28",
                auto_archive_days=7,
                list_submission_attempts=lambda aid, sid: attempts.get((aid, sid), []),
            )
            self.assertFalse(changed)
            self.assertEqual(_read_meta(root, "HW_1")["visibility_status"], "published")

    def test_auto_archive_resumes_after_exempt_until(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            _write_meta(root, "HW_1", {**_META, "auto_archive_exempt_until": "2026-08-21"})
            attempts = {
                ("HW_1", "S1"): [{"valid_submission": True, "submitted_at": "2026-08-20T10:00:00"}],
            }
            changed = maybe_auto_archive(
                "HW_1",
                data_dir=root,
                today_iso="2026-08-28",
                auto_archive_days=7,
                list_submission_attempts=lambda aid, sid: attempts.get((aid, sid), []),
            )
            self.assertTrue(changed)
            self.assertEqual(_read_meta(root, "HW_1")["visibility_status"], "archived")

    def test_auto_archive_latest_date_ignores_invalid_attempts(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            _write_meta(root, "HW_1", _META)
            attempts = {
                ("HW_1", "S1"): [
                    {"valid_submission": True, "submitted_at": "2026-08-20T10:00:00"},
                    {"valid_submission": False, "submitted_at": "2026-08-28T10:00:00"},
                ],
            }
            changed = maybe_auto_archive(
                "HW_1",
                data_dir=root,
                today_iso="2026-08-28",
                auto_archive_days=7,
                list_submission_attempts=lambda aid, sid: attempts.get((aid, sid), []),
            )
            self.assertTrue(changed)

    def test_auto_archive_fail_open_on_corrupt_meta(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            folder = root / "assignments" / "HW_BAD"
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "meta.json").write_text("{not-json", encoding="utf-8")
            changed = maybe_auto_archive(
                "HW_BAD",
                data_dir=root,
                today_iso="2026-08-28",
                auto_archive_days=7,
                list_submission_attempts=lambda *_args, **_kwargs: [],
            )
            self.assertFalse(changed)


if __name__ == "__main__":
    unittest.main()
