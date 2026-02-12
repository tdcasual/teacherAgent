from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Set


@dataclass(frozen=True)
class ExamRangeDeps:
    load_exam_manifest: Callable[[str], Dict[str, Any]]
    exam_responses_path: Callable[[Dict[str, Any]], Any]
    exam_questions_path: Callable[[Dict[str, Any]], Any]
    read_questions_csv: Callable[[Any], Dict[str, Dict[str, Any]]]
    parse_score_value: Callable[[Any], Optional[float]]
    safe_int_arg: Callable[[Any, int, int, int], int]
    exam_question_detail: Callable[..., Dict[str, Any]]


def parse_question_no_int(value: Any) -> Optional[int]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        out = int(text)
        return out if out > 0 else None
    except Exception:
        pass
    match = re.match(r"^(\d+)", text)
    if not match:
        return None
    try:
        out = int(match.group(1))
    except Exception:
        return None
    return out if out > 0 else None


def _median_float(values: List[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    size = len(ordered)
    mid = size // 2
    if size % 2 == 1:
        return float(ordered[mid])
    return float((ordered[mid - 1] + ordered[mid]) / 2.0)


def normalize_question_no_list(value: Any, maximum: int = 200) -> List[int]:
    raw_items: List[Any] = []
    if isinstance(value, list):
        raw_items = list(value)
    elif value is not None:
        raw_items = [x for x in re.split(r"[,\s，;；]+", str(value)) if x]
    normalized: List[int] = []
    seen: Set[int] = set()
    for item in raw_items:
        q_no = parse_question_no_int(item)
        if q_no is None or q_no in seen:
            continue
        seen.add(q_no)
        normalized.append(q_no)
        if len(normalized) >= maximum:
            break
    return normalized


def exam_range_top_students(
    exam_id: str,
    start_question_no: Any,
    end_question_no: Any,
    top_n: int = 10,
    *,
    deps: ExamRangeDeps,
) -> Dict[str, Any]:
    manifest = deps.load_exam_manifest(exam_id)
    if not manifest:
        return {"error": "exam_not_found", "exam_id": exam_id}

    responses_path = deps.exam_responses_path(manifest)
    if not responses_path or not responses_path.exists():
        return {"error": "responses_missing", "exam_id": exam_id}

    start_q = parse_question_no_int(start_question_no)
    end_q = parse_question_no_int(end_question_no)
    if start_q is None or end_q is None:
        return {
            "error": "invalid_question_range",
            "exam_id": exam_id,
            "message": "start_question_no 和 end_question_no 必须是正整数。",
        }
    if start_q > end_q:
        start_q, end_q = end_q, start_q

    sample_n = deps.safe_int_arg(top_n, 10, 1, 100)

    questions_path = deps.exam_questions_path(manifest)
    questions = deps.read_questions_csv(questions_path) if questions_path else {}
    question_no_by_id: Dict[str, int] = {}
    max_score_by_no: Dict[int, float] = {}
    known_question_nos: Set[int] = set()
    for qid, q_meta in questions.items():
        q_no = parse_question_no_int(q_meta.get("question_no"))
        if q_no is None:
            continue
        known_question_nos.add(q_no)
        question_no_by_id[qid] = q_no
        if not (start_q <= q_no <= end_q):
            continue
        q_max = deps.parse_score_value(q_meta.get("max_score"))
        if q_max is None:
            continue
        max_score_by_no[q_no] = max_score_by_no.get(q_no, 0.0) + q_max

    total_scores: Dict[str, float] = {}
    range_scores: Dict[str, float] = {}
    students_meta: Dict[str, Dict[str, str]] = {}
    range_answered_question_nos: Dict[str, Set[int]] = {}
    observed_question_nos: Set[int] = set()

    with responses_path.open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            student_id = str(row.get("student_id") or row.get("student_name") or "").strip()
            if not student_id:
                continue
            if student_id not in students_meta:
                students_meta[student_id] = {
                    "student_id": student_id,
                    "student_name": str(row.get("student_name") or "").strip(),
                    "class_name": str(row.get("class_name") or "").strip(),
                }

            score = deps.parse_score_value(row.get("score"))
            if score is not None:
                total_scores[student_id] = total_scores.get(student_id, 0.0) + score
            else:
                total_scores.setdefault(student_id, 0.0)

            q_no = parse_question_no_int(row.get("question_no"))
            if q_no is None:
                qid = str(row.get("question_id") or "").strip()
                if qid:
                    q_no = question_no_by_id.get(qid)
            if q_no is None or q_no < start_q or q_no > end_q:
                continue

            observed_question_nos.add(q_no)
            range_answered_question_nos.setdefault(student_id, set()).add(q_no)
            if score is not None:
                range_scores[student_id] = range_scores.get(student_id, 0.0) + score

    if not total_scores:
        return {"error": "no_scored_responses", "exam_id": exam_id}

    if questions:
        expected_question_nos = sorted(q for q in known_question_nos if start_q <= q <= end_q)
    else:
        expected_question_nos = sorted(observed_question_nos)
    if not expected_question_nos:
        return {
            "error": "question_range_not_found",
            "exam_id": exam_id,
            "range": {"start_question_no": start_q, "end_question_no": end_q},
            "message": "在该考试中未找到指定题号区间。",
        }

    student_rows: List[Dict[str, Any]] = []
    expected_count = len(expected_question_nos)
    for student_id in sorted(total_scores.keys()):
        meta = students_meta.get(student_id) or {}
        answered = len(range_answered_question_nos.get(student_id) or set())
        student_rows.append(
            {
                "student_id": student_id,
                "student_name": meta.get("student_name", ""),
                "class_name": meta.get("class_name", ""),
                "range_score": round(float(range_scores.get(student_id, 0.0)), 3),
                "total_score": round(float(total_scores.get(student_id, 0.0)), 3),
                "answered_questions": answered,
                "missing_questions": max(0, expected_count - answered),
            }
        )

    sorted_desc = sorted(
        student_rows,
        key=lambda item: (
            -(item.get("range_score") or 0.0),
            -(item.get("total_score") or 0.0),
            str(item.get("student_id") or ""),
        ),
    )
    sorted_asc = sorted(
        student_rows,
        key=lambda item: (
            item.get("range_score") or 0.0,
            item.get("total_score") or 0.0,
            str(item.get("student_id") or ""),
        ),
    )

    top_students: List[Dict[str, Any]] = []
    bottom_students: List[Dict[str, Any]] = []
    for index, item in enumerate(sorted_desc[:sample_n], start=1):
        top_students.append({**item, "rank": index})
    for index, item in enumerate(sorted_asc[:sample_n], start=1):
        bottom_students.append({**item, "rank": index})

    score_values = [float(item.get("range_score") or 0.0) for item in student_rows]
    max_possible_score = 0.0
    for q_no in expected_question_nos:
        max_possible_score += float(max_score_by_no.get(q_no) or 0.0)

    return {
        "ok": True,
        "exam_id": exam_id,
        "range": {
            "start_question_no": start_q,
            "end_question_no": end_q,
            "question_count": len(expected_question_nos),
            "question_nos": expected_question_nos,
            "max_possible_score": round(max_possible_score, 3) if max_possible_score > 0 else None,
        },
        "summary": {
            "student_count": len(student_rows),
            "avg_score": round(sum(score_values) / len(score_values), 3) if score_values else 0.0,
            "median_score": round(_median_float(score_values), 3) if score_values else 0.0,
            "max_score": round(max(score_values), 3) if score_values else 0.0,
            "min_score": round(min(score_values), 3) if score_values else 0.0,
        },
        "top_students": top_students,
        "bottom_students": bottom_students,
    }


def exam_range_summary_batch(exam_id: str, ranges: Any, top_n: int = 5, *, deps: ExamRangeDeps) -> Dict[str, Any]:
    manifest = deps.load_exam_manifest(exam_id)
    if not manifest:
        return {"error": "exam_not_found", "exam_id": exam_id}
    if not isinstance(ranges, list) or not ranges:
        return {"error": "invalid_ranges", "exam_id": exam_id, "message": "ranges 必须是非空数组。"}

    sample_n = deps.safe_int_arg(top_n, 5, 1, 50)
    results: List[Dict[str, Any]] = []
    invalid_ranges: List[Dict[str, Any]] = []
    for idx, item in enumerate(ranges, start=1):
        if not isinstance(item, dict):
            invalid_ranges.append({"index": idx, "error": "range_item_not_object"})
            continue
        start_q = item.get("start_question_no")
        end_q = item.get("end_question_no")
        label = str(item.get("label") or "").strip()
        result = exam_range_top_students(exam_id, start_q, end_q, top_n=sample_n, deps=deps)
        if not result.get("ok"):
            invalid_ranges.append(
                {
                    "index": idx,
                    "label": label or f"range_{idx}",
                    "error": result.get("error") or "range_compute_failed",
                    "message": result.get("message") or "",
                }
            )
            continue
        results.append(
            {
                "index": idx,
                "label": label or f"{result['range']['start_question_no']}-{result['range']['end_question_no']}",
                "range": result.get("range"),
                "summary": result.get("summary"),
                "top_students": result.get("top_students"),
                "bottom_students": result.get("bottom_students"),
            }
        )

    return {
        "ok": bool(results),
        "exam_id": exam_id,
        "range_count_requested": len(ranges),
        "range_count_succeeded": len(results),
        "range_count_failed": len(invalid_ranges),
        "ranges": results,
        "invalid_ranges": invalid_ranges,
    }


def exam_question_batch_detail(exam_id: str, question_nos: Any, top_n: int = 5, *, deps: ExamRangeDeps) -> Dict[str, Any]:
    manifest = deps.load_exam_manifest(exam_id)
    if not manifest:
        return {"error": "exam_not_found", "exam_id": exam_id}

    normalized_nos = normalize_question_no_list(question_nos, maximum=200)
    if not normalized_nos:
        return {"error": "invalid_question_nos", "exam_id": exam_id, "message": "question_nos 必须包含至少一个有效题号。"}

    sample_n = deps.safe_int_arg(top_n, 5, 1, 100)
    items: List[Dict[str, Any]] = []
    missing_question_nos: List[int] = []
    for q_no in normalized_nos:
        detail = deps.exam_question_detail(exam_id, question_no=str(q_no), top_n=sample_n)
        if detail.get("ok"):
            items.append(
                {
                    "question_no": q_no,
                    "question": detail.get("question"),
                    "distribution": detail.get("distribution"),
                    "sample_top_students": detail.get("sample_top_students"),
                    "sample_bottom_students": detail.get("sample_bottom_students"),
                    "response_count": detail.get("response_count"),
                }
            )
            continue
        missing_question_nos.append(q_no)

    return {
        "ok": bool(items),
        "exam_id": exam_id,
        "requested_question_nos": normalized_nos,
        "question_count_succeeded": len(items),
        "question_count_failed": len(missing_question_nos),
        "questions": items,
        "missing_question_nos": missing_question_nos,
    }
