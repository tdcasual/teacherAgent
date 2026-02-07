import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.assignment_upload_draft_service import (
    assignment_upload_not_ready_detail,
    build_assignment_upload_draft,
    load_assignment_draft_override,
)
from services.api.assignment_upload_query_service import (
    AssignmentUploadQueryDeps,
    AssignmentUploadQueryError,
    get_assignment_upload_draft,
    get_assignment_upload_status,
)


class AssignmentUploadQueryServiceTest(unittest.TestCase):
    def _deps(self, root: Path):  # type: ignore[no-untyped-def]
        def load_upload_job(job_id):  # type: ignore[no-untyped-def]
            path = root / "uploads" / "assignment_jobs" / job_id / "job.json"
            if not path.exists():
                raise FileNotFoundError("job not found")
            return json.loads(path.read_text(encoding="utf-8"))

        return AssignmentUploadQueryDeps(
            load_upload_job=load_upload_job,
            upload_job_path=lambda job_id: root / "uploads" / "assignment_jobs" / job_id,
            assignment_upload_not_ready_detail=assignment_upload_not_ready_detail,
            load_assignment_draft_override=load_assignment_draft_override,
            build_assignment_upload_draft=build_assignment_upload_draft,
            merge_requirements=lambda base, update, overwrite=True: {**(base or {}), **(update or {})},
            compute_requirements_missing=lambda req: [] if req.get("topic") else ["topic"],
            parse_list_value=lambda value: value if isinstance(value, list) else [],
        )

    def test_status_job_not_found_raises_404(self):
        with TemporaryDirectory() as td:
            deps = self._deps(Path(td))
            with self.assertRaises(AssignmentUploadQueryError) as cm:
                get_assignment_upload_status("job-404", deps=deps)
            self.assertEqual(cm.exception.status_code, 404)
            self.assertEqual(cm.exception.detail, "job not found")

    def test_status_returns_job_payload(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            job_dir = root / "uploads" / "assignment_jobs" / "job-1"
            job_dir.mkdir(parents=True, exist_ok=True)
            payload = {"job_id": "job-1", "status": "done", "progress": 100}
            (job_dir / "job.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            deps = self._deps(root)
            result = get_assignment_upload_status("job-1", deps=deps)
            self.assertEqual(result, payload)

    def test_draft_not_ready_raises_400_detail(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            job_dir = root / "uploads" / "assignment_jobs" / "job-2"
            job_dir.mkdir(parents=True, exist_ok=True)
            (job_dir / "job.json").write_text(
                json.dumps({"job_id": "job-2", "status": "processing", "step": "ocr", "progress": 35}, ensure_ascii=False),
                encoding="utf-8",
            )
            deps = self._deps(root)
            with self.assertRaises(AssignmentUploadQueryError) as cm:
                get_assignment_upload_draft("job-2", deps=deps)
            self.assertEqual(cm.exception.status_code, 400)
            self.assertEqual(cm.exception.detail.get("error"), "job_not_ready")

    def test_draft_success_builds_draft(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            job_dir = root / "uploads" / "assignment_jobs" / "job-3"
            job_dir.mkdir(parents=True, exist_ok=True)
            (job_dir / "job.json").write_text(
                json.dumps(
                    {
                        "job_id": "job-3",
                        "assignment_id": "HW_3",
                        "status": "done",
                        "scope": "class",
                        "class_name": "高二2403班",
                        "student_ids": [],
                        "source_files": ["paper.pdf"],
                        "answer_files": [],
                        "delivery_mode": "pdf",
                        "draft_version": 1,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (job_dir / "parsed.json").write_text(
                json.dumps(
                    {
                        "questions": [{"stem": "q1"}],
                        "requirements": {"subject": "物理", "topic": "欧姆定律"},
                        "warnings": [],
                        "delivery_mode": "pdf",
                        "autofilled": False,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            deps = self._deps(root)
            result = get_assignment_upload_draft("job-3", deps=deps)
            self.assertEqual(result.get("ok"), True)
            self.assertEqual(result.get("draft", {}).get("assignment_id"), "HW_3")
            self.assertEqual(result.get("draft", {}).get("question_count"), 1)


if __name__ == "__main__":
    unittest.main()
