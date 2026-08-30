"""Tests for services.api.xlsx_rows — shared assignment XLSX preview iterator."""
from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET

from services.api.xlsx_rows import iter_rows


def _col_letters(idx: int) -> str:
    letters = ""
    n = idx
    while n:
        n, rem = divmod(n - 1, 26)
        letters = chr(ord("A") + rem) + letters
    return letters


def _write_minimal_xlsx(path: Path, rows: list[list[str]]) -> None:
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
    od_rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

    sheet = ET.Element("worksheet", {"xmlns": ns})
    sheet_data = ET.SubElement(sheet, "sheetData")
    shared: list[str] = []
    for r_idx, values in enumerate(rows, start=1):
        row_el = ET.SubElement(sheet_data, "row", {"r": str(r_idx)})
        for c_idx, value in enumerate(values, start=1):
            cell_ref = f"{_col_letters(c_idx)}{r_idx}"
            cell = ET.SubElement(row_el, "c", {"r": cell_ref, "t": "inlineStr"})
            is_el = ET.SubElement(cell, "is")
            t_el = ET.SubElement(is_el, "t")
            t_el.text = value
            shared.append(value)

    workbook = ET.Element("workbook", {"xmlns": ns, "xmlns:r": od_rel})
    sheets = ET.SubElement(workbook, "sheets")
    ET.SubElement(sheets, "sheet", {"name": "Sheet1", "sheetId": "1", f"{{{od_rel}}}id": "rId1"})

    rels = ET.Element("Relationships", {"xmlns": rel_ns})
    ET.SubElement(
        rels,
        "Relationship",
        {
            "Id": "rId1",
            "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet",
            "Target": "worksheets/sheet1.xml",
        },
    )

    content_types = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        "</Types>"
    )

    with ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("xl/workbook.xml", ET.tostring(workbook, encoding="unicode"))
        z.writestr("xl/_rels/workbook.xml.rels", ET.tostring(rels, encoding="unicode"))
        z.writestr("xl/worksheets/sheet1.xml", ET.tostring(sheet, encoding="unicode"))


def test_iter_rows_reads_inline_strings(tmp_path: Path) -> None:
    path = tmp_path / "scores.xlsx"
    _write_minimal_xlsx(path, [["姓名", "总分"], ["张三", "90"]])
    rows = list(iter_rows(path))
    assert rows[0][0] == 1
    assert rows[0][1][1] == "姓名"
    assert rows[1][1][2] == "90"


def test_iter_rows_empty_sheet(tmp_path: Path) -> None:
    path = tmp_path / "empty.xlsx"
    _write_minimal_xlsx(path, [])
    assert list(iter_rows(path)) == []
