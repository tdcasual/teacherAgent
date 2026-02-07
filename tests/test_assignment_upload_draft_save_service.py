import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.assignment_upload_draft_save_service import (
    AssignmentUploadDraftSaveDeps,
    AssignmentUploadDraftSaveError,
    save_assignment_upload_draft,
)
from services.api.assignment_upload_draft_service import (
    assignment_upload_not_ready_detail,
    clean_assignment_draft_questions,
    save_assignment_draft_override,
)


class AssignmentUploadDraftSaveServiceTest(unittest.TestCase):
    def _deps(self, root: Path, writes: list):  # type: ignore[no-untyped-def]
        def load_upload_job(job_id):  # type: ignore[no-untyped-def]
            path = root / "uploads" / "assignment_jobs" / job_id / "job.json"
            if not path.exists():
                raise FileNotFoundError("job not found")
            return json.loads(path.read_text(encoding="utf-8"))

        def write_upload_job(job_id, updates):  # type: ignore[no-untyped-def]
            writes.append((job_id, dict(updates)))
            return updates

        return AssignmentUploadDraftSaveDeps(
            load_upload_job=load_upload_job,
            upload_job_path=lambda job_id: root / "uploads" / "assignment_jobs" / job_id,
            assignment_upload_not_ready_detail=assignment_upload_not_ready_detail,
            clean_assignment_draft_questions=clean_assignment_draft_questions,
            save_assignment_draft_override=save_assignment_draft_override,
            merge_requirements=lambda base, override, overwrite=True: {**(base or {}), **(override or {})},
            compute_requirements_missing=lambda req: [] if req.get("subject") else ["subject"],
            write_upload_job=write_upload_job,
            now_iso=lambda: "2026-02-08T12:00:00",
        )

    def test_job_not_found_raises_404(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            deps = self._deps(root, writes=[])
            with self.assertRaises(AssignmentUploadDraftSaveError) as cm:
                save_assignment_upload_draft("job-404", {"subject": "物理"}, [], deps=deps)
            self.assertEqual(cm.exception.status_code, 404)
            self.assertEqual(cm.exception.detail, "job not found")

    def test_not_ready_raises_400_detail(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            writes = []
            job_dir = root / "uploads" / "assignment_jobs" / "job-1"
            job_dir.mkdir(parents=True, exist_ok=True)
            (job_dir / "job.json").write_text(
                json.dumps({"job_id": "job-1", "status": "processing", "step": "ocr", "progress": 30}, ensure_ascii=False),
                encoding="utf-8",
            )
            deps = self._deps(root, writes=writes)
            with self.assertRaises(AssignmentUploadDraftSaveError) as cm:
                save_assignment_upload_draft("job-1", {"subject": "物理"}, [], deps=deps)
            self.assertEqual(cm.exception.status_code, 400)
            detail = cm.exception.detail
            self.assertEqual(detail.get("error"), "job_not_ready")
            self.assertEqual(detail.get("status"), "processing")
            self.assertEqual(len(writes), 0)

    def test_success_persists_override_and_updates_job(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            writes = []
            job_id = "job-2"
            job_dir = root / "uploads" / "assignment_jobs" / job_id
            job_dir.mkdir(parents=True, exist_ok=True)
            (job_dir / "job.json").write_text(
                json.dumps({"job_id": job_id, "status": "done"}, ensure_ascii=False),
                encoding="utf-8",
            )
            (job_dir / "parsed.json").write_text(
                json.dumps(
                    {
                        "questions": [{"stem": "q1"}],
                        "requirements": {"subject": ""},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            deps = self._deps(root, writes=writes)
            result = save_assignment_upload_draft(
                job_id,
                {"subject": "物理"},
                [{"stem": "  edited  ", "score": 5}],
                deps=deps,
            )
            self.assertTrue(result.get("ok"))
            self.assertEqual(result.get("requirements_missing"), [])
            override_path = job_dir / "draft_override.json"
            self.assertTrue(override_path.exists())
            override = json.loads(override_path.read_text(encoding="utf-8"))
            self.assertEqual(override.get("questions"), [{"stem": "edited", "score": 5}])
            self.assertEqual(writes[-1][1].get("draft_saved"), True)


if __name__ == "__main__":
    unittest.main()
