from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


@dataclass(frozen=True)
class ExamLongformDeps:
    data_dir: Path
    exam_students_list: Callable[[str, int], Dict[str, Any]]
    exam_get: Callable[[str], Dict[str, Any]]
    exam_analysis_get: Callable[[str], Dict[str, Any]]
    call_llm: Callable[..., Dict[str, Any]]
    non_ws_len: Callable[[str], int]


def _percentile(sorted_vals: List[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    p = max(0.0, min(1.0, float(p)))
    idx = (len(sorted_vals) - 1) * p
    lo = int(idx)
    hi = min(lo + 1, len(sorted_vals) - 1)
    if lo == hi:
        return float(sorted_vals[lo])
    frac = idx - lo
    return float(sorted_vals[lo]) * (1.0 - frac) + float(sorted_vals[hi]) * frac


def _score_band_label(percent: float) -> str:
    p = max(0.0, min(100.0, float(percent)))
    if p >= 100.0:
        return "90–100%"
    start = int(p // 10) * 10
    end = 100 if start >= 90 else (start + 9)
    return f"{start}–{end}%"


def summarize_exam_students(exam_id: str, max_total: Optional[float], deps: ExamLongformDeps) -> Dict[str, Any]:
    res = deps.exam_students_list(exam_id, 500)
    if not res.get("ok"):
        return {"error": res.get("error") or "students_list_failed", "exam_id": exam_id}
    students = res.get("students") or []
    scores: List[float] = []
    for item in students:
        score = item.get("total_score")
        if isinstance(score, (int, float)):
            scores.append(float(score))
    scores_sorted = sorted(scores)
    stats: Dict[str, Any] = {}
    if scores_sorted:
        stats = {
            "min": round(scores_sorted[0], 3),
            "p10": round(_percentile(scores_sorted, 0.10), 3),
            "p25": round(_percentile(scores_sorted, 0.25), 3),
            "median": round(_percentile(scores_sorted, 0.50), 3),
            "p75": round(_percentile(scores_sorted, 0.75), 3),
            "p90": round(_percentile(scores_sorted, 0.90), 3),
            "max": round(scores_sorted[-1], 3),
        }
    bands = []
    if max_total and isinstance(max_total, (int, float)) and float(max_total) > 0 and scores_sorted:
        buckets = [(0, 9), (10, 19), (20, 29), (30, 39), (40, 49), (50, 59), (60, 69), (70, 79), (80, 89), (90, 100)]
        for lo, hi in buckets:
            label = f"{lo}–{hi}%"
            count = 0
            for score in scores_sorted:
                pct = (float(score) / float(max_total)) * 100.0
                bucket = _score_band_label(pct)
                if bucket == label:
                    count += 1
            bands.append({"band": label, "count": count})
    top_students = students[:5]
    bottom_students = students[-5:] if len(students) >= 5 else students[:]
    return {
        "exam_id": exam_id,
        "total_students": res.get("total_students", len(students)),
        "score_stats": stats,
        "score_bands": bands,
        "top_students": top_students,
        "bottom_students": bottom_students,
    }


def load_kp_catalog(deps: ExamLongformDeps) -> Dict[str, Dict[str, str]]:
    path = deps.data_dir / "knowledge" / "knowledge_points.csv"
    if not path.exists():
        return {}
    out: Dict[str, Dict[str, str]] = {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                kp_id = str(row.get("kp_id") or "").strip()
                if not kp_id:
                    continue
                out[kp_id] = {
                    "name": str(row.get("name") or "").strip(),
                    "status": str(row.get("status") or "").strip(),
                    "notes": str(row.get("notes") or "").strip(),
                }
    except Exception:
        return {}
    return out


def load_question_kp_map(deps: ExamLongformDeps) -> Dict[str, str]:
    path = deps.data_dir / "knowledge" / "knowledge_point_map.csv"
    if not path.exists():
        return {}
    out: Dict[str, str] = {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                qid = str(row.get("question_id") or "").strip()
                kp_id = str(row.get("kp_id") or "").strip()
                if qid and kp_id:
                    out[qid] = kp_id
    except Exception:
        return {}
    return out


def build_exam_longform_context(exam_id: str, deps: ExamLongformDeps) -> Dict[str, Any]:
    overview = deps.exam_get(exam_id)
    analysis_res = deps.exam_analysis_get(exam_id)
    analysis_payload = analysis_res.get("analysis") if isinstance(analysis_res, dict) else None

    max_total = None
    if isinstance(analysis_payload, dict):
        totals = analysis_payload.get("totals")
        if isinstance(totals, dict):
            max_total = totals.get("max_total")
            try:
                max_total = float(max_total) if max_total is not None else None
            except Exception:
                max_total = None

    students_summary = summarize_exam_students(exam_id, max_total=max_total, deps=deps)
    kp_catalog_all = load_kp_catalog(deps)
    q_kp_map_all = load_question_kp_map(deps)

    needed_qids: set[str] = set()
    needed_kp_ids: set[str] = set()
    if isinstance(analysis_payload, dict):
        for item in (analysis_payload.get("question_metrics") or []) + (analysis_payload.get("high_loss_questions") or []):
            if not isinstance(item, dict):
                continue
            qid = str(item.get("question_id") or "").strip()
            if qid:
                needed_qids.add(qid)
        for item in analysis_payload.get("knowledge_points") or []:
            if not isinstance(item, dict):
                continue
            kp_id = str(item.get("kp_id") or "").strip()
            if kp_id:
                needed_kp_ids.add(kp_id)

    for qid in needed_qids:
        kp_id = q_kp_map_all.get(qid)
        if kp_id:
            needed_kp_ids.add(kp_id)

    kp_catalog = {kp_id: kp_catalog_all[kp_id] for kp_id in needed_kp_ids if kp_id in kp_catalog_all}
    q_kp_map = {qid: q_kp_map_all[qid] for qid in needed_qids if qid in q_kp_map_all}

    overview_slim: Dict[str, Any] = overview if not overview.get("ok") else {}
    if overview.get("ok"):
        overview_slim = {
            "ok": True,
            "exam_id": overview.get("exam_id"),
            "generated_at": overview.get("generated_at"),
            "meta": overview.get("meta"),
            "counts": overview.get("counts"),
            "totals_summary": overview.get("totals_summary"),
            "score_mode": overview.get("score_mode"),
        }

    analysis_slim: Dict[str, Any] = analysis_res if not analysis_res.get("ok") else {}
    if analysis_res.get("ok"):
        analysis_slim = {
            "ok": True,
            "exam_id": analysis_res.get("exam_id"),
            "analysis": analysis_payload,
            "source": analysis_res.get("source"),
        }

    return {
        "exam_overview": overview_slim,
        "exam_analysis": analysis_slim,
        "students_summary": students_summary,
        "knowledge_points_catalog": kp_catalog,
        "question_kp_map": q_kp_map,
    }


def calc_longform_max_tokens(min_chars: int) -> int:
    base = int(max(512, min_chars) * 2)
    return max(2048, min(base, 8192))


def generate_longform_reply(
    convo: List[Dict[str, Any]],
    min_chars: int,
    role_hint: Optional[str],
    skill_id: Optional[str],
    teacher_id: Optional[str],
    skill_runtime: Optional[Any],
    deps: ExamLongformDeps,
) -> str:
    max_tokens = calc_longform_max_tokens(min_chars)
    resp = deps.call_llm(
        convo,
        tools=None,
        role_hint=role_hint,
        max_tokens=max_tokens,
        skill_id=skill_id,
        kind="chat.exam_longform",
        teacher_id=teacher_id,
        skill_runtime=skill_runtime,
    )
    content = resp.get("choices", [{}])[0].get("message", {}).get("content") or ""
    if deps.non_ws_len(content) >= min_chars:
        return content

    expand_convo = convo + [
        {"role": "assistant", "content": content},
        {
            "role": "user",
            "content": (
                f"请在不改变事实前提下继续补充扩写，使全文字数不少于 {min_chars} 字。"
                "避免重复已有内容，优先补充：逐题/知识点的具体诊断、典型错误成因、分层教学策略、课内讲评与课后训练安排、可操作的下一步。"
                "不要调用任何工具。"
            ),
        },
    ]
    resp2 = deps.call_llm(
        expand_convo,
        tools=None,
        role_hint=role_hint,
        max_tokens=max_tokens,
        skill_id=skill_id,
        kind="chat.exam_longform",
        teacher_id=teacher_id,
        skill_runtime=skill_runtime,
    )
    content2 = resp2.get("choices", [{}])[0].get("message", {}).get("content") or ""
    if deps.non_ws_len(content2) >= min_chars:
        return content2
    return content2 if deps.non_ws_len(content2) > deps.non_ws_len(content) else content
