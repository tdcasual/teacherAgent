import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from services.api.exam_upload_parse_service import ExamUploadParseDeps, process_exam_upload_job


class ExamUploadParseServiceTest(unittest.TestCase):
    def _deps(self, root: Path, job: dict, writes: list):  # type: ignore[no-untyped-def]
        job_dir = root / "exam_jobs" / "job-1"
        (job_dir / "paper").mkdir(parents=True, exist_ok=True)
        (job_dir / "scores").mkdir(parents=True, exist_ok=True)
        (job_dir / "answers").mkdir(parents=True, exist_ok=True)
        (job_dir / "derived").mkdir(parents=True, exist_ok=True)

        def write_exam_job(job_id, updates):  # type: ignore[no-untyped-def]
            writes.append((job_id, dict(updates)))
            return updates

        def _unused(*_args, **_kwargs):  # type: ignore[no-untyped-def]
            return ""

        def _unused_rows(*_args, **_kwargs):  # type: ignore[no-untyped-def]
            return []

        return ExamUploadParseDeps(
            app_root=root,
            now_iso=lambda: "2026-02-08T12:00:00",
            now_date_compact=lambda: "20260208",
            load_exam_job=lambda _job_id: dict(job),
            exam_job_path=lambda _job_id: job_dir,
            write_exam_job=write_exam_job,
            extract_text_from_file=_unused,
            extract_text_from_pdf=_unused,
            extract_text_from_image=_unused,
            parse_xlsx_with_script=lambda _xlsx, _out, _exam_id, _class_name: [],
            xlsx_to_table_preview=_unused,
            xls_to_table_preview=_unused,
            llm_parse_exam_scores=lambda _text: {"rows": []},
            build_exam_rows_from_parsed_scores=lambda _exam_id, _parsed: ([], {}, []),
            parse_score_value=lambda _v: None,
            write_exam_responses_csv=lambda _p, _rows: None,
            parse_exam_answer_key_text=lambda _text: ([], []),
            write_exam_answers_csv=lambda _p, _rows: None,
            compute_max_scores_from_rows=lambda _rows: {},
            write_exam_questions_csv=lambda _p, _q, max_scores=None: None,
            apply_answer_key_to_responses_csv=lambda _a, _b, _c, _d: {},
            compute_exam_totals=lambda _p: {"totals": {}},
            copy2=lambda _a, _b: None,
            diag_log=lambda _event, _payload=None: None,
            parse_date_str=lambda _v: "",
        )

    def test_missing_paper_marks_failed(self):
        with TemporaryDirectory() as td:
            writes = []
            deps = self._deps(Path(td), {"exam_id": "EX1", "paper_files": [], "score_files": ["scores.xlsx"]}, writes)
            process_exam_upload_job("job-1", deps)
            self.assertTrue(writes)
            self.assertEqual(writes[-1][1].get("status"), "failed")
            self.assertEqual(writes[-1][1].get("error"), "no_paper_files")

    def test_missing_scores_marks_failed(self):
        with TemporaryDirectory() as td:
            writes = []
            deps = self._deps(Path(td), {"exam_id": "EX1", "paper_files": ["paper.pdf"], "score_files": []}, writes)
            process_exam_upload_job("job-1", deps)
            self.assertTrue(writes)
            self.assertEqual(writes[-1][1].get("status"), "failed")
            self.assertEqual(writes[-1][1].get("error"), "no_score_files")


if __name__ == "__main__":
    unittest.main()
