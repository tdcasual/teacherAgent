import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.assignment_upload_confirm_service import (
    AssignmentUploadConfirmDeps,
    AssignmentUploadConfirmError,
    confirm_assignment_upload,
)


class AssignmentUploadConfirmServiceTest(unittest.TestCase):
    def _deps(self, root: Path, writes: list):  # type: ignore[no-untyped-def]
        def write_upload_job(job_id, updates):  # type: ignore[no-untyped-def]
            writes.append((job_id, dict(updates)))
            return updates

        return AssignmentUploadConfirmDeps(
            data_dir=root / "data",
            now_iso=lambda: "2026-02-08T12:00:00",
            discussion_complete_marker="[[discussion_complete]]",
            write_upload_job=write_upload_job,
            merge_requirements=lambda base, override, overwrite=True: {**(base or {}), **(override or {})},
            compute_requirements_missing=lambda req: [] if req.get("subject") else ["subject"],
            write_uploaded_questions=lambda _out, _aid, _questions: [{"question_id": "Q1"}],
            parse_date_str=lambda v: str(v or ""),
            save_assignment_requirements=lambda *_args, **_kwargs: None,
            parse_ids_value=lambda value: value if isinstance(value, list) else [],
            resolve_scope=lambda scope, _student_ids, _class_name: str(scope or ""),
            normalize_due_at=lambda value: str(value or ""),
            compute_expected_students=lambda _scope, _class_name, _student_ids: [],
            atomic_write_json=lambda path, data: path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8"),
            copy2=lambda src, dst: dst.write_bytes(src.read_bytes()),
        )

    def test_missing_parsed_marks_failed_and_raises(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            writes = []
            job_dir = root / "uploads" / "assignment_jobs" / "job-1"
            job_dir.mkdir(parents=True, exist_ok=True)
            deps = self._deps(root, writes)
            with self.assertRaises(AssignmentUploadConfirmError) as ctx:
                confirm_assignment_upload(
                    "job-1",
                    {"assignment_id": "A1", "status": "done"},
                    job_dir,
                    requirements_override=None,
                    strict_requirements=True,
                    deps=deps,
                )
            self.assertEqual(ctx.exception.status_code, 400)
            self.assertEqual(ctx.exception.detail, "parsed result missing")
            self.assertEqual(writes[-1][1].get("status"), "failed")

    def test_strict_missing_requirements_raises(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            writes = []
            job_dir = root / "uploads" / "assignment_jobs" / "job-1"
            job_dir.mkdir(parents=True, exist_ok=True)
            parsed = {"questions": [{"stem": "x"}], "requirements": {}, "missing": ["subject"], "warnings": []}
            (job_dir / "parsed.json").write_text(json.dumps(parsed, ensure_ascii=False), encoding="utf-8")
            deps = self._deps(root, writes)
            with self.assertRaises(AssignmentUploadConfirmError) as ctx:
                confirm_assignment_upload(
                    "job-1",
                    {"assignment_id": "A1", "status": "done"},
                    job_dir,
                    requirements_override=None,
                    strict_requirements=True,
                    deps=deps,
                )
            self.assertEqual(ctx.exception.status_code, 400)
            self.assertEqual(ctx.exception.detail.get("error"), "requirements_missing")

    def test_success_writes_meta_and_returns_ok(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            writes = []
            job_dir = root / "uploads" / "assignment_jobs" / "job-1"
            (job_dir / "source").mkdir(parents=True, exist_ok=True)
            (job_dir / "answer_source").mkdir(parents=True, exist_ok=True)
            (job_dir / "parsed.json").write_text(
                json.dumps(
                    {
                        "questions": [{"stem": "x"}],
                        "requirements": {"subject": "物理"},
                        "missing": [],
                        "warnings": ["w1"],
                        "delivery_mode": "pdf",
                        "autofilled": False,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            deps = self._deps(root, writes)
            result = confirm_assignment_upload(
                "job-1",
                {
                    "assignment_id": "A1",
                    "status": "done",
                    "scope": "class",
                    "class_name": "高二2403班",
                    "student_ids": [],
                    "date": "2026-02-08",
                },
                job_dir,
                requirements_override=None,
                strict_requirements=True,
                deps=deps,
            )
            self.assertTrue(result.get("ok"))
            self.assertEqual(result.get("assignment_id"), "A1")
            meta_path = root / "data" / "assignments" / "A1" / "meta.json"
            self.assertTrue(meta_path.exists())
            self.assertEqual(writes[-1][1].get("status"), "confirmed")

    def test_rejects_invalid_assignment_id_path(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            writes = []
            job_dir = root / "uploads" / "assignment_jobs" / "job-1"
            job_dir.mkdir(parents=True, exist_ok=True)
            (job_dir / "parsed.json").write_text(
                json.dumps({"questions": [{"stem": "x"}], "requirements": {"subject": "物理"}, "missing": [], "warnings": []}, ensure_ascii=False),
                encoding="utf-8",
            )
            deps = self._deps(root, writes)
            with self.assertRaises(AssignmentUploadConfirmError) as ctx:
                confirm_assignment_upload(
                    "job-1",
                    {"assignment_id": "../escape", "status": "done"},
                    job_dir,
                    requirements_override=None,
                    strict_requirements=True,
                    deps=deps,
                )
            self.assertEqual(ctx.exception.status_code, 400)
            self.assertEqual(ctx.exception.detail, "invalid assignment_id")
            self.assertEqual(writes[-1][1].get("status"), "failed")


if __name__ == "__main__":
    unittest.main()
