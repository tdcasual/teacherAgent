import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.assignment_upload_parse_service import AssignmentUploadParseDeps, process_upload_job


class AssignmentUploadParseServiceTest(unittest.TestCase):
    def _deps(  # type: ignore[no-untyped-def]
        self,
        root: Path,
        job: dict,
        writes: list,
        *,
        extract_text_from_file=None,
        llm_parse_assignment_payload=None,
        compute_requirements_missing=None,
        llm_autofill_requirements=None,
    ):
        job_dir = root / "assignment_jobs" / "job-1"
        (job_dir / "source").mkdir(parents=True, exist_ok=True)
        (job_dir / "answer_source").mkdir(parents=True, exist_ok=True)

        def write_upload_job(job_id, updates):  # type: ignore[no-untyped-def]
            writes.append((job_id, dict(updates)))
            return updates

        return AssignmentUploadParseDeps(
            now_iso=lambda: "2026-02-08T12:00:00",
            now_monotonic=lambda: 1.0,
            load_upload_job=lambda _job_id: dict(job),
            upload_job_path=lambda _job_id: job_dir,
            write_upload_job=write_upload_job,
            extract_text_from_file=extract_text_from_file or (lambda _path, language="zh", ocr_mode="FREE_OCR": "文本"),
            llm_parse_assignment_payload=llm_parse_assignment_payload
            or (lambda _source_text, _answer_text: {"questions": [{"stem": "Q1"}], "requirements": {"subject": "物理"}}),
            compute_requirements_missing=compute_requirements_missing or (lambda _req: []),
            llm_autofill_requirements=llm_autofill_requirements
            or (lambda _s, _a, _q, req, missing: (req, missing, False)),
            diag_log=lambda _event, _payload=None: None,
        )

    def test_no_source_files_marks_failed(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            writes = []
            deps = self._deps(root, {"source_files": [], "answer_files": []}, writes)
            process_upload_job("job-1", deps)
            self.assertTrue(writes)
            self.assertEqual(writes[-1][1].get("status"), "failed")
            self.assertEqual(writes[-1][1].get("error"), "no source files")

    def test_source_text_empty_marks_failed(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            writes = []
            job = {"source_files": ["paper.pdf"], "answer_files": []}
            deps = self._deps(
                root,
                job,
                writes,
                extract_text_from_file=lambda _path, language="zh", ocr_mode="FREE_OCR": "",
            )
            process_upload_job("job-1", deps)
            self.assertEqual(writes[-1][1].get("status"), "failed")
            self.assertEqual(writes[-1][1].get("error"), "source_text_empty")

    def test_parse_error_marks_failed(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            writes = []
            job = {"source_files": ["paper.pdf"], "answer_files": []}
            deps = self._deps(
                root,
                job,
                writes,
                llm_parse_assignment_payload=lambda _source_text, _answer_text: {"error": "parse_failed"},
            )
            process_upload_job("job-1", deps)
            self.assertEqual(writes[-1][1].get("status"), "failed")
            self.assertEqual(writes[-1][1].get("error"), "parse_failed")

    def test_success_writes_parsed_and_done_status(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            writes = []
            job = {"source_files": ["paper.pdf"], "answer_files": []}
            deps = self._deps(
                root,
                job,
                writes,
                llm_parse_assignment_payload=lambda _source_text, _answer_text: {
                    "questions": [{"stem": "Q1"}],
                    "requirements": {},
                },
                compute_requirements_missing=lambda req: [] if req.get("subject") else ["subject"],
                llm_autofill_requirements=lambda _s, _a, _q, req, missing: (
                    {**req, "subject": "物理"},
                    [],
                    True,
                ),
            )
            process_upload_job("job-1", deps)
            self.assertEqual(writes[-1][1].get("status"), "done")
            self.assertTrue(bool(writes[-1][1].get("autofilled")))
            parsed_path = root / "assignment_jobs" / "job-1" / "parsed.json"
            self.assertTrue(parsed_path.exists())
            payload = json.loads(parsed_path.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("requirements", {}).get("subject"), "物理")


if __name__ == "__main__":
    unittest.main()
