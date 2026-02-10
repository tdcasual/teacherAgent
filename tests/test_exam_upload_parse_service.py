import unittest
import json
import zipfile
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.sax.saxutils import escape

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
            parse_xlsx_with_script=lambda _xlsx, _out, _exam_id, _class_name, _subject_candidate_id=None: ([], {}),
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

    def _make_minimal_xlsx(self, headers, rows) -> bytes:  # type: ignore[no-untyped-def]
        def cell_inline(col: str, row_idx: int, value: str) -> str:
            return f'<c r="{col}{row_idx}" t="inlineStr"><is><t>{escape(value)}</t></is></c>'

        def cell_number(col: str, row_idx: int, value) -> str:  # type: ignore[no-untyped-def]
            return f'<c r="{col}{row_idx}"><v>{value}</v></c>'

        cols = [chr(ord("A") + i) for i in range(len(headers))]

        sheet_rows = []
        header_cells = "".join([cell_inline(cols[i], 1, str(headers[i])) for i in range(len(headers))])
        sheet_rows.append(f'<row r="1">{header_cells}</row>')
        for r_i, data in enumerate(rows, start=2):
            cells = []
            for c_i, val in enumerate(data):
                col = cols[c_i]
                if isinstance(val, (int, float)) and not isinstance(val, bool):
                    cells.append(cell_number(col, r_i, val))
                else:
                    cells.append(cell_inline(col, r_i, str(val)))
            sheet_rows.append(f'<row r="{r_i}">{"".join(cells)}</row>')

        sheet_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            "<sheetData>"
            + "".join(sheet_rows)
            + "</sheetData>"
            "</worksheet>"
        )

        workbook_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            "<sheets>"
            '<sheet name="Sheet1" sheetId="1" r:id="rId1"/>'
            "</sheets>"
            "</workbook>"
        )

        workbook_rels = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            'Target="worksheets/sheet1.xml"/>'
            "</Relationships>"
        )

        root_rels = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="xl/workbook.xml"/>'
            "</Relationships>"
        )

        content_types = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            "</Types>"
        )

        out = BytesIO()
        with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", content_types)
            z.writestr("_rels/.rels", root_rels)
            z.writestr("xl/workbook.xml", workbook_xml)
            z.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
            z.writestr("xl/worksheets/sheet1.xml", sheet_xml)
        return out.getvalue()

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

            def parse_xlsx_with_script(_xlsx, _out, _exam_id, _class_name, _subject_candidate_id=None):  # type: ignore[no-untyped-def]
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
                ], {
                    "mode": "subject",
                    "confidence": 0.9,
                    "needs_confirm": False,
                    "subject": {
                        "candidate_columns": [
                            {
                                "candidate_id": "pair:4:5",
                                "type": "subject_pair",
                                "subject_col": 4,
                                "score_col": 5,
                            }
                        ]
                    },
                    "summary": {"data_rows": 1, "parsed_rows": 1},
                }

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

    def test_question_mode_wins_when_sources_mixed(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            writes = []
            job = {
                "exam_id": "EX_MIXED",
                "paper_files": ["paper.pdf"],
                "score_files": ["a.xlsx", "b.xlsx"],
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
            (job_dir / "scores" / "a.xlsx").write_text("a", encoding="utf-8")
            (job_dir / "scores" / "b.xlsx").write_text("b", encoding="utf-8")

            def write_exam_job(job_id, updates):  # type: ignore[no-untyped-def]
                writes.append((job_id, dict(updates)))
                return updates

            parse_calls = []

            def parse_xlsx_with_script(path, _out, _exam_id, _class_name, _subject_candidate_id=None):  # type: ignore[no-untyped-def]
                parse_calls.append(path.name)
                if path.name == "a.xlsx":
                    return [
                        {
                            "exam_id": "EX_MIXED",
                            "student_id": "S1",
                            "student_name": "张三",
                            "class_name": "",
                            "question_id": "Q1",
                            "question_no": "1",
                            "sub_no": "",
                            "raw_label": "1",
                            "raw_value": "4",
                            "raw_answer": "",
                            "score": 4,
                            "is_correct": "",
                        }
                    ], {
                        "mode": "question",
                        "confidence": 1.0,
                        "needs_confirm": False,
                        "summary": {"data_rows": 1, "parsed_rows": 1},
                    }
                return [
                    {
                        "exam_id": "EX_MIXED",
                        "student_id": "S1",
                        "student_name": "张三",
                        "class_name": "",
                        "question_id": "SUBJECT_PHYSICS",
                        "question_no": "",
                        "sub_no": "",
                        "raw_label": "物理",
                        "raw_value": "88",
                        "raw_answer": "",
                        "score": 88,
                        "is_correct": "",
                    }
                ], {
                    "mode": "subject",
                    "confidence": 0.9,
                    "needs_confirm": False,
                    "subject": {
                        "candidate_columns": [
                            {
                                "candidate_id": "pair:4:5",
                                "type": "subject_pair",
                                "subject_col": 4,
                                "score_col": 5,
                            }
                        ]
                    },
                    "summary": {"data_rows": 1, "parsed_rows": 1},
                }

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
                compute_exam_totals=lambda _p: {"totals": {"S1": 4.0}},
                copy2=lambda src, dst: dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8"),
                diag_log=lambda _event, _payload=None: None,
                parse_date_str=lambda v: str(v or ""),
            )

            process_exam_upload_job("job-1", deps)

            parsed = json.loads((job_dir / "parsed.json").read_text(encoding="utf-8"))
            self.assertEqual((parsed.get("meta") or {}).get("score_mode"), "question")
            self.assertEqual((parsed.get("score_schema") or {}).get("mode"), "question")
            self.assertEqual(parse_calls, ["a.xlsx", "b.xlsx"])

    def test_selected_candidate_marks_invalid_when_unavailable(self):
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
                "score_schema": {"subject": {"selected_candidate_id": "pair:9:9"}},
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

            def parse_xlsx_with_script(_xlsx, _out, _exam_id, _class_name, _subject_candidate_id=None):  # type: ignore[no-untyped-def]
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
                ], {
                    "mode": "subject",
                    "confidence": 0.9,
                    "needs_confirm": True,
                    "subject": {
                        "selected_candidate_id": "",
                        "selected_candidate_available": False,
                        "requested_candidate_id": "pair:9:9",
                        "candidate_columns": [
                            {
                                "candidate_id": "pair:4:5",
                                "type": "subject_pair",
                                "subject_col": 4,
                                "score_col": 5,
                            }
                        ],
                    },
                    "summary": {"data_rows": 1, "parsed_rows": 1},
                }

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
            score_schema = parsed.get("score_schema") or {}
            subject_info = score_schema.get("subject") or {}
            self.assertTrue(bool(score_schema.get("needs_confirm")))
            self.assertEqual(str(subject_info.get("selection_error") or ""), "selected_candidate_not_found")
            self.assertFalse(bool(subject_info.get("selected_candidate_available")))
            self.assertEqual(str(subject_info.get("recommended_candidate_id") or ""), "pair:4:5")
            self.assertTrue(isinstance(subject_info.get("candidate_summaries"), list))
            self.assertTrue(any("pair:4:5" in str(x) for x in (parsed.get("warnings") or [])))

    def test_candidate_recommendation_prefers_pair_over_chaos(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            writes = []
            job = {
                "exam_id": "EX_RECOMMEND",
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

            def parse_xlsx_with_script(_xlsx, _out, _exam_id, _class_name, _subject_candidate_id=None):  # type: ignore[no-untyped-def]
                return [
                    {
                        "exam_id": "EX_RECOMMEND",
                        "student_id": "S1",
                        "student_name": "张三",
                        "class_name": "",
                        "question_id": "SUBJECT_PHYSICS",
                        "question_no": "",
                        "sub_no": "",
                        "raw_label": "物理",
                        "raw_value": "79",
                        "raw_answer": "",
                        "score": 79,
                        "is_correct": "",
                    }
                ], {
                    "mode": "subject",
                    "confidence": 0.92,
                    "needs_confirm": False,
                    "subject": {
                        "candidate_columns": [
                            {
                                "candidate_id": "pair:4:5",
                                "type": "subject_pair",
                                "rows_considered": 10,
                                "rows_parsed": 9,
                                "rows_invalid": 1,
                            },
                            {
                                "candidate_id": "chaos:text",
                                "type": "chaos_text_scan",
                                "rows_considered": 10,
                                "rows_parsed": 8,
                                "rows_invalid": 2,
                            },
                        ]
                    },
                    "summary": {"data_rows": 10, "parsed_rows": 9},
                }

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
                compute_exam_totals=lambda _p: {"totals": {"S1": 79.0}},
                copy2=lambda src, dst: dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8"),
                diag_log=lambda _event, _payload=None: None,
                parse_date_str=lambda v: str(v or ""),
            )

            process_exam_upload_job("job-1", deps)

            parsed = json.loads((job_dir / "parsed.json").read_text(encoding="utf-8"))
            subject_info = ((parsed.get("score_schema") or {}).get("subject") or {})
            self.assertEqual(str(subject_info.get("recommended_candidate_id") or ""), "pair:4:5")
            summaries = subject_info.get("candidate_summaries") or []
            self.assertTrue(isinstance(summaries, list) and len(summaries) >= 2)
            top = summaries[0] if summaries else {}
            self.assertEqual(str(top.get("candidate_id") or ""), "pair:4:5")

    def test_parse_scores_chaos_text_candidate(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            xlsx_path = root / "chaos.xlsx"
            out_csv = root / "out.csv"
            report_path = root / "out.csv.report.json"

            xlsx_bytes = self._make_minimal_xlsx(
                headers=["学生", "标识", "记录"],
                rows=[
                    ["张三", "7118210001", "物理: 76"],
                    ["李四", "7118210002", "物理 82分"],
                    ["王五", "7118210003", "化学 70"],
                ],
            )
            xlsx_path.write_bytes(xlsx_bytes)

            from services.api.exam_utils import _parse_xlsx_with_script

            rows, report = _parse_xlsx_with_script(
                xlsx_path,
                out_csv,
                "EX_CHAOS",
                "",
                None,
            )

            self.assertIsNotNone(rows)
            self.assertTrue(report_path.exists())
            loaded_report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(loaded_report.get("mode"), "subject")
            candidate_columns = ((loaded_report.get("subject") or {}).get("candidate_columns") or [])
            candidate_ids = [str(item.get("candidate_id") or "") for item in candidate_columns if isinstance(item, dict)]
            self.assertIn("chaos:text", candidate_ids)
            chaos_candidate = next((item for item in candidate_columns if str(item.get("candidate_id") or "") == "chaos:text"), {})
            self.assertGreaterEqual(int(chaos_candidate.get("rows_considered") or 0), 2)
            self.assertGreaterEqual(int(chaos_candidate.get("rows_parsed") or 0), 2)
            self.assertTrue(isinstance(chaos_candidate.get("sample_rows"), list))
            self.assertTrue(len(chaos_candidate.get("sample_rows") or []) >= 1)
            parsed_rows = rows or []
            self.assertTrue(any(str(item.get("question_id") or "") == "SUBJECT_PHYSICS" for item in parsed_rows))

    def test_parse_scores_chaos_sheet_text_candidate(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            xlsx_path = root / "chaos_sheet.xlsx"
            out_csv = root / "out.csv"
            report_path = root / "out.csv.report.json"

            xlsx_bytes = self._make_minimal_xlsx(
                headers=["序列A", "序列B", "序列C"],
                rows=[
                    ["张三", "7118210001", "物理"],
                    ["76", "", ""],
                    ["李四", "7118210002", "physics"],
                    ["82", "", ""],
                    ["王五 7118210003", "化学", "70"],
                ],
            )
            xlsx_path.write_bytes(xlsx_bytes)

            from services.api.exam_utils import _parse_xlsx_with_script

            rows, report = _parse_xlsx_with_script(
                xlsx_path,
                out_csv,
                "EX_CHAOS_SHEET",
                "高二1班",
                None,
            )

            self.assertIsNotNone(rows)
            self.assertTrue(report_path.exists())
            loaded_report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(loaded_report.get("mode"), "subject")
            candidate_columns = ((loaded_report.get("subject") or {}).get("candidate_columns") or [])
            candidate_ids = [str(item.get("candidate_id") or "") for item in candidate_columns if isinstance(item, dict)]
            self.assertIn("chaos:sheet_text", candidate_ids)

            sheet_candidate = next(
                (item for item in candidate_columns if str(item.get("candidate_id") or "") == "chaos:sheet_text"),
                {},
            )
            self.assertGreaterEqual(int(sheet_candidate.get("rows_parsed") or 0), 2)
            self.assertGreaterEqual(int(sheet_candidate.get("rows_considered") or 0), int(sheet_candidate.get("rows_parsed") or 0))
            self.assertTrue(isinstance(sheet_candidate.get("sample_rows"), list))

            subject_info = loaded_report.get("subject") or {}
            self.assertGreaterEqual(int(subject_info.get("chaos_sheet_rows_extracted") or 0), 2)
            self.assertGreaterEqual(
                int(subject_info.get("chaos_sheet_rows_attempted") or 0),
                int(subject_info.get("chaos_sheet_rows_extracted") or 0),
            )

            parsed_rows = rows or []
            parsed_names = {str(item.get("student_name") or "") for item in parsed_rows}
            self.assertIn("张三", parsed_names)
            self.assertIn("李四", parsed_names)
            self.assertTrue(any(str(item.get("question_id") or "") == "SUBJECT_PHYSICS" for item in parsed_rows))

    def test_parse_scores_prefers_stronger_candidate_when_same_student(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            xlsx_path = root / "dedupe.xlsx"
            out_csv = root / "out.csv"
            report_path = root / "out.csv.report.json"

            xlsx_bytes = self._make_minimal_xlsx(
                headers=["姓名", "记录A", "记录B"],
                rows=[
                    ["张三", "物理: 76", ""],
                    ["", "张三 7118210001 physics", "82"],
                ],
            )
            xlsx_path.write_bytes(xlsx_bytes)

            from services.api.exam_utils import _parse_xlsx_with_script

            rows, _report = _parse_xlsx_with_script(
                xlsx_path,
                out_csv,
                "EX_DEDUPE",
                "高二1班",
                None,
            )

            self.assertTrue(report_path.exists())
            parsed_rows = [item for item in (rows or []) if str(item.get("question_id") or "") == "SUBJECT_PHYSICS"]
            zhangsan_rows = [item for item in parsed_rows if str(item.get("student_name") or "") == "张三"]
            self.assertEqual(len(zhangsan_rows), 1)
            self.assertEqual(float(zhangsan_rows[0].get("score") or 0), 76.0)

    def test_parse_scores_extreme_chaos_without_header_uses_sheet_fallback(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            xlsx_path = root / "chaos_no_header.xlsx"
            out_csv = root / "out.csv"
            report_path = root / "out.csv.report.json"

            xlsx_bytes = self._make_minimal_xlsx(
                headers=["####", "@@@@", "----"],
                rows=[
                    ["张三 7118210001", "random text", "物理"],
                    ["###", "76", ""],
                    ["李四 7118210002", "noise", "physics"],
                    ["", "82", "..."],
                ],
            )
            xlsx_path.write_bytes(xlsx_bytes)

            from services.api.exam_utils import _parse_xlsx_with_script

            rows, report = _parse_xlsx_with_script(
                xlsx_path,
                out_csv,
                "EX_CHAOS_NO_HEADER",
                "高二1班",
                None,
            )

            self.assertIsNotNone(rows)
            self.assertTrue(report_path.exists())
            loaded_report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(str(loaded_report.get("mode") or ""), "subject")
            self.assertIn(str(loaded_report.get("header_detect_mode") or ""), {"loose", "none"})

            subject_info = loaded_report.get("subject") or {}
            candidate_columns = subject_info.get("candidate_columns") or []
            candidate_ids = [str(item.get("candidate_id") or "") for item in candidate_columns if isinstance(item, dict)]
            self.assertIn("chaos:sheet_text", candidate_ids)
            self.assertGreaterEqual(int(subject_info.get("chaos_sheet_rows_extracted") or 0), 2)

            parsed_rows = [item for item in (rows or []) if str(item.get("question_id") or "") == "SUBJECT_PHYSICS"]
            parsed_names = {str(item.get("student_name") or "") for item in parsed_rows}
            self.assertIn("张三", parsed_names)
            self.assertIn("李四", parsed_names)


if __name__ == "__main__":
    unittest.main()
