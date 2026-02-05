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
    c = canvas.Canvas(buf, pagesize=letter)
    c.setFont("Helvetica", 12)
    c.drawString(72, 720, text)
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


if __name__ == "__main__":
    unittest.main()
