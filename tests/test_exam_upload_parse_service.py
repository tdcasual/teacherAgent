import unittest
import json
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
            parse_xlsx_with_script=lambda _xlsx, _out, _exam_id, _class_name: ([], {}),
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

    def test_subject_question_ids_set_subject_score_mode(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            writes = []
            job = {
                "exam_id": "EX_SUBJECT",
                "paper_files": ["paper.pdf"],
                "score_files": ["scores.xlsx"],
                "answer_files": [],
                "language": "zh",
                "ocr_mode": "FREE_OCR",
                "date": "2026-02-10",
                "class_name": "",
            }

            job_dir = root / "exam_jobs" / "job-1"
            (job_dir / "paper").mkdir(parents=True, exist_ok=True)
            (job_dir / "scores").mkdir(parents=True, exist_ok=True)
            (job_dir / "answers").mkdir(parents=True, exist_ok=True)
            (job_dir / "derived").mkdir(parents=True, exist_ok=True)
            (job_dir / "paper" / "paper.pdf").write_text("paper", encoding="utf-8")
            (job_dir / "scores" / "scores.xlsx").write_text("xlsx", encoding="utf-8")

            def write_exam_job(job_id, updates):  # type: ignore[no-untyped-def]
                writes.append((job_id, dict(updates)))
                return updates

            def parse_xlsx_with_script(_xlsx, _out, _exam_id, _class_name):  # type: ignore[no-untyped-def]
                return [
                    {
                        "exam_id": "EX_SUBJECT",
                        "student_id": "S1",
                        "student_name": "张三",
                        "class_name": "",
                        "question_id": "SUBJECT_PHYSICS",
                        "question_no": "",
                        "sub_no": "",
                        "raw_label": "物理",
                        "raw_value": "42",
                        "raw_answer": "",
                        "score": 42,
                        "is_correct": "",
                    }
                ], {}

            def write_exam_responses_csv(path, rows):  # type: ignore[no-untyped-def]
                import csv

                path.parent.mkdir(parents=True, exist_ok=True)
                fields = [
                    "exam_id",
                    "student_id",
                    "student_name",
                    "class_name",
                    "question_id",
                    "question_no",
                    "sub_no",
                    "raw_label",
                    "raw_value",
                    "raw_answer",
                    "score",
                    "is_correct",
                ]
                with path.open("w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=fields)
                    writer.writeheader()
                    for row in rows:
                        writer.writerow({k: row.get(k, "") for k in fields})

            def write_exam_questions_csv(path, questions, max_scores=None):  # type: ignore[no-untyped-def]
                import csv

                path.parent.mkdir(parents=True, exist_ok=True)
                fields = ["question_id", "question_no", "sub_no", "order", "max_score", "stem_ref"]
                with path.open("w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=fields)
                    writer.writeheader()
                    for idx, question in enumerate(questions, start=1):
                        qid = str(question.get("question_id") or "").strip()
                        writer.writerow(
                            {
                                "question_id": qid,
                                "question_no": question.get("question_no") or "",
                                "sub_no": question.get("sub_no") or "",
                                "order": str(idx),
                                "max_score": str((max_scores or {}).get(qid, "")) if max_scores else "",
                                "stem_ref": "",
                            }
                        )

            deps = ExamUploadParseDeps(
                app_root=root,
                now_iso=lambda: "2026-02-10T12:00:00",
                now_date_compact=lambda: "20260210",
                load_exam_job=lambda _job_id: dict(job),
                exam_job_path=lambda _job_id: job_dir,
                write_exam_job=write_exam_job,
                extract_text_from_file=lambda *_args, **_kwargs: "",
                extract_text_from_pdf=lambda *_args, **_kwargs: "",
                extract_text_from_image=lambda *_args, **_kwargs: "",
                parse_xlsx_with_script=parse_xlsx_with_script,
                xlsx_to_table_preview=lambda *_args, **_kwargs: "",
                xls_to_table_preview=lambda *_args, **_kwargs: "",
                llm_parse_exam_scores=lambda _text: {},
                build_exam_rows_from_parsed_scores=lambda _exam_id, _parsed: ([], {}, []),
                parse_score_value=lambda v: float(v) if str(v or "").strip() else None,
                write_exam_responses_csv=write_exam_responses_csv,
                parse_exam_answer_key_text=lambda _text: ([], []),
                write_exam_answers_csv=lambda _p, _rows: None,
                compute_max_scores_from_rows=lambda _rows: {},
                write_exam_questions_csv=write_exam_questions_csv,
                apply_answer_key_to_responses_csv=lambda _a, _b, _c, _d: {},
                compute_exam_totals=lambda _p: {"totals": {"S1": 42.0}},
                copy2=lambda src, dst: dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8"),
                diag_log=lambda _event, _payload=None: None,
                parse_date_str=lambda v: str(v or ""),
            )

            process_exam_upload_job("job-1", deps)

            parsed = json.loads((job_dir / "parsed.json").read_text(encoding="utf-8"))
            self.assertEqual((parsed.get("meta") or {}).get("score_mode"), "subject")
            self.assertEqual((parsed.get("questions") or [{}])[0].get("question_id"), "SUBJECT_PHYSICS")


if __name__ == "__main__":
    unittest.main()
