from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.assignment_archive_service import (
    AssignmentArchiveError,
    archive_assignment,
    maybe_auto_archive,
    publish_assignment,
    unarchive_assignment,
)
from services.api.assignment_upload_confirm_service import AssignmentUploadConfirmDeps
from services.api.auth_service import AuthPrincipal, reset_current_principal, set_current_principal


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
    def _finalize_deps(self, root: Path) -> AssignmentUploadConfirmDeps:
        def _write_json(path: Path, payload: dict) -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        return AssignmentUploadConfirmDeps(
            data_dir=root,
            now_iso=lambda: "2026-08-28T12:00:00",
            discussion_complete_marker="[[discussion_complete]]",
            write_upload_job=lambda *_a, **_k: {},
            merge_requirements=lambda base, override, overwrite=True: {**(base or {}), **(override or {})},
            compute_requirements_missing=lambda req, **_k: [] if req.get("subject") else ["subject"],
            write_uploaded_questions=lambda *_a, **_k: [],
            optional_assignment_date=lambda value: str(value or "").strip() or None,
            save_assignment_requirements=lambda *_a, **_k: None,
            parse_ids_value=lambda value: value if isinstance(value, list) else [],
            resolve_scope=lambda scope, _s, _c: str(scope or "") or "public",
            normalize_due_at=lambda value: str(value or ""),
            compute_expected_students=lambda *_a, **_k: ["S1"],
            atomic_write_json=_write_json,
            copy2=lambda src, dst: dst.write_bytes(src.read_bytes()) if src.exists() else None,
        )

    def test_owner_can_publish_draft(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            folder = _write_meta(root, "HW_DRAFT", {**_META, "visibility_status": "draft"})
            (folder / "requirements.json").write_text(
                json.dumps({"subject": "物理", "topic": "电", "grade_level": "初二"}, ensure_ascii=False),
                encoding="utf-8",
            )
            (folder / "questions.csv").write_text(
                "question_id,kp_id,difficulty,type,stem_ref,answer_ref,source,tags\nQ1,k,basic,open,,,,\n",
                encoding="utf-8",
            )
            token = set_current_principal(_owner())
            try:
                published = publish_assignment(
                    "HW_DRAFT",
                    principal=_owner(),
                    data_dir=root,
                    finalize_deps=self._finalize_deps(root),
                )
            finally:
                reset_current_principal(token)
            self.assertEqual(published["visibility_status"], "published")
            meta = _read_meta(root, "HW_DRAFT")
            self.assertEqual(meta["visibility_status"], "published")
            self.assertTrue(str(meta.get("published_at") or "").strip())

    def test_assignment_publish_runs_kind_gated_requirements(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            _write_meta(
                root,
                "HW_SCENARIO",
                {
                    **_META,
                    "visibility_status": "draft",
                    "assignment_kind": "scenario",
                    "content_source": "ai",
                },
            )
            token = set_current_principal(_owner())
            try:
                with self.assertRaises(AssignmentArchiveError) as ctx:
                    publish_assignment(
                        "HW_SCENARIO",
                        principal=_owner(),
                        data_dir=root,
                    )
            finally:
                reset_current_principal(token)
            self.assertEqual(ctx.exception.status_code, 400)
            detail = ctx.exception.detail
            if isinstance(detail, dict):
                self.assertEqual(detail.get("error"), "requirements_missing")
                self.assertIn("brief", detail.get("missing") or [])
            else:
                self.assertIn("requirements_missing", str(detail))

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
