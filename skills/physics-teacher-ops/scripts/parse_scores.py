#!/usr/bin/env python3
import argparse
import csv
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

NS = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

NAME_HEADERS = {"姓名", "考生姓名", "学生姓名"}
ID_HEADERS = {"准考证号", "考号", "学号", "自定义考号"}
CLASS_HEADERS = {"班级", "行政班", "教学班", "班别"}
TOTAL_HEADERS = {"总分", "总成绩"}
SUBJECT_HEADERS = {"科目", "学科", "选科", "科目名称", "选考科目"}
SCORE_HEADERS = {"分数", "成绩", "得分", "科目分数", "科目成绩"}

HEADER_HINT_KEYWORDS = (
    "姓名",
    "考生",
    "学生",
    "考号",
    "学号",
    "班级",
    "科目",
    "物理",
    "成绩",
    "分数",
    "总分",
)

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


def is_plausible_score(value: Any) -> bool:
    try:
        score = float(value)
    except Exception:
        return False
    return 0.0 <= score <= 200.0


def is_probable_student_name(value: str) -> bool:
    s = normalize_header_value(value)
    if not s:
        return False
    if is_summary_student_name(s):
        return False
    comp = compact_text(s)
    if any(k in comp for k in ("姓名", "考生", "学生", "科目", "分数", "成绩", "总分", "班级", "考号", "学号")):
        return False
    return bool(re.fullmatch(r"[\u4e00-\u9fa5·]{2,6}", s))


def is_probable_student_id_token(value: str) -> bool:
    token = normalize_header_value(value)
    if not token:
        return False
    if not re.fullmatch(r"[A-Za-z0-9_-]{6,24}", token):
        return False
    return sum(ch.isdigit() for ch in token) >= 4


def infer_name_col(rows, header_row_idx: int, id_col: Optional[int], class_col: Optional[int]) -> Optional[int]:
    stats: Dict[int, Dict[str, int]] = {}
    for r_idx, row_cells in rows:
        if r_idx <= header_row_idx:
            continue
        for col, raw in row_cells.items():
            if col in {id_col, class_col}:
                continue
            value = normalize_header_value(raw)
            if not value:
                continue
            bucket = stats.setdefault(col, {"non_empty": 0, "name_like": 0})
            bucket["non_empty"] += 1
            if is_probable_student_name(value):
                bucket["name_like"] += 1

    best_col = None
    best_score = -1.0
    for col, item in stats.items():
        non_empty = int(item.get("non_empty") or 0)
        name_like = int(item.get("name_like") or 0)
        if non_empty <= 0 or name_like < 2:
            continue
        ratio = name_like / non_empty
        score = (name_like * 1.0) + (ratio * 2.0)
        if ratio < 0.35:
            continue
        if score > best_score:
            best_score = score
            best_col = col
    return best_col


def infer_student_name_from_row(
    row_cells: Dict[int, Any],
    *,
    excluded_cols: Optional[set[int]] = None,
) -> str:
    excluded_cols = excluded_cols or set()
    for col in sorted(row_cells.keys()):
        if col in excluded_cols:
            continue
        value = normalize_header_value(row_cells.get(col, ""))
        if is_probable_student_name(value):
            return value
    return ""


def infer_student_id_from_row(
    row_cells: Dict[int, Any],
    *,
    id_col: Optional[int],
    excluded_cols: Optional[set[int]] = None,
) -> str:
    if id_col is not None:
        sid = normalize_header_value(row_cells.get(id_col, ""))
        if sid:
            return sid

    excluded_cols = excluded_cols or set()
    for col in sorted(row_cells.keys()):
        if col in excluded_cols:
            continue
        value = normalize_header_value(row_cells.get(col, ""))
        if not value:
            continue
        if is_probable_student_id_token(value):
            return value
    return ""


def row_contains_physics_token(row_cells: Dict[int, Any]) -> bool:
    for raw in row_cells.values():
        comp = compact_text(raw)
        if "物理" in comp or "physics" in comp:
            return True
    return False


def extract_physics_score_from_row(row_cells: Dict[int, Any], header_by_col: Dict[int, str]) -> Optional[Tuple[float, str, str]]:
    ordered_cols = sorted(row_cells.keys())

    for col in ordered_cols:
        raw = normalize_header_value(row_cells.get(col, ""))
        if not raw:
            continue
        comp = compact_text(raw)
        if "物理" not in comp and "physics" not in comp:
            continue

        inline = re.search(r"(?:物理|physics)[^0-9\-]{0,8}([0-9]+(?:\.[0-9]+)?)", raw, flags=re.IGNORECASE)
        if inline:
            inline_raw = inline.group(1)
            score_inline = parse_numeric(inline_raw)
            if score_inline is not None and is_plausible_score(score_inline):
                return float(score_inline), inline_raw, "物理"

        for offset in (1, 2, -1):
            near_raw = normalize_header_value(row_cells.get(col + offset, ""))
            score_near = parse_numeric(near_raw)
            if score_near is not None and is_plausible_score(score_near):
                return float(score_near), near_raw, "物理"

    for col in ordered_cols:
        header = header_by_col.get(col, "")
        if not is_physics_score_header(header):
            continue
        raw = normalize_header_value(row_cells.get(col, ""))
        score = parse_numeric(raw)
        if score is not None and is_plausible_score(score):
            return float(score), raw, header or "物理"

    row_text = " ".join(
        [normalize_header_value(row_cells.get(col, "")) for col in ordered_cols if normalize_header_value(row_cells.get(col, ""))]
    )
    if row_text:
        text_hit = extract_physics_score_from_text(row_text)
        if text_hit is not None:
            score, raw = text_hit
            return float(score), raw, "物理"
    return None


def extract_physics_score_from_text(text: str) -> Optional[Tuple[float, str]]:
    row_text = normalize_header_value(text)
    if not row_text:
        return None
    for pattern in (
        r"(?:物理|physics)[^0-9\-]{0,8}([0-9]+(?:\.[0-9]+)?)",
        r"([0-9]+(?:\.[0-9]+)?)\s*(?:分)?\s*(?:物理|physics)",
    ):
        m = re.search(pattern, row_text, flags=re.IGNORECASE)
        if not m:
            continue
        raw = m.group(1)
        score = parse_numeric(raw)
        if score is not None and is_plausible_score(score):
            return float(score), raw
    return None


def extract_plausible_score_token_from_text(text: str) -> Optional[Tuple[float, str]]:
    raw_text = normalize_header_value(text)
    if not raw_text:
        return None
    tokens = re.findall(r"-?\d+(?:\.\d+)?", raw_text)
    for token in reversed(tokens):
        score = parse_numeric(token)
        if score is None or not is_plausible_score(score):
            continue
        return float(score), token
    return None


def extract_name_and_id_from_text_line(text: str) -> Tuple[str, str]:
    raw_text = normalize_header_value(text)
    if not raw_text:
        return "", ""
    name = ""
    student_id = ""
    parts = re.split(r"[\s,，;；|]+", raw_text)
    for part in parts:
        token = normalize_header_value(part)
        token = re.sub(r"^[^\w\u4e00-\u9fa5]+|[^\w\u4e00-\u9fa5]+$", "", token)
        if not token:
            continue
        if not student_id and is_probable_student_id_token(token):
            student_id = token
        if not name and is_probable_student_name(token):
            name = token
        if name and student_id:
            break
    return name, student_id


def extract_chaos_rows_from_sheet_text(
    rows,
    *,
    start_row_idx: int,
    class_name_hint: str,
    existing_student_keys: Optional[set[str]] = None,
) -> Tuple[List[Dict[str, Any]], int]:
    extracted: List[Dict[str, Any]] = []
    attempted = 0
    seen_keys = set(existing_student_keys or set())
    context_name = ""
    context_id = ""
    physics_context_ttl = 0

    for r_idx, row_cells in rows:
        if r_idx <= start_row_idx:
            continue
        ordered_cols = sorted(row_cells.keys())
        raw_values = [normalize_header_value(row_cells.get(col, "")) for col in ordered_cols]
        values = [value for value in raw_values if value]
        if not values:
            physics_context_ttl = max(0, physics_context_ttl - 1)
            continue

        row_text = " ".join(values)
        line_name, line_id = extract_name_and_id_from_text_line(row_text)
        if line_name:
            context_name = line_name
        if line_id:
            context_id = line_id

        row_comp = compact_text(row_text)
        has_physics_token = ("物理" in row_comp) or ("physics" in row_comp)
        if has_physics_token:
            physics_context_ttl = max(physics_context_ttl, 2)

        score_hit = extract_physics_score_from_text(row_text)
        if score_hit is None and physics_context_ttl > 0:
            score_hit = extract_plausible_score_token_from_text(row_text)
        if score_hit is None:
            if has_physics_token or physics_context_ttl > 0:
                attempted += 1
            physics_context_ttl = max(0, physics_context_ttl - 1)
            continue

        attempted += 1
        score_value, raw_value = score_hit
        student_name = line_name or context_name
        student_id = line_id or context_id
        if not student_name and not student_id:
            physics_context_ttl = max(0, physics_context_ttl - 1)
            continue
        if not student_name:
            student_name = student_id
        if not student_id:
            student_id = re.sub(r"\s+", "_", (student_name or f"row_{r_idx}").strip())

        dedupe_key = student_id or student_name
        if dedupe_key in seen_keys:
            physics_context_ttl = max(0, physics_context_ttl - 1)
            continue
        seen_keys.add(dedupe_key)
        extracted.append(
            {
                "row_idx": r_idx,
                "student_id": student_id,
                "student_name": student_name,
                "class_name": class_name_hint,
                "raw_value": raw_value,
                "score": float(score_value),
            }
        )
        physics_context_ttl = max(0, physics_context_ttl - 1)

    return extracted, attempted


def candidate_source_rank(candidate_id: str) -> int:
    cid = str(candidate_id or "").strip()
    if cid.startswith("pair:"):
        return 1
    if cid.startswith("direct:"):
        return 2
    if cid == "chaos:text":
        return 3
    if cid == "chaos:sheet_text":
        return 4
    return 9


def should_replace_subject_result(prev: Dict[str, Any], new_item: Dict[str, Any]) -> bool:
    prev_rank = int(prev.get("candidate_rank") or 99)
    new_rank = int(new_item.get("candidate_rank") or 99)
    if new_rank != prev_rank:
        return new_rank < prev_rank

    prev_score = float(prev.get("score") or 0.0)
    new_score = float(new_item.get("score") or 0.0)
    if new_score != prev_score:
        return new_score > prev_score

    prev_id_quality = 2 if is_probable_student_id_token(str(prev.get("student_id") or "")) else (1 if str(prev.get("student_id") or "").strip() else 0)
    new_id_quality = 2 if is_probable_student_id_token(str(new_item.get("student_id") or "")) else (1 if str(new_item.get("student_id") or "").strip() else 0)
    return new_id_quality > prev_id_quality


def merge_subject_result_items(current: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    keep = dict(current)
    drop = dict(incoming)
    if should_replace_subject_result(current, incoming):
        keep, drop = dict(incoming), dict(current)

    if not str(keep.get("student_name") or "").strip() and str(drop.get("student_name") or "").strip():
        keep["student_name"] = str(drop.get("student_name") or "").strip()
    keep_id = str(keep.get("student_id") or "").strip()
    drop_id = str(drop.get("student_id") or "").strip()
    if (not keep_id or not is_probable_student_id_token(keep_id)) and is_probable_student_id_token(drop_id):
        keep["student_id"] = drop_id
    elif not keep_id and drop_id:
        keep["student_id"] = drop_id
    if not str(keep.get("class_name") or "").strip() and str(drop.get("class_name") or "").strip():
        keep["class_name"] = str(drop.get("class_name") or "").strip()
    if not str(keep.get("raw_label") or "").strip() and str(drop.get("raw_label") or "").strip():
        keep["raw_label"] = str(drop.get("raw_label") or "").strip()
    if not str(keep.get("raw_value") or "").strip() and str(drop.get("raw_value") or "").strip():
        keep["raw_value"] = str(drop.get("raw_value") or "").strip()
    return keep


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


def detect_loose_header_row(rows) -> Tuple[Optional[int], Optional[Dict[int, str]]]:
    best_row_idx: Optional[int] = None
    best_cells: Optional[Dict[int, str]] = None
    best_score = -1.0
    for r_idx, row_cells in rows:
        values = [normalize_header_value(v) for v in row_cells.values() if normalize_header_value(v)]
        if len(values) < 2:
            continue
        keyword_hits = 0
        text_like = 0
        numeric_scores = 0
        for value in values:
            comp = compact_text(value)
            if any(key in comp for key in HEADER_HINT_KEYWORDS):
                keyword_hits += 1
            if not re.fullmatch(r"[-+]?\d+(?:\.\d+)?", value):
                text_like += 1
            parsed = parse_numeric(value)
            if parsed is not None and is_plausible_score(parsed):
                numeric_scores += 1

        row_text = " ".join(values)
        row_comp = compact_text(row_text)
        has_physics_token = ("物理" in row_comp) or ("physics" in row_comp)
        line_name, line_id = extract_name_and_id_from_text_line(row_text)

        data_penalty = 0.0
        if line_name and line_id:
            data_penalty += 8.0
        if has_physics_token and numeric_scores >= 1:
            data_penalty += 6.0
        if numeric_scores >= 2:
            data_penalty += 3.0

        score = (keyword_hits * 5.0) + text_like - data_penalty
        if score > best_score:
            best_score = score
            best_row_idx = r_idx
            best_cells = row_cells
    return best_row_idx, best_cells


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
    parser.add_argument("--subject-candidate-id", help="Optional selected subject mapping candidate id")
    args = parser.parse_args()
    report_path = Path(args.report) if args.report else None
    selected_candidate_id = str(args.subject_candidate_id or "").strip()

    sheet_index = max(args.sheet - 1, 0)
    rows = list(iter_rows(Path(args.scores), sheet_index=sheet_index, sheet_name=args.sheet_name))

    header_row_idx, header_cells = detect_header_row(rows, args.header_row)
    header_detect_mode = "strict"
    if header_row_idx is None or header_cells is None:
        header_row_idx, header_cells = detect_loose_header_row(rows)
        if header_row_idx is not None and header_cells is not None:
            header_detect_mode = "loose"
    if header_row_idx is None or header_cells is None:
        header_row_idx = 0
        header_cells = {}
        header_detect_mode = "none"
        print("[WARN] 未识别到可靠表头，启用全表文本兜底解析。")

    header_by_col = {col: normalize_header_value(val) for col, val in header_cells.items()}
    class_col = find_first_col(header_by_col, is_class_header)
    id_col = find_first_col(header_by_col, is_id_header)
    name_col = find_first_col(header_by_col, is_name_header)
    name_col_inferred = False
    if name_col is None:
        inferred_name_col = infer_name_col(rows, header_row_idx, id_col=id_col, class_col=class_col)
        if inferred_name_col is not None:
            name_col = inferred_name_col
            name_col_inferred = True
            print(f"[WARN] 姓名列未显式命中，使用推断列: {name_col}")
        else:
            print("[WARN] 姓名列缺失，将逐行推断学生姓名。")

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
            subject_pairs.append(
                {
                    "candidate_id": f"pair:{col}:{score_col}",
                    "subject_col": col,
                    "subject_header": header_by_col.get(col, ""),
                    "score_col": score_col,
                    "score_header": header_by_col.get(score_col, ""),
                    "type": "subject_pair",
                }
            )

    direct_physics_candidates = [
        {
            "candidate_id": f"direct:{col}",
            "score_col": col,
            "score_header": header_by_col.get(col, ""),
            "type": "direct_physics",
        }
        for col, name in sorted(header_by_col.items())
        if col not in {name_col, class_col, id_col} and is_physics_score_header(name)
    ]

    chaos_subject_candidates: List[Dict[str, Any]] = []
    if not question_cols and not subject_pairs and not direct_physics_candidates:
        chaos_subject_candidates.append(
            {
                "candidate_id": "chaos:text",
                "type": "chaos_text_scan",
                "score_col": None,
                "score_header": "row_text_scan",
            }
        )
        chaos_subject_candidates.append(
            {
                "candidate_id": "chaos:sheet_text",
                "type": "chaos_sheet_text",
                "score_col": None,
                "score_header": "sheet_text_scan",
            }
        )

    candidate_metrics: Dict[str, Dict[str, Any]] = {}
    for item in list(subject_pairs) + list(direct_physics_candidates) + list(chaos_subject_candidates):
        candidate_id = str(item.get("candidate_id") or "").strip()
        if not candidate_id:
            continue
        candidate_metrics[candidate_id] = {
            "rows_considered": 0,
            "rows_parsed": 0,
            "rows_invalid": 0,
            "sample_rows": [],
        }

    def record_candidate_metric(
        candidate_id: str,
        *,
        considered: bool = False,
        parsed: bool = False,
        invalid: bool = False,
        student_id: str = "",
        student_name: str = "",
        class_name: str = "",
        raw_value: str = "",
        score: Optional[float] = None,
    ) -> None:
        if not candidate_id:
            return
        bucket = candidate_metrics.setdefault(
            candidate_id,
            {
                "rows_considered": 0,
                "rows_parsed": 0,
                "rows_invalid": 0,
                "sample_rows": [],
            },
        )
        if considered:
            bucket["rows_considered"] = int(bucket.get("rows_considered") or 0) + 1
        if parsed:
            bucket["rows_parsed"] = int(bucket.get("rows_parsed") or 0) + 1
        if invalid:
            bucket["rows_invalid"] = int(bucket.get("rows_invalid") or 0) + 1

        if not (parsed or invalid):
            return
        samples = bucket.get("sample_rows")
        if not isinstance(samples, list):
            samples = []
            bucket["sample_rows"] = samples
        if len(samples) >= 5:
            return
        sample_item: Dict[str, Any] = {
            "student_id": student_id,
            "student_name": student_name,
            "class_name": class_name,
            "raw_value": raw_value,
            "status": "parsed" if parsed else "invalid",
        }
        if parsed and score is not None:
            sample_item["score"] = int(score) if float(score).is_integer() else round(float(score), 3)
        samples.append(sample_item)

    candidate_ids = {
        str(item.get("candidate_id") or "")
        for item in (subject_pairs + direct_physics_candidates + chaos_subject_candidates)
        if str(item.get("candidate_id") or "").strip()
    }
    selected_candidate_available = True
    active_selected_candidate_id = selected_candidate_id
    if selected_candidate_id and selected_candidate_id not in candidate_ids:
        selected_candidate_available = False
        active_selected_candidate_id = ""
        print(f"[WARN] 所选映射 {selected_candidate_id} 不在当前文件候选中，回退自动匹配。")

    if not question_cols and not candidate_ids:
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
        chaos_rows_extracted = 0
        chaos_rows_attempted = 0
        chaos_sheet_rows_extracted = 0
        chaos_sheet_rows_attempted = 0
        existing_student_keys: set[str] = set()
        subject_result_by_student: Dict[str, Dict[str, Any]] = {}
        unresolved_students: list[str] = []
        for r_idx, row_cells in rows:
            if r_idx <= header_row_idx:
                continue

            excluded_cols = {col for col in (name_col, class_col, id_col) if col is not None}
            student_name = normalize_header_value(row_cells.get(name_col, "")) if name_col is not None else ""
            if not student_name:
                student_name = infer_student_name_from_row(row_cells, excluded_cols=excluded_cols)
            if is_summary_student_name(student_name):
                continue

            if not student_name:
                if question_cols:
                    continue
                if not row_contains_physics_token(row_cells):
                    continue
                student_name = f"ROW_{r_idx}"

            data_rows_total += 1

            class_name = ""
            if class_col is not None:
                class_name = normalize_header_value(row_cells.get(class_col, ""))
            class_name = class_name.strip() or (args.class_name or "")

            student_id = ""
            if id_col is not None:
                student_id = normalize_header_value(row_cells.get(id_col, ""))
            if not student_id:
                student_id = infer_student_id_from_row(row_cells, id_col=id_col, excluded_cols=excluded_cols)
            student_id = student_id.strip()
            if not student_id:
                student_id = f"{class_name}_{student_name}" if class_name else (student_name or f"row_{r_idx}")
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
            for candidate in subject_pairs:
                candidate_id = str(candidate.get("candidate_id") or "")
                if active_selected_candidate_id and candidate_id != active_selected_candidate_id:
                    continue
                subject_col = int(candidate.get("subject_col") or 0)
                score_col = int(candidate.get("score_col") or 0)
                subject_name = normalize_header_value(row_cells.get(subject_col, ""))
                if not is_physics_subject(subject_name):
                    continue
                subject_candidates_total += 1
                record_candidate_metric(
                    candidate_id,
                    considered=True,
                    student_id=student_id,
                    student_name=student_name,
                    class_name=class_name,
                )
                raw_value = normalize_header_value(row_cells.get(score_col, ""))
                score = parse_numeric(raw_value)
                if score is None:
                    subject_invalid_total += 1
                    record_candidate_metric(
                        candidate_id,
                        invalid=True,
                        student_id=student_id,
                        student_name=student_name,
                        class_name=class_name,
                        raw_value=raw_value,
                    )
                    continue
                record_candidate_metric(
                    candidate_id,
                    parsed=True,
                    student_id=student_id,
                    student_name=student_name,
                    class_name=class_name,
                    raw_value=raw_value,
                    score=float(score),
                )
                subject_candidates.append((float(score), raw_value, subject_name or "物理", candidate_id))

            if not subject_candidates:
                for candidate in direct_physics_candidates:
                    candidate_id = str(candidate.get("candidate_id") or "")
                    if active_selected_candidate_id and candidate_id != active_selected_candidate_id:
                        continue
                    score_col = int(candidate.get("score_col") or 0)
                    subject_candidates_total += 1
                    record_candidate_metric(
                        candidate_id,
                        considered=True,
                        student_id=student_id,
                        student_name=student_name,
                        class_name=class_name,
                    )
                    raw_value = normalize_header_value(row_cells.get(score_col, ""))
                    score = parse_numeric(raw_value)
                    if score is None:
                        subject_invalid_total += 1
                        record_candidate_metric(
                            candidate_id,
                            invalid=True,
                            student_id=student_id,
                            student_name=student_name,
                            class_name=class_name,
                            raw_value=raw_value,
                        )
                        continue
                    record_candidate_metric(
                        candidate_id,
                        parsed=True,
                        student_id=student_id,
                        student_name=student_name,
                        class_name=class_name,
                        raw_value=raw_value,
                        score=float(score),
                    )
                    subject_candidates.append((float(score), raw_value, "物理", candidate_id))

            if not subject_candidates and (not active_selected_candidate_id or active_selected_candidate_id == "chaos:text"):
                chaos_rows_attempted += 1
                record_candidate_metric(
                    "chaos:text",
                    considered=True,
                    student_id=student_id,
                    student_name=student_name,
                    class_name=class_name,
                )
                chaos_hit = extract_physics_score_from_row(row_cells, header_by_col)
                if chaos_hit is not None:
                    c_score, c_raw_value, c_label = chaos_hit
                    subject_candidates_total += 1
                    chaos_rows_extracted += 1
                    record_candidate_metric(
                        "chaos:text",
                        parsed=True,
                        student_id=student_id,
                        student_name=student_name,
                        class_name=class_name,
                        raw_value=c_raw_value,
                        score=float(c_score),
                    )
                    subject_candidates.append((float(c_score), c_raw_value, c_label or "物理", "chaos:text"))

            if not subject_candidates:
                unresolved_students.append(student_name)
                continue
            if len(subject_candidates) > 1:
                subject_multi_candidate_rows += 1

            best_score, raw_value, raw_label, best_candidate_id = sorted(subject_candidates, key=lambda x: x[0], reverse=True)[0]
            dedupe_key = student_id or student_name
            if dedupe_key:
                prev = subject_result_by_student.get(dedupe_key)
                next_rank = candidate_source_rank(best_candidate_id)
                should_replace = False
                if prev is None:
                    should_replace = True
                else:
                    prev_rank = int(prev.get("candidate_rank") or 99)
                    prev_score = float(prev.get("score") or 0.0)
                    if next_rank < prev_rank:
                        should_replace = True
                    elif next_rank == prev_rank and float(best_score) > prev_score:
                        should_replace = True
                if should_replace:
                    subject_result_by_student[dedupe_key] = {
                        "student_id": student_id,
                        "student_name": student_name,
                        "class_name": class_name,
                        "raw_label": raw_label,
                        "raw_value": raw_value,
                        "score": float(best_score),
                        "candidate_id": best_candidate_id,
                        "candidate_rank": next_rank,
                    }
                existing_student_keys.add(dedupe_key)

        if (
            not question_cols
            and (not active_selected_candidate_id or active_selected_candidate_id == "chaos:sheet_text")
            and any(str(item.get("candidate_id") or "") == "chaos:sheet_text" for item in chaos_subject_candidates)
        ):
            sheet_rows, sheet_attempted = extract_chaos_rows_from_sheet_text(
                rows,
                start_row_idx=header_row_idx,
                class_name_hint=(args.class_name or "").strip(),
                existing_student_keys=existing_student_keys,
            )
            chaos_sheet_rows_attempted = sheet_attempted
            for item in sheet_rows:
                student_id = str(item.get("student_id") or "").strip()
                student_name = str(item.get("student_name") or "").strip()
                class_name = str(item.get("class_name") or "").strip()
                raw_value = str(item.get("raw_value") or "").strip()
                score_value = parse_numeric(item.get("score"))
                if score_value is None or not is_plausible_score(score_value):
                    continue
                dedupe_key = student_id or student_name
                if not dedupe_key:
                    continue
                existing_student_keys.add(dedupe_key)
                prev = subject_result_by_student.get(dedupe_key)
                next_rank = candidate_source_rank("chaos:sheet_text")
                should_replace = False
                if prev is None:
                    should_replace = True
                else:
                    prev_rank = int(prev.get("candidate_rank") or 99)
                    prev_score = float(prev.get("score") or 0.0)
                    if next_rank < prev_rank:
                        should_replace = True
                    elif next_rank == prev_rank and float(score_value) > prev_score:
                        should_replace = True
                if should_replace:
                    subject_result_by_student[dedupe_key] = {
                        "student_id": student_id,
                        "student_name": student_name,
                        "class_name": class_name,
                        "raw_label": "物理",
                        "raw_value": raw_value,
                        "score": float(score_value),
                        "candidate_id": "chaos:sheet_text",
                        "candidate_rank": next_rank,
                    }
                chaos_sheet_rows_extracted += 1
                record_candidate_metric(
                    "chaos:sheet_text",
                    considered=True,
                    parsed=True,
                    student_id=student_id,
                    student_name=student_name,
                    class_name=class_name,
                    raw_value=raw_value,
                    score=float(score_value),
                )
            invalid_count = max(0, int(chaos_sheet_rows_attempted) - int(chaos_sheet_rows_extracted))
            for _ in range(invalid_count):
                record_candidate_metric(
                    "chaos:sheet_text",
                    considered=True,
                    invalid=True,
                    student_id="",
                    student_name="",
                    class_name="",
                    raw_value="",
                )

        if not question_cols:
            merged_by_key: Dict[str, Dict[str, Any]] = {}

            def _identity_keys(item: Dict[str, Any]) -> List[str]:
                keys: List[str] = []
                sid = str(item.get("student_id") or "").strip()
                sname = str(item.get("student_name") or "").strip()
                cname = str(item.get("class_name") or "").strip()
                if sid:
                    keys.append(f"sid:{sid}")
                if sname:
                    keys.append(f"name:{cname}|{sname}" if cname else f"name:{sname}")
                if sid and sname:
                    keys.append(f"sid_name:{sid}|{sname}")
                return keys

            for dedupe_key in sorted(subject_result_by_student.keys()):
                item = dict(subject_result_by_student.get(dedupe_key) or {})
                if not item:
                    continue
                identities = _identity_keys(item)
                if not identities:
                    continue

                anchor = None
                for key in identities:
                    if key in merged_by_key:
                        anchor = key
                        break
                if anchor is None:
                    anchor = identities[0]
                    merged_by_key[anchor] = item
                else:
                    previous_item = merged_by_key.get(anchor)
                    merged_item = merge_subject_result_items(merged_by_key.get(anchor) or {}, item)
                    if previous_item is not None:
                        for alias_key, alias_value in list(merged_by_key.items()):
                            if alias_value is previous_item:
                                merged_by_key[alias_key] = merged_item
                    merged_by_key[anchor] = merged_item
                current_item = merged_by_key.get(anchor) or {}
                for key in identities:
                    merged_by_key[key] = current_item

            emitted: set[int] = set()
            final_items: List[Dict[str, Any]] = []
            for item in merged_by_key.values():
                item_id = id(item)
                if item_id in emitted:
                    continue
                emitted.add(item_id)
                final_items.append(item)

            final_items.sort(
                key=lambda item: (
                    str(item.get("class_name") or ""),
                    str(item.get("student_name") or ""),
                    str(item.get("student_id") or ""),
                )
            )

            for item in final_items:
                student_id = str(item.get("student_id") or "").strip()
                student_name = str(item.get("student_name") or "").strip()
                class_name = str(item.get("class_name") or "").strip()
                raw_label = str(item.get("raw_label") or "物理").strip() or "物理"
                raw_value = str(item.get("raw_value") or "").strip()
                score_value = parse_numeric(item.get("score"))
                if score_value is None or not is_plausible_score(score_value):
                    continue
                score_out = int(score_value) if float(score_value).is_integer() else round(float(score_value), 3)
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

        if not question_cols and wrote_rows <= 0:
            has_sheet_candidate = any(
                str(item.get("candidate_id") or "") == "chaos:sheet_text" for item in chaos_subject_candidates
            )
            if not has_sheet_candidate:
                chaos_subject_candidates.append(
                    {
                        "candidate_id": "chaos:sheet_text",
                        "type": "chaos_sheet_text",
                        "score_col": None,
                        "score_header": "sheet_text_scan",
                    }
                )

            forced_rows, forced_attempted = extract_chaos_rows_from_sheet_text(
                rows,
                start_row_idx=0,
                class_name_hint=(args.class_name or "").strip(),
                existing_student_keys=set(),
            )
            chaos_sheet_rows_attempted = max(int(chaos_sheet_rows_attempted), int(forced_attempted))

            forced_written = 0
            for item in forced_rows:
                student_id = str(item.get("student_id") or "").strip()
                student_name = str(item.get("student_name") or "").strip()
                class_name = str(item.get("class_name") or "").strip()
                raw_value = str(item.get("raw_value") or "").strip()
                score_value = parse_numeric(item.get("score"))
                if score_value is None or not is_plausible_score(score_value):
                    continue
                score_out = int(score_value) if float(score_value).is_integer() else round(float(score_value), 3)
                writer.writerow(
                    [
                        args.exam_id,
                        student_id,
                        student_name,
                        class_name,
                        "SUBJECT_PHYSICS",
                        "",
                        "",
                        "物理",
                        raw_value,
                        "",
                        score_out,
                    ]
                )
                wrote_rows += 1
                subject_rows_extracted += 1
                chaos_sheet_rows_extracted += 1
                forced_written += 1
                record_candidate_metric(
                    "chaos:sheet_text",
                    considered=True,
                    parsed=True,
                    student_id=student_id,
                    student_name=student_name,
                    class_name=class_name,
                    raw_value=raw_value,
                    score=float(score_value),
                )

            invalid_count = max(0, int(forced_attempted) - int(forced_written))
            for _ in range(invalid_count):
                record_candidate_metric(
                    "chaos:sheet_text",
                    considered=True,
                    invalid=True,
                    student_id="",
                    student_name="",
                    class_name="",
                    raw_value="",
                )

            if forced_written > 0:
                print(f"[WARN] 常规解析未提取到有效数据，启用全表文本兜底提取 {forced_written} 条物理成绩。")

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
        "header_detect_mode": header_detect_mode,
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
        coverage_raw = (subject_rows_extracted / data_rows_total) if data_rows_total > 0 else 0.0
        coverage = max(0.0, min(1.0, coverage_raw))
        has_chaos_candidate = any(
            str(item.get("candidate_id") or "") in {"chaos:text", "chaos:sheet_text"}
            for item in chaos_subject_candidates
        )
        has_sheet_chaos = any(str(item.get("candidate_id") or "") == "chaos:sheet_text" for item in chaos_subject_candidates)
        header_score = 1.0 if (subject_pairs or direct_physics_candidates) else (0.45 if has_chaos_candidate else 0.0)
        layout_score = (
            1.0
            if subject_pairs
            else (0.72 if direct_physics_candidates else (0.28 if has_sheet_chaos else (0.35 if has_chaos_candidate else 0.0)))
        )
        value_score = (
            (subject_candidates_total - subject_invalid_total) / subject_candidates_total
            if subject_candidates_total > 0
            else 0.0
        )
        coverage_score = max(0.0, min(1.0, coverage))
        confidence = (0.35 * header_score) + (0.30 * layout_score) + (0.20 * value_score) + (0.15 * coverage_score)
        confidence = max(0.0, min(1.0, confidence))
        needs_confirm = bool((coverage < 0.85) or (confidence < 0.82))
        candidate_columns_enriched: List[Dict[str, Any]] = []
        for candidate in list(subject_pairs) + list(direct_physics_candidates) + list(chaos_subject_candidates):
            candidate_id = str(candidate.get("candidate_id") or "").strip()
            metrics = candidate_metrics.get(candidate_id) or {}
            candidate_columns_enriched.append(
                {
                    **candidate,
                    "rows_considered": int(metrics.get("rows_considered") or 0),
                    "rows_parsed": int(metrics.get("rows_parsed") or 0),
                    "rows_invalid": int(metrics.get("rows_invalid") or 0),
                    "sample_rows": list(metrics.get("sample_rows") or []),
                    "selected": bool(candidate_id and candidate_id == active_selected_candidate_id),
                }
            )
        report = merge_score_schema(
            report,
            {
                "confidence": round(confidence, 4),
                "needs_confirm": needs_confirm,
                "subject": {
                    "target": "physics",
                    "question_id": "SUBJECT_PHYSICS",
                    "selected_candidate_id": active_selected_candidate_id,
                    "selected_candidate_available": selected_candidate_available,
                    "requested_candidate_id": selected_candidate_id,
                    "coverage": round(coverage, 4),
                    "data_rows": data_rows_total,
                    "parsed_rows": subject_rows_extracted,
                    "unresolved_students": unresolved_students,
                    "multi_candidate_rows": subject_multi_candidate_rows,
                    "chaos_rows_attempted": chaos_rows_attempted,
                    "chaos_rows_extracted": chaos_rows_extracted,
                    "chaos_sheet_rows_attempted": chaos_sheet_rows_attempted,
                    "chaos_sheet_rows_extracted": chaos_sheet_rows_extracted,
                    "thresholds": {"coverage": 0.85, "confidence": 0.82},
                    "candidate_columns": candidate_columns_enriched,
                },
            },
        )

    if name_col_inferred:
        report["name_col_inferred"] = True
        report["name_col"] = name_col

    write_report(report_path, report)

    print(f"[OK] Wrote {out_path}")


if __name__ == "__main__":
    main()
