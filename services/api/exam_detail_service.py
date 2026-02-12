from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

_log = logging.getLogger(__name__)



@dataclass(frozen=True)
class ExamDetailDeps:
    load_exam_manifest: Callable[[str], Dict[str, Any]]
    exam_responses_path: Callable[[Dict[str, Any]], Optional[Path]]
    exam_questions_path: Callable[[Dict[str, Any]], Optional[Path]]
    read_questions_csv: Callable[[Path], Dict[str, Dict[str, Any]]]
    parse_score_value: Callable[[Any], Optional[float]]
    safe_int_arg: Callable[[Any, int, int, int], int]


def exam_student_detail(
    exam_id: str,
    *,
    deps: ExamDetailDeps,
    student_id: Optional[str] = None,
    student_name: Optional[str] = None,
    class_name: Optional[str] = None,
) -> Dict[str, Any]:
    manifest = deps.load_exam_manifest(exam_id)
    if not manifest:
        return {"error": "exam_not_found", "exam_id": exam_id}
    responses_path = deps.exam_responses_path(manifest)
    if not responses_path or not responses_path.exists():
        return {"error": "responses_missing", "exam_id": exam_id}
    questions_path = deps.exam_questions_path(manifest)
    questions = deps.read_questions_csv(questions_path) if questions_path else {}

    matches: List[str] = []
    student_id = str(student_id or "").strip() or None
    student_name = str(student_name or "").strip() or None
    class_name = str(class_name or "").strip() or None

    with responses_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sid = str(row.get("student_id") or row.get("student_name") or "").strip()
            if not sid:
                continue
            name = str(row.get("student_name") or "").strip()
            cls = str(row.get("class_name") or "").strip()
            if student_id and sid == student_id:
                matches.append(sid)
                break
            if student_name and name == student_name and (not class_name or cls == class_name):
                matches.append(sid)

    matches = sorted(set(matches))
    if not matches:
        return {
            "error": "student_not_found",
            "exam_id": exam_id,
            "message": "未在该考试中找到该学生。请提供 student_id，或提供准确的 student_name + class_name。",
        }
    if len(matches) > 1 and not student_id:
        return {"error": "multiple_students", "exam_id": exam_id, "candidates": matches[:10]}
    target_id = student_id or matches[0]

    total_score = 0.0
    per_question: Dict[str, Dict[str, Any]] = {}
    student_meta: Dict[str, str] = {"student_id": target_id, "student_name": "", "class_name": ""}
    with responses_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sid = str(row.get("student_id") or row.get("student_name") or "").strip()
            if sid != target_id:
                continue
            student_meta["student_name"] = str(row.get("student_name") or student_meta["student_name"]).strip()
            student_meta["class_name"] = str(row.get("class_name") or student_meta["class_name"]).strip()
            qid = str(row.get("question_id") or "").strip()
            if not qid:
                continue
            score = deps.parse_score_value(row.get("score"))
            if score is not None:
                total_score += score
            per_question[qid] = {
                "question_id": qid,
                "question_no": str(row.get("question_no") or questions.get(qid, {}).get("question_no") or "").strip(),
                "sub_no": str(row.get("sub_no") or "").strip(),
                "score": score,
                "max_score": questions.get(qid, {}).get("max_score"),
                "is_correct": row.get("is_correct"),
                "raw_value": row.get("raw_value"),
                "raw_answer": row.get("raw_answer"),
            }

    question_scores = list(per_question.values())
    question_scores.sort(key=lambda x: int(x.get("question_no") or "0") if str(x.get("question_no") or "").isdigit() else 9999)
    return {
        "ok": True,
        "exam_id": exam_id,
        "student": {**student_meta, "total_score": round(total_score, 3)},
        "question_scores": question_scores,
        "question_count": len(question_scores),
    }


def exam_question_detail(
    exam_id: str,
    *,
    deps: ExamDetailDeps,
    question_id: Optional[str] = None,
    question_no: Optional[str] = None,
    top_n: int = 5,
) -> Dict[str, Any]:
    manifest = deps.load_exam_manifest(exam_id)
    if not manifest:
        return {"error": "exam_not_found", "exam_id": exam_id}
    responses_path = deps.exam_responses_path(manifest)
    if not responses_path or not responses_path.exists():
        return {"error": "responses_missing", "exam_id": exam_id}
    questions_path = deps.exam_questions_path(manifest)
    questions = deps.read_questions_csv(questions_path) if questions_path else {}

    question_id = str(question_id or "").strip() or None
    question_no = str(question_no or "").strip() or None

    if not question_id and question_no:
        for qid, q in questions.items():
            if str(q.get("question_no") or "").strip() == question_no:
                question_id = qid
                break

    if not question_id:
        return {"error": "question_not_specified", "exam_id": exam_id, "message": "请提供 question_id 或 question_no。"}

    scores: List[float] = []
    correct_flags: List[int] = []
    by_student: List[Dict[str, Any]] = []
    with responses_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            qid = str(row.get("question_id") or "").strip()
            if qid != question_id:
                continue
            score = deps.parse_score_value(row.get("score"))
            if score is not None:
                scores.append(score)
            is_correct_raw = row.get("is_correct")
            if is_correct_raw not in (None, ""):
                is_correct_text = str(is_correct_raw).strip()
                if not is_correct_text:
                    continue
                try:
                    correct_flags.append(int(float(is_correct_text)))
                except Exception:
                    _log.debug("numeric conversion failed", exc_info=True)
                    pass
            by_student.append(
                {
                    "student_id": str(row.get("student_id") or row.get("student_name") or "").strip(),
                    "student_name": str(row.get("student_name") or "").strip(),
                    "class_name": str(row.get("class_name") or "").strip(),
                    "score": score,
                    "raw_value": row.get("raw_value"),
                }
            )

    avg_score = sum(scores) / len(scores) if scores else 0.0
    max_score = questions.get(question_id, {}).get("max_score")
    loss_rate = (max_score - avg_score) / max_score if max_score else None
    correct_rate = sum(correct_flags) / len(correct_flags) if correct_flags else None

    dist: Dict[str, int] = {}
    for s in scores:
        key = str(int(s)) if float(s).is_integer() else str(s)
        dist[key] = dist.get(key, 0) + 1

    sample_n = deps.safe_int_arg(top_n, 5, 1, 100)
    by_student_sorted = sorted(by_student, key=lambda x: (x["score"] is None, -(x["score"] or 0)))
    top_students = [x for x in by_student_sorted if x.get("student_id")][:sample_n]
    bottom_students = sorted(by_student, key=lambda x: (x["score"] is None, x["score"] or 0))[:sample_n]

    return {
        "ok": True,
        "exam_id": exam_id,
        "question": {
            "question_id": question_id,
            "question_no": questions.get(question_id, {}).get("question_no") if questions else None,
            "max_score": max_score,
            "avg_score": round(avg_score, 3),
            "loss_rate": round(loss_rate, 4) if loss_rate is not None else None,
            "correct_rate": round(correct_rate, 4) if correct_rate is not None else None,
        },
        "distribution": dist,
        "sample_top_students": top_students,
        "sample_bottom_students": bottom_students,
        "response_count": len(by_student),
    }
