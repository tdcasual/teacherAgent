#!/usr/bin/env python3
import argparse
import csv
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Optional, Tuple

NS = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

NAME_HEADERS = {"姓名", "考生姓名", "学生姓名"}
ID_HEADERS = {"准考证号", "考号", "学号", "自定义考号"}
CLASS_HEADERS = {"班级", "行政班", "教学班", "班别"}
TOTAL_HEADERS = {"总分", "总成绩"}
SUBJECT_HEADERS = {"科目", "学科", "选科", "科目名称", "选考科目"}
SCORE_HEADERS = {"分数", "成绩", "得分", "科目分数", "科目成绩"}

META_HEADERS = {
    "序号",
    "姓名",
    "考生姓名",
    "学生姓名",
    "准考证号",
    "考号",
    "学号",
    "自定义考号",
    "班级",
    "行政班",
    "教学班",
    "班别",
    "总分",
    "总成绩",
    "校次",
    "班次",
    "班次/校次",
    "科目",
    "学科",
    "科目名称",
    "选考科目",
    "分数",
    "成绩",
    "得分",
}


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
    if re.fullmatch(r"\d+\.0", s):
        s = s[:-2]
    return s


def compact_text(value: str) -> str:
    s = normalize_header_value(value)
    s = re.sub(r"[\s/_\-（）()【】\[\]：:·.]", "", s)
    return s.strip().lower()


def _is_in_aliases(value: str, aliases: set[str]) -> bool:
    comp = compact_text(value)
    return comp in {compact_text(x) for x in aliases}


def is_rank_like_header(name: str) -> bool:
    comp = compact_text(name)
    return any(k in comp for k in ("排名", "名次", "班次", "校次", "位次", "次序"))


def is_name_header(name: str) -> bool:
    return _is_in_aliases(name, NAME_HEADERS)


def is_id_header(name: str) -> bool:
    return _is_in_aliases(name, ID_HEADERS)


def is_class_header(name: str) -> bool:
    return _is_in_aliases(name, CLASS_HEADERS)


def is_total_header(name: str) -> bool:
    comp = compact_text(name)
    return ("总分" in comp or "总成绩" in comp) and not is_rank_like_header(name)


def is_subject_header(name: str) -> bool:
    return _is_in_aliases(name, SUBJECT_HEADERS)


def is_score_header(name: str) -> bool:
    comp = compact_text(name)
    if is_rank_like_header(name):
        return False
    return _is_in_aliases(name, SCORE_HEADERS) or comp.endswith("分数") or comp.endswith("成绩")


def is_physics_subject(value: str) -> bool:
    comp = compact_text(value)
    return "物理" in comp


def is_physics_score_header(name: str) -> bool:
    comp = compact_text(name)
    if "物理" not in comp or is_rank_like_header(name):
        return False
    return ("分" in comp) or ("成绩" in comp) or ("得分" in comp) or ("赋分" in comp) or comp == "物理"


def parse_question_label(label: str):
    if not label:
        return None
    s = normalize_header_value(label)
    if not s:
        return None
    if re.fullmatch(r"\d+", s):
        return int(s), None, s
    m = re.fullmatch(r"(\d+)\(([^)]+)\)", s)
    if m:
        return int(m.group(1)), m.group(2), s
    m = re.fullmatch(r"(\d+)[-_]([A-Za-z0-9]+)", s)
    if m:
        return int(m.group(1)), m.group(2), s
    m = re.fullmatch(r"(\d+)([A-Za-z]+)", s)
    if m:
        return int(m.group(1)), m.group(2), s
    return None


def normalize_answer(value: str) -> str:
    s = str(value).strip().upper()
    letters = re.findall(r"[A-Z]", s)
    if not letters:
        return s
    return "".join(sorted(letters))


def parse_numeric(value: str):
    raw = str(value or "").strip()
    if not raw:
        return None
    if "/" in raw:
        return None
    norm = raw.replace(",", "")
    try:
        num = float(norm)
        if num.is_integer():
            return int(num)
        return num
    except Exception:
        return None


def merge_score_schema(base: Dict[str, object], update: Dict[str, object]) -> Dict[str, object]:
    out = dict(base)
    for key, value in (update or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            nested = dict(out.get(key) or {})
            nested.update(value)
            out[key] = nested
            continue
        out[key] = value
    return out


def write_report(path: Optional[Path], payload: Dict[str, object]) -> None:
    if not path:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def is_summary_student_name(value: str) -> bool:
    comp = compact_text(value)
    if not comp:
        return True
    prefixes = ("平均", "最高", "最低", "标准差", "及格", "优秀", "总计", "合计", "人数")
    return any(comp.startswith(prefix) for prefix in prefixes)


def find_first_col(header_by_col: Dict[int, str], predicate) -> Optional[int]:
    for col in sorted(header_by_col.keys()):
        if predicate(header_by_col[col]):
            return col
    return None


def detect_header_row(rows, explicit_header_row: Optional[int]) -> Tuple[Optional[int], Optional[Dict[int, str]]]:
    if explicit_header_row is not None:
        for r_idx, row_cells in rows:
            if r_idx == explicit_header_row:
                return r_idx, row_cells
        return None, None

    for r_idx, row_cells in rows:
        values = [normalize_header_value(v) for v in row_cells.values() if normalize_header_value(v)]
        if not values:
            continue
        has_name = any(is_name_header(v) for v in values)
        has_structure = any(
            is_class_header(v) or is_id_header(v) or is_total_header(v) or is_subject_header(v)
            for v in values
        )
        if has_name and has_structure:
            return r_idx, row_cells
    return None, None


def main():
    parser = argparse.ArgumentParser(description="Parse score sheet (xls/xlsx) into responses.csv")
    parser.add_argument("--scores", required=True, help="Path to xls/xlsx file")
    parser.add_argument("--exam-id", required=True, help="Exam ID")
    parser.add_argument("--class-name", help="Class name if class column missing")
    parser.add_argument("--header-row", type=int, help="Header row index override (1-based)")
    parser.add_argument("--sheet", type=int, default=1, help="Sheet number (1-based). Default: 1")
    parser.add_argument("--sheet-name", help="Sheet name to parse (overrides --sheet)")
    parser.add_argument("--out", required=True, help="Output responses.csv")
    parser.add_argument("--report", help="Optional parser report json output")
    args = parser.parse_args()
    report_path = Path(args.report) if args.report else None

    sheet_index = max(args.sheet - 1, 0)
    rows = list(iter_rows(Path(args.scores), sheet_index=sheet_index, sheet_name=args.sheet_name))

    header_row_idx, header_cells = detect_header_row(rows, args.header_row)
    if header_row_idx is None or header_cells is None:
        raise SystemExit("Header row not found. Use --header-row to specify it.")

    header_by_col = {col: normalize_header_value(val) for col, val in header_cells.items()}
    name_col = find_first_col(header_by_col, is_name_header)
    if name_col is None:
        raise SystemExit("Required name column not found (姓名/考生姓名).")

    class_col = find_first_col(header_by_col, is_class_header)
    id_col = find_first_col(header_by_col, is_id_header)

    if class_col is None and not args.class_name:
        print("[WARN] 班级列缺失，使用 --class-name 参数作为班级。")

    question_cols = {}
    for col, name in header_by_col.items():
        if col in {name_col, class_col, id_col}:
            continue
        if name in META_HEADERS or name == "":
            continue
        if is_total_header(name) or is_subject_header(name) or is_score_header(name) or is_rank_like_header(name):
            continue
        parsed = parse_question_label(name)
        if parsed:
            q_no, sub_no, raw_label = parsed
            question_cols[col] = (q_no, sub_no, raw_label)

    subject_pairs = []
    for col, name in sorted(header_by_col.items()):
        if not is_subject_header(name):
            continue
        score_col = None
        for offset in (1, 2):
            candidate = col + offset
            if is_score_header(header_by_col.get(candidate, "")):
                score_col = candidate
                break
        if score_col is not None:
            subject_pairs.append((col, score_col))

    direct_physics_cols = [
        col
        for col, name in sorted(header_by_col.items())
        if col not in {name_col, class_col, id_col} and is_physics_score_header(name)
    ]

    if not question_cols and not subject_pairs and not direct_physics_cols:
        write_report(
            report_path,
            {
                "ok": False,
                "mode": "unknown",
                "error": "no_question_or_subject_columns",
                "header_row": header_row_idx,
            },
        )
        raise SystemExit("No question columns detected.")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
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
            ]
        )

        wrote_rows = 0
        data_rows_total = 0
        subject_rows_extracted = 0
        subject_candidates_total = 0
        subject_invalid_total = 0
        subject_multi_candidate_rows = 0
        unresolved_students: list[str] = []
        for r_idx, row_cells in rows:
            if r_idx <= header_row_idx:
                continue

            name_cell = row_cells.get(name_col)
            student_name = normalize_header_value(name_cell)
            if is_summary_student_name(student_name):
                continue
            data_rows_total += 1

            class_name = ""
            if class_col is not None:
                class_name = normalize_header_value(row_cells.get(class_col, ""))
            class_name = class_name.strip() or (args.class_name or "")

            student_id = ""
            if id_col is not None:
                student_id = normalize_header_value(row_cells.get(id_col, ""))
            student_id = student_id.strip()
            if not student_id:
                student_id = f"{class_name}_{student_name}" if class_name else student_name
                student_id = re.sub(r"\s+", "_", student_id.strip())

            if question_cols:
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

                    writer.writerow(
                        [
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
                        ]
                    )
                    wrote_rows += 1
                continue

            subject_candidates = []
            for subject_col, score_col in subject_pairs:
                subject_name = normalize_header_value(row_cells.get(subject_col, ""))
                if not is_physics_subject(subject_name):
                    continue
                subject_candidates_total += 1
                raw_value = normalize_header_value(row_cells.get(score_col, ""))
                score = parse_numeric(raw_value)
                if score is None:
                    subject_invalid_total += 1
                    continue
                subject_candidates.append((float(score), raw_value, subject_name or "物理"))

            if not subject_candidates:
                for score_col in direct_physics_cols:
                    subject_candidates_total += 1
                    raw_value = normalize_header_value(row_cells.get(score_col, ""))
                    score = parse_numeric(raw_value)
                    if score is None:
                        subject_invalid_total += 1
                        continue
                    subject_candidates.append((float(score), raw_value, "物理"))

            if not subject_candidates:
                unresolved_students.append(student_name)
                continue
            if len(subject_candidates) > 1:
                subject_multi_candidate_rows += 1

            best_score, raw_value, raw_label = sorted(subject_candidates, key=lambda x: x[0], reverse=True)[0]
            score_out = int(best_score) if float(best_score).is_integer() else round(best_score, 3)
            writer.writerow(
                [
                    args.exam_id,
                    student_id,
                    student_name,
                    class_name,
                    "SUBJECT_PHYSICS",
                    "",
                    "",
                    raw_label,
                    raw_value,
                    "",
                    score_out,
                ]
            )
            wrote_rows += 1
            subject_rows_extracted += 1

    if wrote_rows <= 0:
        write_report(
            report_path,
            {
                "ok": False,
                "mode": "unknown",
                "error": "no_usable_rows",
                "header_row": header_row_idx,
            },
        )
        raise SystemExit("No usable score rows detected.")

    mode = "question" if question_cols else "subject"
    report: Dict[str, object] = {
        "ok": True,
        "mode": mode,
        "header_row": header_row_idx,
        "summary": {
            "data_rows": data_rows_total,
            "parsed_rows": wrote_rows,
        },
    }
    if mode == "question":
        report = merge_score_schema(
            report,
            {
                "confidence": 1.0,
                "needs_confirm": False,
                "question_columns": [
                    {
                        "col": col,
                        "header": header_by_col.get(col, ""),
                    }
                    for col in sorted(question_cols.keys())
                ],
            },
        )
    else:
        coverage = (subject_rows_extracted / data_rows_total) if data_rows_total > 0 else 0.0
        header_score = 1.0 if (subject_pairs or direct_physics_cols) else 0.0
        layout_score = 1.0 if subject_pairs else (0.72 if direct_physics_cols else 0.0)
        value_score = (
            (subject_candidates_total - subject_invalid_total) / subject_candidates_total
            if subject_candidates_total > 0
            else 0.0
        )
        coverage_score = max(0.0, min(1.0, coverage))
        confidence = (0.35 * header_score) + (0.30 * layout_score) + (0.20 * value_score) + (0.15 * coverage_score)
        confidence = max(0.0, min(1.0, confidence))
        needs_confirm = bool((coverage < 0.85) or (confidence < 0.82))
        report = merge_score_schema(
            report,
            {
                "confidence": round(confidence, 4),
                "needs_confirm": needs_confirm,
                "subject": {
                    "target": "physics",
                    "question_id": "SUBJECT_PHYSICS",
                    "coverage": round(coverage, 4),
                    "data_rows": data_rows_total,
                    "parsed_rows": subject_rows_extracted,
                    "unresolved_students": unresolved_students,
                    "multi_candidate_rows": subject_multi_candidate_rows,
                    "thresholds": {"coverage": 0.85, "confidence": 0.82},
                    "candidate_columns": [
                        {
                            "subject_col": subject_col,
                            "subject_header": header_by_col.get(subject_col, ""),
                            "score_col": score_col,
                            "score_header": header_by_col.get(score_col, ""),
                            "type": "subject_pair",
                        }
                        for subject_col, score_col in subject_pairs
                    ]
                    + [
                        {
                            "score_col": score_col,
                            "score_header": header_by_col.get(score_col, ""),
                            "type": "direct_physics",
                        }
                        for score_col in direct_physics_cols
                    ],
                },
            },
        )

    write_report(report_path, report)

    print(f"[OK] Wrote {out_path}")


if __name__ == "__main__":
    main()
