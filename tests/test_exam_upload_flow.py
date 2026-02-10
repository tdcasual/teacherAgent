import csv
import importlib
import json
import os
import time
import unittest
import zipfile
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.sax.saxutils import escape

from fastapi.testclient import TestClient


def load_app(tmp_dir: Path):
    os.environ["DATA_DIR"] = str(tmp_dir / "data")
    os.environ["UPLOADS_DIR"] = str(tmp_dir / "uploads")
    os.environ["DIAG_LOG"] = "0"
    import services.api.app as app_mod

    importlib.reload(app_mod)
    return app_mod


def make_pdf_bytes(text: str) -> bytes:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    buf = BytesIO()
    safe_text = (text or "").strip()
    if len(safe_text) < 60:
        repeat = max(1, (60 // max(len(safe_text), 1)) + 1)
        safe_text = " ".join([safe_text] * repeat).strip()
    c = canvas.Canvas(buf, pagesize=letter)
    c.setFont("Helvetica", 12)
    c.drawString(72, 720, safe_text)
    c.showPage()
    c.save()
    return buf.getvalue()


def make_minimal_xlsx(headers, rows) -> bytes:
    # Build a tiny XLSX with inline strings; enough for parse_scores.py's XML reader.
    def cell_inline(col: str, row_idx: int, value: str) -> str:
        return f'<c r="{col}{row_idx}" t="inlineStr"><is><t>{escape(value)}</t></is></c>'

    def cell_number(col: str, row_idx: int, value) -> str:
        return f'<c r="{col}{row_idx}"><v>{value}</v></c>'

    cols = [chr(ord("A") + i) for i in range(len(headers))]

    sheet_rows = []
    # header row
    header_cells = "".join([cell_inline(cols[i], 1, str(headers[i])) for i in range(len(headers))])
    sheet_rows.append(f'<row r="1">{header_cells}</row>')
    # data rows
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


class ExamUploadFlowTest(unittest.TestCase):
    def test_exam_upload_start_status_draft_confirm(self):
        with TemporaryDirectory() as td:
            tmp_dir = Path(td)
            app_mod = load_app(tmp_dir)
            with TestClient(app_mod.app) as client:

                exam_id = "EX_UPLOAD_TEST"
                paper_pdf = make_pdf_bytes("Physics Exam Paper")
                # columns: 姓名, 班级, 1, 2
                xlsx = make_minimal_xlsx(
                    headers=["姓名", "班级", "1", "2"],
                    rows=[
                        ["张三", "高二2403班", 4, 3],
                        ["李四", "高二2403班", 2, 1],
                    ],
                )

                files = [
                    ("paper_files", ("paper.pdf", paper_pdf, "application/pdf")),
                    ("score_files", ("scores.xlsx", xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")),
                ]
                data = {"exam_id": exam_id, "date": "2026-02-05", "class_name": "高二2403班"}

                res = client.post("/exam/upload/start", data=data, files=files)
                self.assertEqual(res.status_code, 200)
                payload = res.json()
                self.assertTrue(payload["ok"])
                job_id = payload["job_id"]

                # Poll until done
                status = None
                for _ in range(120):
                    res = client.get("/exam/upload/status", params={"job_id": job_id})
                    self.assertEqual(res.status_code, 200)
                    status_payload = res.json()
                    status = status_payload.get("status")
                    if status == "done":
                        break
                    if status == "failed":
                        self.fail(f"exam upload failed: {status_payload}")
                    time.sleep(0.1)
                self.assertEqual(status, "done")

                res = client.get("/exam/upload/draft", params={"job_id": job_id})
                self.assertEqual(res.status_code, 200)
                draft = res.json()["draft"]
                self.assertEqual(draft["exam_id"], exam_id)
                self.assertTrue(draft["counts"]["students"] >= 2)
                self.assertTrue(len(draft["questions"]) >= 2)

                # Save draft (edit max_score)
                draft["questions"][0]["max_score"] = 4
                res = client.post(
                    "/exam/upload/draft/save", json={"job_id": job_id, "meta": draft["meta"], "questions": draft["questions"]}
                )
                self.assertEqual(res.status_code, 200)

                res = client.post("/exam/upload/confirm", json={"job_id": job_id})
                self.assertEqual(res.status_code, 200)
                confirmed = res.json()
                self.assertEqual(confirmed["exam_id"], exam_id)

                manifest_path = Path(os.environ["DATA_DIR"]) / "exams" / exam_id / "manifest.json"
                self.assertTrue(manifest_path.exists())

                analysis_path = Path(os.environ["DATA_DIR"]) / "analysis" / exam_id / "draft.json"
                self.assertTrue(analysis_path.exists())

                # Sanity: exam endpoints can read it
                res = client.get(f"/exam/{exam_id}")
                self.assertEqual(res.status_code, 200)

    def test_exam_upload_with_answer_key_scores_objective_answers(self):
        with TemporaryDirectory() as td:
            tmp_dir = Path(td)
            app_mod = load_app(tmp_dir)
            with TestClient(app_mod.app) as client:

                exam_id = "EX_UPLOAD_WITH_ANSWERS"
                paper_pdf = make_pdf_bytes("Physics Exam Paper")
                # Score sheet contains objective answers (A/B/C) instead of numeric scores.
                xlsx = make_minimal_xlsx(
                    headers=["姓名", "班级", "1", "2"],
                    rows=[
                        ["张三", "高二2403班", "A", "C"],
                        ["李四", "高二2403班", "B", "C"],
                    ],
                )
                # Answer key as Markdown (avoid OCR/LLM in tests).
                answer_md = b"1 A\n2 C\n"

                files = [
                    ("paper_files", ("paper.pdf", paper_pdf, "application/pdf")),
                    ("score_files", ("scores.xlsx", xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")),
                    ("answer_files", ("answers.md", answer_md, "text/markdown")),
                ]
                data = {"exam_id": exam_id, "date": "2026-02-05", "class_name": "高二2403班"}

                res = client.post("/exam/upload/start", data=data, files=files)
                self.assertEqual(res.status_code, 200)
                payload = res.json()
                self.assertTrue(payload["ok"])
                job_id = payload["job_id"]

                # Poll until done
                status = None
                for _ in range(120):
                    res = client.get("/exam/upload/status", params={"job_id": job_id})
                    self.assertEqual(res.status_code, 200)
                    status_payload = res.json()
                    status = status_payload.get("status")
                    if status == "done":
                        break
                    if status == "failed":
                        self.fail(f"exam upload failed: {status_payload}")
                    time.sleep(0.1)
                self.assertEqual(status, "done")

                res = client.get("/exam/upload/draft", params={"job_id": job_id})
                self.assertEqual(res.status_code, 200)
                draft = res.json()["draft"]
                self.assertEqual(draft["exam_id"], exam_id)
                # Should have parsed answer key into draft (count > 0)
                self.assertTrue((draft.get("answer_key") or {}).get("count", 0) >= 2)

                # Ensure responses_scored.csv has numeric scores filled.
                derived = Path(os.environ["UPLOADS_DIR"]) / "exam_jobs" / job_id / "derived"
                scored_path = derived / "responses_scored.csv"
                self.assertTrue(scored_path.exists())
                with scored_path.open(encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    scored_rows = list(reader)
                self.assertTrue(any((r.get("score") or "").strip() != "" for r in scored_rows))

                # Confirm creates exam with answers in manifest.
                res = client.post("/exam/upload/confirm", json={"job_id": job_id})
                self.assertEqual(res.status_code, 200)
                confirmed = res.json()
                self.assertEqual(confirmed["exam_id"], exam_id)

                manifest_path = Path(os.environ["DATA_DIR"]) / "exams" / exam_id / "manifest.json"
                self.assertTrue(manifest_path.exists())
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                self.assertTrue("answers" in (manifest.get("files") or {}))

    def test_exam_upload_answer_key_override_via_draft_save(self):
        with TemporaryDirectory() as td:
            tmp_dir = Path(td)
            app_mod = load_app(tmp_dir)
            with TestClient(app_mod.app) as client:

                exam_id = "EX_UPLOAD_OVERRIDE_ANS"
                paper_pdf = make_pdf_bytes("Physics Exam Paper")
                # Score sheet contains objective answers (A/B/C) instead of numeric scores.
                xlsx = make_minimal_xlsx(
                    headers=["姓名", "班级", "1", "2"],
                    rows=[
                        ["张三", "高二2403班", "A", "C"],
                        ["李四", "高二2403班", "B", "C"],
                    ],
                )

                files = [
                    ("paper_files", ("paper.pdf", paper_pdf, "application/pdf")),
                    ("score_files", ("scores.xlsx", xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")),
                ]
                data = {"exam_id": exam_id, "date": "2026-02-05", "class_name": "高二2403班"}

                res = client.post("/exam/upload/start", data=data, files=files)
                self.assertEqual(res.status_code, 200)
                payload = res.json()
                self.assertTrue(payload["ok"])
                job_id = payload["job_id"]

                # Poll until done
                status = None
                for _ in range(120):
                    res = client.get("/exam/upload/status", params={"job_id": job_id})
                    self.assertEqual(res.status_code, 200)
                    status_payload = res.json()
                    status = status_payload.get("status")
                    if status == "done":
                        break
                    if status == "failed":
                        self.fail(f"exam upload failed: {status_payload}")
                    time.sleep(0.1)
                self.assertEqual(status, "done")

                # Save draft with answer key override (text).
                res = client.get("/exam/upload/draft", params={"job_id": job_id})
                self.assertEqual(res.status_code, 200)
                draft = res.json()["draft"]
                res = client.post(
                    "/exam/upload/draft/save",
                    json={
                        "job_id": job_id,
                        "meta": draft.get("meta") or {},
                        "questions": draft.get("questions") or [],
                        "score_schema": draft.get("score_schema") or {},
                        "answer_key_text": "1 A\n2 C\n",
                    },
                )
                self.assertEqual(res.status_code, 200)

                # Confirm should use override to score.
                res = client.post("/exam/upload/confirm", json={"job_id": job_id})
                self.assertEqual(res.status_code, 200)

                # Exam derived scored responses should contain numeric scores.
                scored_path = Path(os.environ["DATA_DIR"]) / "exams" / exam_id / "derived" / "responses_scored.csv"
                self.assertTrue(scored_path.exists())
                with scored_path.open(encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)
                self.assertTrue(any((r.get("score") or "").strip() != "" for r in rows))

    def test_exam_upload_multi_select_partial_credit(self):
        with TemporaryDirectory() as td:
            tmp_dir = Path(td)
            app_mod = load_app(tmp_dir)
            with TestClient(app_mod.app) as client:

                exam_id = "EX_UPLOAD_MULTI_SELECT"
                paper_pdf = make_pdf_bytes("Physics Exam Paper")
                # One multi-select question: correct is AC.
                xlsx = make_minimal_xlsx(
                    headers=["姓名", "班级", "1"],
                    rows=[
                        ["张三", "高二2403班", "A"],   # missing C -> half score
                        ["李四", "高二2403班", "AC"],  # full score
                        ["王五", "高二2403班", "AB"],  # wrong option -> 0
                    ],
                )
                answer_md = b"1 AC\n"

                files = [
                    ("paper_files", ("paper.pdf", paper_pdf, "application/pdf")),
                    ("score_files", ("scores.xlsx", xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")),
                    ("answer_files", ("answers.md", answer_md, "text/markdown")),
                ]
                data = {"exam_id": exam_id, "date": "2026-02-05", "class_name": "高二2403班"}

                res = client.post("/exam/upload/start", data=data, files=files)
                self.assertEqual(res.status_code, 200)
                payload = res.json()
                self.assertTrue(payload["ok"])
                job_id = payload["job_id"]

                # Poll until done
                status = None
                for _ in range(120):
                    res = client.get("/exam/upload/status", params={"job_id": job_id})
                    self.assertEqual(res.status_code, 200)
                    status_payload = res.json()
                    status = status_payload.get("status")
                    if status == "done":
                        break
                    if status == "failed":
                        self.fail(f"exam upload failed: {status_payload}")
                    time.sleep(0.1)
                self.assertEqual(status, "done")

                # Set max_score=2 for Q1 then confirm, so half credit becomes 1.
                res = client.get("/exam/upload/draft", params={"job_id": job_id})
                self.assertEqual(res.status_code, 200)
                draft = res.json()["draft"]
                for q in draft.get("questions") or []:
                    if str(q.get("question_id") or "").strip() == "Q1":
                        q["max_score"] = 2
                res = client.post(
                    "/exam/upload/draft/save",
                    json={
                        "job_id": job_id,
                        "meta": draft.get("meta") or {},
                        "questions": draft.get("questions") or [],
                        "score_schema": draft.get("score_schema") or {},
                        "answer_key_text": draft.get("answer_key_text") or "",
                    },
                )
                self.assertEqual(res.status_code, 200)

                res = client.post("/exam/upload/confirm", json={"job_id": job_id})
                self.assertEqual(res.status_code, 200)

                scored_path = Path(os.environ["DATA_DIR"]) / "exams" / exam_id / "derived" / "responses_scored.csv"
                self.assertTrue(scored_path.exists())
                rows = []
                with scored_path.open(encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    rows = [r for r in reader if (r.get("question_id") or "").strip() == "Q1"]
                self.assertEqual(len(rows), 3)

                def _score_of(name: str) -> str:
                    for r in rows:
                        if (r.get("student_name") or "").strip() == name:
                            return str(r.get("score") or "").strip()
                    return ""

                self.assertEqual(_score_of("张三"), "1")
                self.assertEqual(_score_of("李四"), "2")
                self.assertEqual(_score_of("王五"), "0")

    def test_exam_upload_subject_score_sheet_extracts_physics(self):
        with TemporaryDirectory() as td:
            tmp_dir = Path(td)
            app_mod = load_app(tmp_dir)
            with TestClient(app_mod.app) as client:

                exam_id = "EX_UPLOAD_SUBJECT_PHYSICS"
                paper_pdf = make_pdf_bytes("Physics Exam Paper")
                xlsx = make_minimal_xlsx(
                    headers=[
                        "考生姓名",
                        "考号",
                        "总分",
                        "班次/校次",
                        "科目",
                        "分数",
                        "班次/校次",
                        "科目",
                        "分数",
                        "班次/校次",
                        "科目",
                        "分数",
                    ],
                    rows=[
                        ["平均分", "-", 371.7, "-/-", "语文", 92.1, "-/-", "数学", 85.4, "-/-", "物理", 29.8],
                        ["张三", "7118210001", 450.0, "2/10", "语文", 96, "4/10", "数学", 90, "1/10", "物理", 42],
                        ["李四", "7118210002", 430.5, "5/10", "语文", 91, "3/10", "数学", 88, "6/10", "物理", 35],
                    ],
                )

                files = [
                    ("paper_files", ("paper.pdf", paper_pdf, "application/pdf")),
                    (
                        "score_files",
                        ("scores.xlsx", xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
                    ),
                ]
                data = {"exam_id": exam_id, "date": "2026-02-05"}

                res = client.post("/exam/upload/start", data=data, files=files)
                self.assertEqual(res.status_code, 200)
                payload = res.json()
                self.assertTrue(payload["ok"])
                job_id = payload["job_id"]

                status = None
                for _ in range(120):
                    res = client.get("/exam/upload/status", params={"job_id": job_id})
                    self.assertEqual(res.status_code, 200)
                    status_payload = res.json()
                    status = status_payload.get("status")
                    if status == "done":
                        break
                    if status == "failed":
                        self.fail(f"exam upload failed: {status_payload}")
                    time.sleep(0.1)
                self.assertEqual(status, "done")

                res = client.get("/exam/upload/draft", params={"job_id": job_id})
                self.assertEqual(res.status_code, 200)
                draft = res.json()["draft"]
                self.assertEqual((draft.get("meta") or {}).get("score_mode"), "subject")
                questions = draft.get("questions") or []
                self.assertEqual(len(questions), 1)
                self.assertEqual(str(questions[0].get("question_id") or "").strip(), "SUBJECT_PHYSICS")

                res = client.post("/exam/upload/confirm", json={"job_id": job_id})
                self.assertEqual(res.status_code, 200)

                scored_path = Path(os.environ["DATA_DIR"]) / "exams" / exam_id / "derived" / "responses_scored.csv"
                self.assertTrue(scored_path.exists())
                with scored_path.open(encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    rows = [r for r in reader if (r.get("question_id") or "").strip() == "SUBJECT_PHYSICS"]

                self.assertEqual(len(rows), 2)

                def _score_of(name: str) -> str:
                    for r in rows:
                        if (r.get("student_name") or "").strip() == name:
                            return str(r.get("score") or "").strip()
                    return ""

                self.assertAlmostEqual(float(_score_of("张三") or 0), 42.0)
                self.assertAlmostEqual(float(_score_of("李四") or 0), 35.0)

    def test_exam_upload_subject_mode_requires_draft_confirmation_when_low_confidence(self):
        with TemporaryDirectory() as td:
            tmp_dir = Path(td)
            app_mod = load_app(tmp_dir)
            with TestClient(app_mod.app) as client:

                exam_id = "EX_UPLOAD_SUBJECT_NEEDS_CONFIRM"
                paper_pdf = make_pdf_bytes("Physics Exam Paper")
                xlsx = make_minimal_xlsx(
                    headers=[
                        "考生姓名",
                        "考号",
                        "总分",
                        "科目",
                        "分数",
                    ],
                    rows=[
                        ["张三", "7118210001", 450.0, "物理", 42],
                        ["李四", "7118210002", 430.5, "化学", 35],
                    ],
                )

                files = [
                    ("paper_files", ("paper.pdf", paper_pdf, "application/pdf")),
                    (
                        "score_files",
                        ("scores.xlsx", xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
                    ),
                ]
                data = {"exam_id": exam_id, "date": "2026-02-05"}

                res = client.post("/exam/upload/start", data=data, files=files)
                self.assertEqual(res.status_code, 200)
                payload = res.json()
                self.assertTrue(payload["ok"])
                job_id = payload["job_id"]

                status = None
                for _ in range(120):
                    res = client.get("/exam/upload/status", params={"job_id": job_id})
                    self.assertEqual(res.status_code, 200)
                    status_payload = res.json()
                    status = status_payload.get("status")
                    if status == "done":
                        break
                    if status == "failed":
                        self.fail(f"exam upload failed: {status_payload}")
                    time.sleep(0.1)
                self.assertEqual(status, "done")

                res = client.get("/exam/upload/status", params={"job_id": job_id})
                self.assertEqual(res.status_code, 200)
                status_payload = res.json()
                self.assertTrue(bool(status_payload.get("needs_confirm")))

                res = client.post("/exam/upload/confirm", json={"job_id": job_id})
                self.assertEqual(res.status_code, 400)
                detail = res.json().get("detail") or {}
                self.assertEqual(detail.get("error"), "score_schema_confirm_required")

                res = client.get("/exam/upload/draft", params={"job_id": job_id})
                self.assertEqual(res.status_code, 200)
                draft = res.json().get("draft") or {}
                self.assertTrue(bool(draft.get("needs_confirm")))
                score_schema = draft.get("score_schema") or {}

                res = client.post(
                    "/exam/upload/draft/save",
                    json={
                        "job_id": job_id,
                        "meta": draft.get("meta") or {},
                        "questions": draft.get("questions") or [],
                        "score_schema": {**score_schema, "confirm": True},
                        "answer_key_text": draft.get("answer_key_text") or "",
                    },
                )
                self.assertEqual(res.status_code, 200)

                res = client.post("/exam/upload/confirm", json={"job_id": job_id})
                self.assertEqual(res.status_code, 200)


if __name__ == "__main__":
    unittest.main()
