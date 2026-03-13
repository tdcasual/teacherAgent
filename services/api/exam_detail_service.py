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


def _normalized_text(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    return text or None


def _response_student_id(row: Dict[str, Any]) -> str:
    return str(row.get("student_id") or row.get("student_name") or "").strip()


def _resolve_student_matches(
    responses_path: Path,
    *,
    student_id: Optional[str],
    student_name: Optional[str],
    class_name: Optional[str],
) -> List[str]:
    matches: List[str] = []
    with responses_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sid = _response_student_id(row)
            if not sid:
                continue
            if student_id and sid == student_id:
                return [sid]
            if student_name and _student_name_matches(row, student_name=student_name, class_name=class_name):
                matches.append(sid)
    return sorted(set(matches))


def _student_name_matches(row: Dict[str, Any], *, student_name: str, class_name: Optional[str]) -> bool:
    name = str(row.get("student_name") or "").strip()
    cls = str(row.get("class_name") or "").strip()
    if name != student_name:
        return False
    return not class_name or cls == class_name


def _question_sort_key(question: Dict[str, Any]) -> int:
    question_no = str(question.get("question_no") or "").strip()
    return int(question_no) if question_no.isdigit() else 9999


def _collect_student_detail(
    responses_path: Path,
    *,
    target_id: str,
    questions: Dict[str, Dict[str, Any]],
    parse_score_value: Callable[[Any], Optional[float]],
) -> tuple[Dict[str, str], float, List[Dict[str, Any]]]:
    total_score = 0.0
    per_question: Dict[str, Dict[str, Any]] = {}
    student_meta: Dict[str, str] = {"student_id": target_id, "student_name": "", "class_name": ""}

    with responses_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if _response_student_id(row) != target_id:
                continue
            student_meta["student_name"] = str(row.get("student_name") or student_meta["student_name"]).strip()
            student_meta["class_name"] = str(row.get("class_name") or student_meta["class_name"]).strip()
            qid = str(row.get("question_id") or "").strip()
            if not qid:
                continue
            score = parse_score_value(row.get("score"))
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
    question_scores.sort(key=_question_sort_key)
    return student_meta, total_score, question_scores


def _resolve_question_id(
    *,
    question_id: Optional[str],
    question_no: Optional[str],
    questions: Dict[str, Dict[str, Any]],
) -> Optional[str]:
    if question_id:
        return question_id
    if not question_no:
        return None
    for qid, question in questions.items():
        if str(question.get("question_no") or "").strip() == question_no:
            return qid
    return None


def _append_correct_flag(correct_flags: List[int], raw_value: Any) -> None:
    if raw_value in (None, ""):
        return
    value = str(raw_value).strip()
    if not value:
        return
    try:
        correct_flags.append(int(float(value)))
    except Exception:
        _log.debug("numeric conversion failed", exc_info=True)


def _collect_question_detail(
    responses_path: Path,
    *,
    question_id: str,
    parse_score_value: Callable[[Any], Optional[float]],
) -> tuple[List[float], List[int], List[Dict[str, Any]]]:
    scores: List[float] = []
    correct_flags: List[int] = []
    by_student: List[Dict[str, Any]] = []

    with responses_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if str(row.get("question_id") or "").strip() != question_id:
                continue
            score = parse_score_value(row.get("score"))
            if score is not None:
                scores.append(score)
            _append_correct_flag(correct_flags, row.get("is_correct"))
            by_student.append(
                {
                    "student_id": _response_student_id(row),
                    "student_name": str(row.get("student_name") or "").strip(),
                    "class_name": str(row.get("class_name") or "").strip(),
                    "score": score,
                    "raw_value": row.get("raw_value"),
                }
            )
    return scores, correct_flags, by_student


def _score_distribution(scores: List[float]) -> Dict[str, int]:
    distribution: Dict[str, int] = {}
    for score in scores:
        key = str(int(score)) if float(score).is_integer() else str(score)
        distribution[key] = distribution.get(key, 0) + 1
    return distribution


def _student_top_sort_key(student: Dict[str, Any]) -> tuple[bool, float]:
    score = student.get("score")
    return score is None, -(score or 0)


def _student_bottom_sort_key(student: Dict[str, Any]) -> tuple[bool, float]:
    score = student.get("score")
    return score is None, score or 0


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

    student_id = _normalized_text(student_id)
    student_name = _normalized_text(student_name)
    class_name = _normalized_text(class_name)
    matches = _resolve_student_matches(
        responses_path,
        student_id=student_id,
        student_name=student_name,
        class_name=class_name,
    )
    if not matches:
        return {
            "error": "student_not_found",
            "exam_id": exam_id,
            "message": "未在该考试中找到该学生。请提供 student_id，或提供准确的 student_name + class_name。",
        }
    if len(matches) > 1 and not student_id:
        return {"error": "multiple_students", "exam_id": exam_id, "candidates": matches[:10]}
    target_id = student_id or matches[0]

    student_meta, total_score, question_scores = _collect_student_detail(
        responses_path,
        target_id=target_id,
        questions=questions,
        parse_score_value=deps.parse_score_value,
    )
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

    question_id = _normalized_text(question_id)
    question_no = _normalized_text(question_no)
    question_id = _resolve_question_id(question_id=question_id, question_no=question_no, questions=questions)

    if not question_id:
        return {"error": "question_not_specified", "exam_id": exam_id, "message": "请提供 question_id 或 question_no。"}

    scores, correct_flags, by_student = _collect_question_detail(
        responses_path,
        question_id=question_id,
        parse_score_value=deps.parse_score_value,
    )

    avg_score = sum(scores) / len(scores) if scores else 0.0
    max_score = questions.get(question_id, {}).get("max_score")
    loss_rate = (max_score - avg_score) / max_score if max_score else None
    correct_rate = sum(correct_flags) / len(correct_flags) if correct_flags else None

    dist = _score_distribution(scores)
    sample_n = deps.safe_int_arg(top_n, 5, 1, 100)
    by_student_sorted = sorted(by_student, key=_student_top_sort_key)
    top_students = [x for x in by_student_sorted if x.get("student_id")][:sample_n]
    bottom_students = sorted(by_student, key=_student_bottom_sort_key)[:sample_n]

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
