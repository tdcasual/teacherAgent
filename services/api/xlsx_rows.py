"""Shared XLSX row iterator for assignment upload previews.

Extracted from skills/physics-teacher-ops/scripts/parse_scores.py so assignment
upload can parse sheets after exam score scripts are removed.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

NS = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

__all__ = ["iter_rows"]


def col_to_index(col_letters: str) -> int:
    col = 0
    for ch in col_letters:
        if not ch.isalpha():
            break
        col = col * 26 + (ord(ch.upper()) - ord("A") + 1)
    return col


def split_cell_ref(cell_ref: str) -> Tuple[str, str]:
    letters = "".join(ch for ch in cell_ref if ch.isalpha())
    numbers = "".join(ch for ch in cell_ref if ch.isdigit())
    return letters, numbers


def load_shared_strings(z: zipfile.ZipFile) -> List[str]:
    if "xl/sharedStrings.xml" not in z.namelist():
        return []
    root = ET.fromstring(z.read("xl/sharedStrings.xml"))
    strings: List[str] = []
    for si in root.findall("main:si", NS):
        texts = [t.text or "" for t in si.findall(".//main:t", NS)]
        strings.append("".join(texts))
    return strings


def cell_value(c: ET.Element, shared_strings: List[str]) -> str:
    t = c.get("t")
    v = c.find("main:v", NS)
    if t == "s":
        if v is None or v.text is None:
            return ""
        idx = int(v.text)
        return shared_strings[idx] if idx < len(shared_strings) else ""
    if t == "inlineStr":
        is_el = c.find("main:is", NS)
        if is_el is None:
            return ""
        texts = [t_el.text or "" for t_el in is_el.findall(".//main:t", NS)]
        return "".join(texts)
    if v is None or v.text is None:
        return ""
    return v.text


def get_sheet_path(z: zipfile.ZipFile, sheet_name: Optional[str], sheet_index: int) -> str:
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    sheets = []
    for sheet in wb.findall("main:sheets/main:sheet", NS):
        sheets.append(
            {
                "name": sheet.get("name"),
                "rid": sheet.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"),
            }
        )
    if not sheets:
        raise ValueError("No sheets found in workbook.xml")

    if sheet_name:
        match = next((s for s in sheets if s["name"] == sheet_name), None)
        if not match:
            available = ", ".join(str(s["name"] or "") for s in sheets)
            raise ValueError(f"Sheet name not found: {sheet_name}. Available: {available}")
        rid = match["rid"]
    else:
        if sheet_index < 0 or sheet_index >= len(sheets):
            raise ValueError(f"sheet_index out of range: {sheet_index}")
        rid = sheets[sheet_index]["rid"]

    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    rel_ns = "{http://schemas.openxmlformats.org/package/2006/relationships}"
    target = None
    for rel in rels.findall(f"{rel_ns}Relationship"):
        if rel.get("Id") == rid:
            target = rel.get("Target")
            break
    if not target:
        raise ValueError(f"Worksheet relationship not found for id {rid}")
    if not target.startswith("xl/"):
        target = f"xl/{target}"
    return target


def iter_rows(
    path: Path,
    sheet_index: int = 0,
    sheet_name: Optional[str] = None,
) -> Iterator[Tuple[int, Dict[int, str]]]:
    with zipfile.ZipFile(path) as z:
        shared_strings = load_shared_strings(z)
        sheet_path = get_sheet_path(z, sheet_name, sheet_index)
        sheet_xml = z.read(sheet_path)
        sheet = ET.fromstring(sheet_xml)

        for row in sheet.findall(".//main:sheetData/main:row", NS):
            r_idx = int(row.get("r") or 0)
            row_cells: Dict[int, str] = {}
            for c in row.findall("main:c", NS):
                cell_ref = c.get("r") or ""
                letters, _ = split_cell_ref(cell_ref)
                col_idx = col_to_index(letters)
                row_cells[col_idx] = cell_value(c, shared_strings)
            yield r_idx, row_cells
