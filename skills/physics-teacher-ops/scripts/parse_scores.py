#!/usr/bin/env python3
import argparse
import csv
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

NS = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

META_HEADERS = {"序号", "姓名", "准考证号", "自定义考号", "班级", "总分", "校次", "班次"}


def col_to_index(col_letters: str) -> int:
    col = 0
    for ch in col_letters:
        if not ch.isalpha():
            break
        col = col * 26 + (ord(ch.upper()) - ord("A") + 1)
    return col


def split_cell_ref(cell_ref: str):
    letters = "".join(ch for ch in cell_ref if ch.isalpha())
    numbers = "".join(ch for ch in cell_ref if ch.isdigit())
    return letters, numbers


def load_shared_strings(z: zipfile.ZipFile):
    if "xl/sharedStrings.xml" not in z.namelist():
        return []
    root = ET.fromstring(z.read("xl/sharedStrings.xml"))
    strings = []
    for si in root.findall("main:si", NS):
        texts = []
        for t in si.findall(".//main:t", NS):
            texts.append(t.text or "")
        strings.append("".join(texts))
    return strings


def cell_value(c, shared_strings):
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
            available = ", ".join(s["name"] for s in sheets)
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


def iter_rows(path: Path, sheet_index: int = 0, sheet_name: Optional[str] = None):
    with zipfile.ZipFile(path) as z:
        shared_strings = load_shared_strings(z)
        sheet_path = get_sheet_path(z, sheet_name, sheet_index)
        sheet_xml = z.read(sheet_path)
        sheet = ET.fromstring(sheet_xml)

        for row in sheet.findall(".//main:sheetData/main:row", NS):
            r_idx = int(row.get("r"))
            row_cells = {}
            for c in row.findall("main:c", NS):
                cell_ref = c.get("r")
                letters, _ = split_cell_ref(cell_ref)
                col_idx = col_to_index(letters)
                row_cells[col_idx] = cell_value(c, shared_strings)
            yield r_idx, row_cells


def normalize_header_value(value):
    if value is None:
        return ""
    s = str(value).strip()
    # Convert numeric-like to int string if possible
    if re.fullmatch(r"\d+\.0", s):
        s = s[:-2]
    return s


def parse_question_label(label: str):
    if not label:
        return None
    s = normalize_header_value(label)
    if not s:
        return None
    # pure digits
    if re.fullmatch(r"\d+", s):
        return int(s), None, s
    # 12(1) or 12(a)
    m = re.fullmatch(r"(\d+)\(([^)]+)\)", s)
    if m:
        return int(m.group(1)), m.group(2), s
    # 12-1 or 12_1
    m = re.fullmatch(r"(\d+)[-_]([A-Za-z0-9]+)", s)
    if m:
        return int(m.group(1)), m.group(2), s
    # 12a
    m = re.fullmatch(r"(\d+)([A-Za-z]+)", s)
    if m:
        return int(m.group(1)), m.group(2), s
    return None


def normalize_answer(value: str) -> str:
    s = str(value).strip().upper()
    # keep letters only for objective answers, sort for stable matching
    letters = re.findall(r"[A-Z]", s)
    if not letters:
        return s
    return "".join(sorted(letters))


def parse_numeric(value: str):
    try:
        num = float(value)
        if num.is_integer():
            return int(num)
        return num
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser(description="Parse score sheet (xls/xlsx) into responses.csv")
    parser.add_argument("--scores", required=True, help="Path to xls/xlsx file")
    parser.add_argument("--exam-id", required=True, help="Exam ID")
    parser.add_argument("--class-name", help="Class name if class column missing")
    parser.add_argument("--header-row", type=int, help="Header row index override (1-based)")
    parser.add_argument("--sheet", type=int, default=1, help="Sheet number (1-based). Default: 1")
    parser.add_argument("--sheet-name", help="Sheet name to parse (overrides --sheet)")
    parser.add_argument("--out", required=True, help="Output responses.csv")
    args = parser.parse_args()

    sheet_index = max(args.sheet - 1, 0)
    rows = list(iter_rows(Path(args.scores), sheet_index=sheet_index, sheet_name=args.sheet_name))

    header_row_idx = args.header_row
    header_cells = None

    if header_row_idx is None:
        for r_idx, row_cells in rows:
            values = {normalize_header_value(v) for v in row_cells.values()}
            if "姓名" in values and ("班级" in values or "准考证号" in values):
                header_row_idx = r_idx
                header_cells = row_cells
                break
    else:
        for r_idx, row_cells in rows:
            if r_idx == header_row_idx:
                header_cells = row_cells
                break

    if header_row_idx is None or header_cells is None:
        raise SystemExit("Header row not found. Use --header-row to specify it.")

    # Build header map
    header_by_col = {col: normalize_header_value(val) for col, val in header_cells.items()}

    # Identify meta columns
    meta_cols = {name: col for col, name in header_by_col.items() if name in META_HEADERS}

    if "姓名" not in meta_cols:
        raise SystemExit("Required column '姓名' not found in header.")

    if "班级" not in meta_cols and not args.class_name:
        # class name not present, must be provided
        print("[WARN] 班级列缺失，使用 --class-name 参数作为班级。")

    # Identify question columns
    question_cols = {}
    for col, name in header_by_col.items():
        if name in META_HEADERS or name == "":
            continue
        parsed = parse_question_label(name)
        if parsed:
            q_no, sub_no, raw_label = parsed
            question_cols[col] = (q_no, sub_no, raw_label)

    if not question_cols:
        raise SystemExit("No question columns detected.")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
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
        ])

        data_started = False
        for r_idx, row_cells in rows:
            if r_idx <= header_row_idx:
                continue
            # Require name to treat as data row
            name_cell = row_cells.get(meta_cols.get("姓名"))
            student_name = (name_cell or "").strip()
            if not student_name:
                if data_started:
                    continue
                else:
                    continue
            data_started = True

            class_cell = row_cells.get(meta_cols.get("班级"), "") if "班级" in meta_cols else ""
            class_name = (class_cell or "").strip() or (args.class_name or "")

            student_id = f"{class_name}_{student_name}" if class_name else student_name
            student_id = re.sub(r"\s+", "_", student_id.strip())

            for col, (q_no, sub_no, raw_label) in question_cols.items():
                raw = row_cells.get(col, "")
                raw_value = str(raw).strip()
                if raw_value == "":
                    continue
                score = parse_numeric(raw_value)
                raw_answer = ""
                if score is None:
                    raw_answer = normalize_answer(raw_value)
                question_id = f"Q{q_no}{sub_no}" if sub_no else f"Q{q_no}"

                writer.writerow([
                    args.exam_id,
                    student_id,
                    student_name,
                    class_name,
                    question_id,
                    q_no,
                    sub_no or "",
                    raw_label,
                    raw_value,
                    raw_answer,
                    "" if score is None else score,
                ])

    print(f"[OK] Wrote {out_path}")


if __name__ == "__main__":
    main()
