from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable, Dict, List, Optional, Tuple, cast

_log = logging.getLogger(__name__)



@dataclass(frozen=True)
class ExamOverviewDeps:
    data_dir: Path
    load_exam_manifest: Callable[[str], Optional[Dict[str, Any]]]
    exam_responses_path: Callable[[Dict[str, Any]], Optional[Path]]
    exam_questions_path: Callable[[Dict[str, Any]], Optional[Path]]
    exam_analysis_draft_path: Callable[[Dict[str, Any]], Optional[Path]]
    read_questions_csv: Callable[[Path], Dict[str, Dict[str, Any]]]
    compute_exam_totals: Callable[[Path], Dict[str, Any]]
    now_iso: Callable[[], str]
    parse_xlsx_with_script: Optional[
        Callable[[Path, Path, str, str, Optional[str]], Tuple[Optional[List[Dict[str, Any]]], Dict[str, Any]]]
    ] = None


def _resolve_exam_dir(data_dir: Path, exam_id: str) -> Optional[Path]:
    root = (data_dir / "exams").resolve()
    eid = str(exam_id or "").strip()
    if not eid:
        return None
    target = (root / eid).resolve()
    if target != root and root not in target.parents:
        return None
    return target


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        _log.debug("numeric conversion failed", exc_info=True)
        return None


def _score_mode(meta: Dict[str, Any], questions: Dict[str, Dict[str, Any]]) -> str:
    mode = str(meta.get("score_mode") or "").strip().lower()
    if mode:
        return mode
    return "question" if questions else "unknown"


def _compute_totals_from_rows(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    totals: Dict[str, float] = {}
    students: Dict[str, Dict[str, str]] = {}
    for row in rows:
        score = _safe_float(row.get("score"))
        if score is None:
            continue
        student_id = str(row.get("student_id") or row.get("student_name") or "").strip()
        if not student_id:
            continue
        totals[student_id] = totals.get(student_id, 0.0) + float(score)
        if student_id not in students:
            students[student_id] = {
                "student_id": student_id,
                "student_name": str(row.get("student_name") or "").strip(),
                "class_name": str(row.get("class_name") or "").strip(),
            }
    return {"totals": totals, "students": students}


def _normalize_fallback_questions(payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    raw = payload.get("questions")
    if not isinstance(raw, dict):
        return {}

    questions: Dict[str, Dict[str, Any]] = {}
    for question_id, item in raw.items():
        if isinstance(item, dict):
            questions[str(question_id)] = dict(item)
    return questions


def _normalize_fallback_rows(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw = payload.get("rows")
    if not isinstance(raw, list):
        return []
    return [dict(item) for item in raw if isinstance(item, dict)]


def _collect_subject_fallback(
    exam_id: str,
    manifest: Dict[str, Any],
    deps: ExamOverviewDeps,
) -> Optional[Dict[str, Any]]:
    parser = deps.parse_xlsx_with_script
    if parser is None:
        return None

    exam_dir = _resolve_exam_dir(deps.data_dir, exam_id)
    if exam_dir is None:
        return None

    scores_dir = exam_dir / "scores"
    if not scores_dir.exists() or not scores_dir.is_dir():
        return None

    score_files = sorted([item for item in scores_dir.iterdir() if item.is_file() and item.suffix.lower() == ".xlsx"])
    if not score_files:
        return None

    meta = manifest.get("meta") if isinstance(manifest.get("meta"), dict) else {}
    class_name_hint = str((meta or {}).get("class_name") or "").strip()

    dedup: Dict[Tuple[str, str], Dict[str, Any]] = {}
    q_meta: Dict[str, Dict[str, Any]] = {}
    source_files: List[str] = []
    with TemporaryDirectory(prefix="exam_subject_fallback_") as tmp_dir_raw:
        tmp_dir = Path(tmp_dir_raw)
        for idx, score_path in enumerate(score_files):
            out_csv = tmp_dir / f"scores_{idx}.csv"
            try:
                parsed_rows, _report = parser(score_path, out_csv, exam_id, class_name_hint, None)
            except Exception:
                _log.debug("operation failed", exc_info=True)
                continue
            if not parsed_rows:
                continue
            source_files.append(score_path.name)
            for row in parsed_rows:
                qid = str(row.get("question_id") or "").strip()
                if not qid.startswith("SUBJECT_"):
                    continue
                score = _safe_float(row.get("score"))
                if score is None:
                    continue

                student_id = str(row.get("student_id") or row.get("student_name") or "").strip()
                if not student_id:
                    continue

                key = (student_id, qid)
                prev = dedup.get(key)
                prev_score = _safe_float(prev.get("score")) if isinstance(prev, dict) else None
                normalized = dict(row)
                normalized["score"] = float(score)
                if prev is None or prev_score is None or float(score) > float(prev_score):
                    dedup[key] = normalized

                question_no = str(row.get("question_no") or "").strip()
                sub_no = str(row.get("sub_no") or "").strip()
                q_bucket = q_meta.setdefault(
                    qid,
                    {
                        "question_id": qid,
                        "question_no": question_no,
                        "sub_no": sub_no,
                        "max_score": float(score),
                    },
                )
                if not q_bucket.get("question_no") and question_no:
                    q_bucket["question_no"] = question_no
                if not q_bucket.get("sub_no") and sub_no:
                    q_bucket["sub_no"] = sub_no
                if float(score) > float(q_bucket.get("max_score") or 0.0):
                    q_bucket["max_score"] = float(score)

    if not dedup:
        return None

    rows = list(dedup.values())
    rows.sort(
        key=lambda item: (
            str(item.get("class_name") or ""),
            str(item.get("student_name") or ""),
            str(item.get("student_id") or ""),
            str(item.get("question_id") or ""),
        )
    )
    questions: Dict[str, Dict[str, Any]] = {}
    for qid, item in q_meta.items():
        questions[qid] = {
            "question_id": qid,
            "question_no": str(item.get("question_no") or "").strip(),
            "sub_no": str(item.get("sub_no") or "").strip(),
            "order": "",
            "max_score": _safe_float(item.get("max_score")),
        }
    return {
        "rows": rows,
        "questions": questions,
        "source_files": source_files,
    }


def _resolve_effective_scores(
    exam_id: str,
    manifest: Dict[str, Any],
    *,
    deps: ExamOverviewDeps,
) -> Tuple[Dict[str, Any], Dict[str, Dict[str, Any]], Dict[str, Any], str, str]:
    responses_path = deps.exam_responses_path(manifest)
    questions_path = deps.exam_questions_path(manifest)
    questions = deps.read_questions_csv(questions_path) if questions_path else {}
    totals_result = deps.compute_exam_totals(responses_path) if responses_path and responses_path.exists() else {"totals": {}, "students": {}}

    meta_raw = manifest.get("meta") if isinstance(manifest.get("meta"), dict) else {}
    meta = dict(meta_raw or {})
    mode_from_manifest = _score_mode(meta, questions)

    score_mode = mode_from_manifest
    score_mode_source = "manifest"
    if mode_from_manifest == "total":
        fallback = _collect_subject_fallback(exam_id, manifest, deps)
        if fallback:
            score_mode = "subject"
            score_mode_source = "subject_from_scores_file"
            questions = _normalize_fallback_questions(fallback)
            rows = _normalize_fallback_rows(fallback)
            totals_result = _compute_totals_from_rows(rows)
            meta["score_mode"] = "subject"
            meta["score_mode_source"] = score_mode_source
            meta["score_mode_original"] = "total"
            meta["score_mode_fallback_files"] = fallback.get("source_files") or []

    return totals_result, questions, meta, score_mode, score_mode_source


def exam_get(exam_id: str, deps: ExamOverviewDeps) -> Dict[str, Any]:
    manifest = deps.load_exam_manifest(exam_id)
    if not manifest:
        return {"error": "exam_not_found", "exam_id": exam_id}

    responses_path = deps.exam_responses_path(manifest)
    questions_path = deps.exam_questions_path(manifest)
    analysis_path = deps.exam_analysis_draft_path(manifest)
    totals_result, questions, meta, score_mode, score_mode_source = _resolve_effective_scores(
        exam_id,
        manifest,
        deps=deps,
    )
    totals = totals_result["totals"]
    total_values = sorted(totals.values())
    avg_total = sum(total_values) / len(total_values) if total_values else 0.0
    median_total = total_values[len(total_values) // 2] if total_values else 0.0

    manifest_path = None
    exam_dir = _resolve_exam_dir(deps.data_dir, exam_id)
    if exam_dir is not None:
        manifest_path = exam_dir / "manifest.json"

    return {
        "ok": True,
        "exam_id": manifest.get("exam_id") or exam_id,
        "generated_at": manifest.get("generated_at"),
        "meta": meta or {},
        "counts": {
            "students": len(totals),
            "questions": len(questions),
        },
        "totals_summary": {
            "avg_total": round(avg_total, 3),
            "median_total": round(median_total, 3),
            "max_total_observed": max(total_values) if total_values else 0.0,
            "min_total_observed": min(total_values) if total_values else 0.0,
        },
        "score_mode": score_mode,
        "score_mode_source": score_mode_source,
        "files": {
            "manifest": str(manifest_path.resolve()) if manifest_path else None,
            "responses": str(responses_path) if responses_path else None,
            "questions": str(questions_path) if questions_path else None,
            "analysis_draft": str(analysis_path) if analysis_path else None,
        },
    }


def exam_analysis_get(exam_id: str, deps: ExamOverviewDeps) -> Dict[str, Any]:
    manifest = deps.load_exam_manifest(exam_id)
    if not manifest:
        return {"error": "exam_not_found", "exam_id": exam_id}

    totals_result, questions, _meta, score_mode, score_mode_source = _resolve_effective_scores(
        exam_id,
        manifest,
        deps=deps,
    )
    if score_mode == "subject" and score_mode_source == "subject_from_scores_file":
        totals = sorted(totals_result["totals"].values())
        avg_total = sum(totals) / len(totals) if totals else 0.0
        median_total = totals[len(totals) // 2] if totals else 0.0
        question_metrics: List[Dict[str, Any]] = []
        for qid, question in sorted(questions.items(), key=lambda item: str(item[0])):
            max_score = _safe_float(question.get("max_score"))
            q_scores: List[float] = []
            for student_id, total_score in (totals_result.get("totals") or {}).items():
                if qid.startswith("SUBJECT_"):
                    q_scores.append(float(total_score))
            avg_score = (sum(q_scores) / len(q_scores)) if q_scores else 0.0
            loss_rate = None
            if max_score and max_score > 0:
                loss_rate = max(0.0, min(1.0, (max_score - avg_score) / max_score))
            question_metrics.append(
                {
                    "question_id": qid,
                    "question_no": str(question.get("question_no") or "").strip(),
                    "max_score": max_score if max_score is not None else 0.0,
                    "avg_score": round(avg_score, 3),
                    "loss_rate": None if loss_rate is None else round(loss_rate, 4),
                    "correct_rate": None,
                }
            )

        return {
            "ok": True,
            "exam_id": exam_id,
            "analysis": {
                "exam_id": exam_id,
                "generated_at": deps.now_iso(),
                "totals": {
                    "student_count": len(totals),
                    "avg_total": round(avg_total, 3),
                    "median_total": round(median_total, 3),
                    "max_total_observed": max(totals) if totals else 0.0,
                    "min_total_observed": min(totals) if totals else 0.0,
                },
                "question_metrics": question_metrics,
                "notes": "Used subject-score fallback extracted from score sheets.",
            },
            "source": "computed_subject_from_scores",
        }

    analysis_path = deps.exam_analysis_draft_path(manifest)
    if analysis_path and analysis_path.exists():
        try:
            payload = json.loads(analysis_path.read_text(encoding="utf-8"))
            return {"ok": True, "exam_id": exam_id, "analysis": payload, "source": str(analysis_path)}
        except Exception:
            _log.debug("JSON parse failed", exc_info=True)
            return {"error": "analysis_parse_failed", "exam_id": exam_id, "source": str(analysis_path)}

    responses_path = deps.exam_responses_path(manifest)
    if not responses_path or not responses_path.exists():
        return {"error": "responses_missing", "exam_id": exam_id}

    totals_result = deps.compute_exam_totals(responses_path)
    totals = sorted(totals_result["totals"].values())
    avg_total = sum(totals) / len(totals) if totals else 0.0
    median_total = totals[len(totals) // 2] if totals else 0.0

    return {
        "ok": True,
        "exam_id": exam_id,
        "analysis": {
            "exam_id": exam_id,
            "generated_at": deps.now_iso(),
            "totals": {
                "student_count": len(totals),
                "avg_total": round(avg_total, 3),
                "median_total": round(median_total, 3),
                "max_total_observed": max(totals) if totals else 0.0,
                "min_total_observed": min(totals) if totals else 0.0,
            },
            "notes": "No precomputed analysis draft found; returned minimal totals summary.",
        },
        "source": "computed",
    }


def exam_students_list(exam_id: str, limit: int, deps: ExamOverviewDeps) -> Dict[str, Any]:
    manifest = deps.load_exam_manifest(exam_id)
    if not manifest:
        return {"error": "exam_not_found", "exam_id": exam_id}

    totals_result, _questions, _meta, score_mode, score_mode_source = _resolve_effective_scores(
        exam_id,
        manifest,
        deps=deps,
    )
    if score_mode == "subject" and score_mode_source == "subject_from_scores_file":
        totals = cast(Dict[str, float], totals_result["totals"])
        students_meta = cast(Dict[str, Dict[str, str]], totals_result["students"])
        items: List[Dict[str, Any]] = []
        for student_id, total_score in totals.items():
            meta = students_meta.get(student_id) or {}
            items.append(
                {
                    "student_id": student_id,
                    "student_name": meta.get("student_name", ""),
                    "class_name": meta.get("class_name", ""),
                    "total_score": round(total_score, 3),
                }
            )

        items.sort(key=lambda x: float(x.get("total_score") or 0.0), reverse=True)
        total_students = len(items)
        for idx, item in enumerate(items, start=1):
            item["rank"] = idx
            item["percentile"] = round(1.0 - (idx - 1) / total_students, 4) if total_students else 0.0

        return {
            "ok": True,
            "exam_id": exam_id,
            "total_students": total_students,
            "students": items[: max(1, int(limit or 50))],
        }

    responses_path = deps.exam_responses_path(manifest)
    if not responses_path or not responses_path.exists():
        return {"error": "responses_missing", "exam_id": exam_id}

    totals_result = deps.compute_exam_totals(responses_path)
    totals = cast(Dict[str, float], totals_result["totals"])
    students_meta = cast(Dict[str, Dict[str, str]], totals_result["students"])
    items = []
    for student_id, total_score in totals.items():
        meta = students_meta.get(student_id) or {}
        items.append(
            {
                "student_id": student_id,
                "student_name": meta.get("student_name", ""),
                "class_name": meta.get("class_name", ""),
                "total_score": round(total_score, 3),
            }
        )

    items.sort(key=lambda x: float(x.get("total_score") or 0.0), reverse=True)
    total_students = len(items)
    for idx, item in enumerate(items, start=1):
        item["rank"] = idx
        item["percentile"] = round(1.0 - (idx - 1) / total_students, 4) if total_students else 0.0

    return {
        "ok": True,
        "exam_id": exam_id,
        "total_students": total_students,
        "students": items[: max(1, int(limit or 50))],
    }
