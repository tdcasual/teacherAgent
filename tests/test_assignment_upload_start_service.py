import asyncio
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.assignment_upload_start_service import (
    AssignmentUploadStartDeps,
    AssignmentUploadStartError,
    start_assignment_upload,
)


class _FakeUpload:
    def __init__(self, filename: str):
        self.filename = filename


class AssignmentUploadStartServiceTest(unittest.TestCase):
    def _deps(self, root: Path):  # type: ignore[no-untyped-def]
        writes = {}
        queued = []
        logs = []

        async def save_upload_file(upload, dest):  # type: ignore[no-untyped-def]
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(f"from:{upload.filename}", encoding="utf-8")
            return len(upload.filename)

        deps = AssignmentUploadStartDeps(
            new_job_id=lambda: "job_fixed_001",
            parse_date_str=lambda value: str(value or "2026-02-08"),
            upload_job_path=lambda job_id: root / "assignment_jobs" / job_id,
            sanitize_filename=lambda name: str(name or "").strip(),
            save_upload_file=save_upload_file,
            parse_ids_value=lambda value: [item.strip() for item in str(value or "").split(",") if item.strip()],
            resolve_scope=lambda scope, student_ids, class_name: str(scope or "public"),
            normalize_due_at=lambda value: str(value or ""),
            now_iso=lambda: "2026-02-08T12:00:00",
            write_upload_job=lambda job_id, updates, overwrite=False: writes.setdefault(job_id, {**updates, "_overwrite": overwrite}),
            enqueue_upload_job=lambda job_id: queued.append(job_id),
            diag_log=lambda event, payload=None: logs.append((event, payload or {})),
        )
        return deps, writes, queued, logs

    def test_start_upload_creates_job_and_enqueues(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            deps, writes, queued, logs = self._deps(root)

            result = asyncio.run(
                start_assignment_upload(
                    assignment_id="HW_1",
                    date="2026-02-08",
                    due_at="2026-02-09T20:00:00",
                    scope="class",
                    class_name="高二2403班",
                    student_ids="",
                    files=[_FakeUpload("paper.pdf")],
                    answer_files=[_FakeUpload("answer.pdf")],
                    ocr_mode="FREE_OCR",
                    language="zh",
                    deps=deps,
                )
            )

            self.assertEqual(result.get("ok"), True)
            self.assertEqual(result.get("job_id"), "job_fixed_001")
            self.assertEqual(queued, ["job_fixed_001"])
            self.assertIn("job_fixed_001", writes)
            job = writes["job_fixed_001"]
            self.assertEqual(job.get("assignment_id"), "HW_1")
            self.assertEqual(job.get("status"), "queued")
            self.assertEqual(job.get("delivery_mode"), "pdf")
            self.assertEqual(job.get("_overwrite"), True)
            self.assertEqual(logs[0][0], "upload.job.created")

    def test_start_upload_requires_source_files(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            deps, _writes, _queued, _logs = self._deps(root)
            with self.assertRaises(AssignmentUploadStartError) as cm:
                asyncio.run(
                    start_assignment_upload(
                        assignment_id="HW_1",
                        date="2026-02-08",
                        due_at="",
                        scope="public",
                        class_name="",
                        student_ids="",
                        files=[_FakeUpload("   ")],
                        answer_files=None,
                        ocr_mode="FREE_OCR",
                        language="zh",
                        deps=deps,
                    )
                )
            self.assertEqual(cm.exception.status_code, 400)
            self.assertEqual(cm.exception.detail, "No source files uploaded")

    def test_student_scope_requires_student_ids(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            deps, _writes, _queued, _logs = self._deps(root)
            deps = AssignmentUploadStartDeps(
                **{**deps.__dict__, "resolve_scope": lambda scope, student_ids, class_name: "student"}
            )
            with self.assertRaises(AssignmentUploadStartError) as cm:
                asyncio.run(
                    start_assignment_upload(
                        assignment_id="HW_1",
                        date="2026-02-08",
                        due_at="",
                        scope="student",
                        class_name="",
                        student_ids="",
                        files=[_FakeUpload("paper.png")],
                        answer_files=None,
                        ocr_mode="FREE_OCR",
                        language="zh",
                        deps=deps,
                    )
                )
            self.assertEqual(cm.exception.status_code, 400)
            self.assertEqual(cm.exception.detail, "student scope requires student_ids")


if __name__ == "__main__":
    unittest.main()
