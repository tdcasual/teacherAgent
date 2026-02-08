from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional


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


def _resolve_exam_dir(data_dir: Path, exam_id: str) -> Optional[Path]:
    root = (data_dir / "exams").resolve()
    eid = str(exam_id or "").strip()
    if not eid:
        return None
    target = (root / eid).resolve()
    if target != root and root not in target.parents:
        return None
    return target


def exam_get(exam_id: str, deps: ExamOverviewDeps) -> Dict[str, Any]:
    manifest = deps.load_exam_manifest(exam_id)
    if not manifest:
        return {"error": "exam_not_found", "exam_id": exam_id}

    responses_path = deps.exam_responses_path(manifest)
    questions_path = deps.exam_questions_path(manifest)
    analysis_path = deps.exam_analysis_draft_path(manifest)
    questions = deps.read_questions_csv(questions_path) if questions_path else {}
    totals_result = deps.compute_exam_totals(responses_path) if responses_path and responses_path.exists() else {"totals": {}, "students": {}}
    totals = totals_result["totals"]
    total_values = sorted(totals.values())
    avg_total = sum(total_values) / len(total_values) if total_values else 0.0
    median_total = total_values[len(total_values) // 2] if total_values else 0.0
    meta = manifest.get("meta") if isinstance(manifest.get("meta"), dict) else {}
    score_mode = meta.get("score_mode") if isinstance(meta, dict) else None
    if not score_mode:
        score_mode = "question" if questions else "unknown"

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

    analysis_path = deps.exam_analysis_draft_path(manifest)
    if analysis_path and analysis_path.exists():
        try:
            payload = json.loads(analysis_path.read_text(encoding="utf-8"))
            return {"ok": True, "exam_id": exam_id, "analysis": payload, "source": str(analysis_path)}
        except Exception:
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

    responses_path = deps.exam_responses_path(manifest)
    if not responses_path or not responses_path.exists():
        return {"error": "responses_missing", "exam_id": exam_id}

    totals_result = deps.compute_exam_totals(responses_path)
    totals: Dict[str, float] = totals_result["totals"]
    students_meta: Dict[str, Dict[str, str]] = totals_result["students"]
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

    items.sort(key=lambda x: x["total_score"], reverse=True)
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
