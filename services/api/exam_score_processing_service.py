from __future__ import annotations

import csv
import logging
import math
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


_log = logging.getLogger(__name__)


def parse_score_value(value: Any) -> Optional[float]:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        return float(s)
    except Exception:
        return None


def normalize_student_id_for_exam(class_name: str, student_name: str) -> str:
    base = f"{(class_name or '').strip()}_{(student_name or '').strip()}" if class_name else (student_name or "").strip()
    base = re.sub(r"\s+", "_", base)
    return base.strip("_") or (student_name or "").strip() or "unknown"


def normalize_excel_cell(value: Any) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    if re.fullmatch(r"\d+\.0", s):
        s = s[:-2]
    return s


def parse_exam_question_label(label: str) -> Optional[Tuple[int, Optional[str], str]]:
    if not label:
        return None
    s = normalize_excel_cell(label)
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


def build_exam_question_id(q_no: int, sub_no: Optional[str]) -> str:
    if sub_no:
        return f"Q{q_no}{sub_no}"
    return f"Q{q_no}"


def build_exam_rows_from_parsed_scores(exam_id: str, parsed: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[str]]:
    mode = str(parsed.get("mode") or "").strip().lower()
    if mode not in {"question", "total"}:
        mode = "question" if parsed.get("questions") else "total"
    warnings: List[str] = []
    if isinstance(parsed.get("warnings"), list):
        warnings.extend([str(x) for x in parsed.get("warnings") if x])

    students = parsed.get("students") or []
    if not isinstance(students, list):
        return [], [], ["students_missing_or_invalid"]

    questions_out: Dict[str, Dict[str, Any]] = {}
    questions_in = parsed.get("questions") or []
    if isinstance(questions_in, list):
        for item in questions_in:
            if not isinstance(item, dict):
                continue
            raw_label = str(item.get("raw_label") or "").strip()
            q_no = item.get("question_no")
            sub_no = str(item.get("sub_no") or "").strip() or None
            qid = str(item.get("question_id") or "").strip()
            if not qid and q_no:
                try:
                    qid = build_exam_question_id(int(q_no), sub_no)
                except Exception:
                    qid = ""
            if not raw_label and qid:
                raw_label = qid
            if not qid:
                continue
            questions_out[qid] = {
                "question_id": qid,
                "question_no": str(q_no or "").strip(),
                "sub_no": str(sub_no or "").strip(),
            }

    rows: List[Dict[str, Any]] = []
    for s in students:
        if not isinstance(s, dict):
            continue
        student_name = str(s.get("student_name") or "").strip()
        class_name = str(s.get("class_name") or "").strip()
        student_id = str(s.get("student_id") or "").strip() or normalize_student_id_for_exam(class_name, student_name)
        if not student_name:
            if not student_id:
                continue
        if mode == "total":
            total_score = parse_score_value(s.get("total_score"))
            if total_score is None:
                continue
            rows.append(
                {
                    "exam_id": exam_id,
                    "student_id": student_id,
                    "student_name": student_name,
                    "class_name": class_name,
                    "question_id": "TOTAL",
                    "question_no": "",
                    "sub_no": "",
                    "raw_label": "TOTAL",
                    "raw_value": str(total_score),
                    "raw_answer": "",
                    "score": total_score,
                    "is_correct": "",
                }
            )
            continue

        scores_map = s.get("scores") or {}
        if isinstance(scores_map, list):
            converted: Dict[str, Any] = {}
            for item in scores_map:
                if not isinstance(item, dict):
                    continue
                lbl = str(item.get("raw_label") or item.get("label") or "").strip()
                converted[lbl] = item.get("score")
            scores_map = converted
        if not isinstance(scores_map, dict):
            continue
        for raw_label, raw_score in scores_map.items():
            raw_label_str = str(raw_label or "").strip()
            if not raw_label_str:
                continue
            score = parse_score_value(raw_score)
            if score is None:
                continue
            parsed_label = parse_exam_question_label(raw_label_str)
            if parsed_label:
                q_no, sub_no, raw_norm = parsed_label
                qid = build_exam_question_id(q_no, sub_no)
                question_no = str(q_no)
                sub_no_str = str(sub_no or "")
                raw_label_final = raw_norm
            else:
                qid = raw_label_str if raw_label_str.startswith("Q") else f"Q{raw_label_str}"
                question_no = ""
                sub_no_str = ""
                raw_label_final = raw_label_str
            if qid not in questions_out:
                questions_out[qid] = {"question_id": qid, "question_no": question_no, "sub_no": sub_no_str}
            rows.append(
                {
                    "exam_id": exam_id,
                    "student_id": student_id,
                    "student_name": student_name,
                    "class_name": class_name,
                    "question_id": qid,
                    "question_no": question_no,
                    "sub_no": sub_no_str,
                    "raw_label": raw_label_final,
                    "raw_value": str(raw_score),
                    "raw_answer": "",
                    "score": score,
                    "is_correct": "",
                }
            )

    questions_list = list(questions_out.values())

    def _q_key(q: Dict[str, Any]) -> Tuple[int, str]:
        no = q.get("question_no") or ""
        try:
            no_int = int(str(no))
        except Exception:
            no_int = 9999
        return no_int, str(q.get("sub_no") or "")

    questions_list.sort(key=_q_key)
    return rows, questions_list, warnings


def write_exam_responses_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
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
            out = dict(row)
            if out.get("score") is not None:
                out["score"] = str(out["score"])
            writer.writerow({k: out.get(k, "") for k in fields})


def write_exam_questions_csv(path: Path, questions: List[Dict[str, Any]], max_scores: Optional[Dict[str, float]] = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["question_id", "question_no", "sub_no", "order", "max_score", "stem_ref"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for idx, q in enumerate(questions, start=1):
            qid = str(q.get("question_id") or "").strip()
            if not qid:
                continue
            max_score = None
            if max_scores and qid in max_scores:
                max_score = max_scores[qid]
            writer.writerow(
                {
                    "question_id": qid,
                    "question_no": str(q.get("question_no") or "").strip(),
                    "sub_no": str(q.get("sub_no") or "").strip(),
                    "order": str(idx),
                    "max_score": "" if max_score is None else str(max_score),
                    "stem_ref": "",
                }
            )


def compute_max_scores_from_rows(rows: List[Dict[str, Any]]) -> Dict[str, float]:
    max_scores: Dict[str, float] = {}
    for row in rows:
        qid = str(row.get("question_id") or "").strip()
        if not qid or qid == "TOTAL":
            continue
        score = row.get("score")
        if score is None:
            continue
        try:
            val = float(score)
        except Exception:
            continue
        prev = max_scores.get(qid)
        if prev is None or val > prev:
            max_scores[qid] = val
    return max_scores


def normalize_objective_answer(value: str) -> str:
    s = (value or "").strip().upper()
    letters = [ch for ch in s if "A" <= ch <= "Z"]
    if not letters:
        return s
    if len(letters) == 1:
        return letters[0]
    return "".join(sorted(set(letters)))


def parse_exam_answer_key_text(text: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    warnings: List[str] = []
    if not text or not text.strip():
        return [], ["答案文本为空"]

    items: Dict[str, Dict[str, Any]] = {}
    line_re = re.compile(
        r"^\s*(?P<label>\d+(?:\([^)]+\)|[-_][A-Za-z0-9]+|[A-Za-z]+)?)\s*[\.\):：\s]\s*(?P<ans>[A-Za-z]{1,8})\s*$"
    )
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        m = line_re.match(line)
        if not m:
            continue
        label = m.group("label").strip()
        ans = normalize_objective_answer(m.group("ans"))
        if not ans:
            continue
        parsed = parse_exam_question_label(label)
        if parsed:
            q_no, sub_no, raw_norm = parsed
            qid = build_exam_question_id(q_no, sub_no)
            q_no_str = str(q_no)
            sub_no_str = str(sub_no or "")
            raw_label = raw_norm
        else:
            qid = label if label.upper().startswith("Q") else f"Q{label}"
            q_no_str = ""
            sub_no_str = ""
            raw_label = label
        items[qid] = {
            "question_id": qid,
            "question_no": q_no_str,
            "sub_no": sub_no_str,
            "raw_label": raw_label,
            "correct_answer": ans,
        }

    if not items:
        inline_re = re.compile(
            r"(?P<label>\d+(?:\([^)]+\)|[-_][A-Za-z0-9]+|[A-Za-z]+)?)\s*[\.\):：]\s*(?P<ans>[A-Za-z]{1,8})",
        )
        for m in inline_re.finditer(text):
            label = (m.group("label") or "").strip()
            ans = normalize_objective_answer(m.group("ans"))
            if not label or not ans:
                continue
            parsed = parse_exam_question_label(label)
            if parsed:
                q_no, sub_no, raw_norm = parsed
                qid = build_exam_question_id(q_no, sub_no)
                q_no_str = str(q_no)
                sub_no_str = str(sub_no or "")
                raw_label = raw_norm
            else:
                qid = label if label.upper().startswith("Q") else f"Q{label}"
                q_no_str = ""
                sub_no_str = ""
                raw_label = label
            items[qid] = {
                "question_id": qid,
                "question_no": q_no_str,
                "sub_no": sub_no_str,
                "raw_label": raw_label,
                "correct_answer": ans,
            }

    if not items:
        warnings.append("未能从答案文本中识别出“题号-答案”结构（建议上传更清晰的答案PDF/图片，或使用可复制文本的答案文件）。")
    rows = list(items.values())

    def _k(r: Dict[str, Any]) -> Tuple[int, str]:
        qid = str(r.get("question_id") or "")
        m = re.match(r"^Q(\d+)", qid)
        if m:
            return int(m.group(1)), qid
        return 9999, qid

    rows.sort(key=_k)
    return rows, warnings


def write_exam_answers_csv(path: Path, answers: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["question_id", "question_no", "sub_no", "raw_label", "correct_answer"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in answers:
            if not isinstance(row, dict):
                continue
            out = {k: row.get(k, "") for k in fields}
            qid = str(out.get("question_id") or "").strip()
            ans = str(out.get("correct_answer") or "").strip()
            if not qid or not ans:
                continue
            out["correct_answer"] = normalize_objective_answer(ans)
            writer.writerow(out)


def load_exam_answer_key_from_csv(path: Path) -> Dict[str, str]:
    answers: Dict[str, str] = {}
    if not path.exists():
        return answers
    try:
        with path.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                qid = str(row.get("question_id") or row.get("question_no") or "").strip()
                if not qid:
                    continue
                correct = normalize_objective_answer(str(row.get("correct_answer") or ""))
                if correct:
                    answers[qid] = correct
    except Exception:
        _log.exception("failed to load answer key from %s", path)
    return answers


def load_exam_max_scores_from_questions_csv(path: Path) -> Dict[str, float]:
    scores: Dict[str, float] = {}
    if not path.exists():
        return scores
    try:
        with path.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                qid = str(row.get("question_id") or "").strip()
                if not qid:
                    continue
                raw = row.get("max_score")
                if raw is None or raw == "":
                    continue
                try:
                    scores[qid] = float(raw)
                except (ValueError, TypeError):
                    continue
    except Exception:
        _log.exception("failed to load max scores from %s", path)
    return scores


def ensure_questions_max_score(
    questions_csv: Path,
    qids: Iterable[str],
    default_score: float = 1.0,
) -> List[str]:
    target = {str(q or "").strip() for q in qids if str(q or "").strip()}
    if not target or not questions_csv.exists():
        return []

    rows: List[Dict[str, Any]] = []
    defaulted: List[str] = []
    fields = ["question_id", "question_no", "sub_no", "order", "max_score", "stem_ref"]
    try:
        with questions_csv.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                out = {k: row.get(k, "") for k in fields}
                qid = str(out.get("question_id") or "").strip()
                if qid and qid in target:
                    raw = out.get("max_score")
                    if raw is None or str(raw).strip() == "":
                        out["max_score"] = str(default_score)
                        defaulted.append(qid)
                rows.append(out)
    except Exception:
        _log.exception("failed to read questions CSV: %s", questions_csv)
        return []

    if not defaulted:
        return []
    try:
        with questions_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
    except Exception:
        _log.exception("failed to write questions CSV: %s", questions_csv)
        return []
    return defaulted


def score_objective_answer(raw_answer: str, correct: str, max_score: float) -> Tuple[float, int]:
    if not raw_answer:
        return 0.0, 0
    if not math.isfinite(max_score) or max_score <= 0:
        return 0.0, 0
    raw = normalize_objective_answer(raw_answer)
    if not raw:
        return 0.0, 0

    if len(correct) == 1:
        return (max_score if raw == correct else 0.0), (1 if raw == correct else 0)

    correct_set = set(correct)
    raw_set = set(raw)
    if raw_set == correct_set:
        return max_score, 1
    if raw_set.issubset(correct_set):
        return max_score * 0.5, 0
    return 0.0, 0


def apply_answer_key_to_responses_csv(
    responses_path: Path,
    answers_csv: Path,
    questions_csv: Path,
    out_path: Path,
) -> Dict[str, Any]:
    answers = load_exam_answer_key_from_csv(answers_csv)
    max_scores = load_exam_max_scores_from_questions_csv(questions_csv)

    stats = {
        "updated_rows": 0,
        "total_rows": 0,
        "scored_rows": 0,
        "missing_answer_qids": [],
        "missing_max_score_qids": [],
    }
    missing_answer_qids: set[str] = set()
    missing_max_score_qids: set[str] = set()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with responses_path.open(encoding="utf-8") as f_in, out_path.open("w", newline="", encoding="utf-8") as f_out:
        reader = csv.DictReader(f_in)
        fieldnames = list(reader.fieldnames or [])
        if "is_correct" not in fieldnames:
            fieldnames.append("is_correct")

        writer = csv.DictWriter(f_out, fieldnames=fieldnames)
        writer.writeheader()

        for row in reader:
            stats["total_rows"] += 1
            qid = str(row.get("question_id") or "").strip()
            raw_answer = str(row.get("raw_answer") or "").strip()
            score_val = row.get("score", "")

            scored = parse_score_value(score_val)
            if scored is not None:
                stats["scored_rows"] += 1
                if row.get("is_correct") is None:
                    row["is_correct"] = ""
                writer.writerow(row)
                continue

            if raw_answer:
                if qid not in answers:
                    missing_answer_qids.add(qid)
                elif qid not in max_scores:
                    missing_max_score_qids.add(qid)
                else:
                    score, is_correct = score_objective_answer(raw_answer, answers[qid], max_scores[qid])
                    row["score"] = str(int(score)) if float(score).is_integer() else str(score)
                    row["is_correct"] = str(is_correct)
                    stats["updated_rows"] += 1
                    stats["scored_rows"] += 1 if score is not None else 0
            else:
                if row.get("is_correct") is None:
                    row["is_correct"] = ""
            writer.writerow(row)

    stats["missing_answer_qids"] = sorted([q for q in missing_answer_qids if q])
    stats["missing_max_score_qids"] = sorted([q for q in missing_max_score_qids if q])
    return stats
