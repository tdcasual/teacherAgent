import json
import threading
import unittest
from collections import deque
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.assignment_upload_job_service import (
    AssignmentUploadJobDeps,
    enqueue_upload_job,
    load_upload_job,
    scan_pending_upload_jobs,
    upload_job_path,
    upload_job_worker_step,
    write_upload_job,
)


class AssignmentUploadJobServiceTest(unittest.TestCase):
    def _deps(self, root: Path, process_upload_job):  # type: ignore[no-untyped-def]
        return AssignmentUploadJobDeps(
            upload_job_dir=root / "upload_jobs",
            now_iso=lambda: "2026-02-08T12:00:00",
            atomic_write_json=lambda path, data: path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8"),
            queue=deque(),
            lock=threading.Lock(),
            event=threading.Event(),
            process_upload_job=process_upload_job,
            diag_log=lambda event, payload=None: None,
            sleep=lambda sec: None,
        )

    def test_write_and_load_roundtrip(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            deps = self._deps(root, process_upload_job=lambda _job_id: None)
            write_upload_job("job-1", {"job_id": "job-1", "status": "queued"}, deps=deps)
            data = load_upload_job("job-1", deps=deps)
            self.assertEqual(data.get("job_id"), "job-1")
            self.assertEqual(data.get("status"), "queued")
            self.assertEqual(data.get("updated_at"), "2026-02-08T12:00:00")
            self.assertEqual(upload_job_path("job/1", deps=deps).name, "job_1")

    def test_scan_pending_enqueues_jobs(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            deps = self._deps(root, process_upload_job=lambda _job_id: None)
            write_upload_job("job-a", {"job_id": "job-a", "status": "queued"}, deps=deps)
            write_upload_job("job-b", {"job_id": "job-b", "status": "processing"}, deps=deps)
            write_upload_job("job-c", {"job_id": "job-c", "status": "done"}, deps=deps)
            scan_pending_upload_jobs(deps)
            self.assertEqual(set(deps.queue), {"job-a", "job-b"})
            self.assertTrue(deps.event.is_set())

    def test_worker_step_marks_failed_when_exception(self):
        with TemporaryDirectory() as td:
            root = Path(td)

            def crash(_job_id):  # type: ignore[no-untyped-def]
                raise RuntimeError("boom")

            deps = self._deps(root, process_upload_job=crash)
            write_upload_job("job-x", {"job_id": "job-x", "status": "queued"}, deps=deps)
            enqueue_upload_job("job-x", deps=deps)
            worked = upload_job_worker_step(deps)
            self.assertTrue(worked)
            data = load_upload_job("job-x", deps=deps)
            self.assertEqual(data.get("status"), "failed")
            self.assertIn("boom", str(data.get("error") or ""))


if __name__ == "__main__":
    unittest.main()
