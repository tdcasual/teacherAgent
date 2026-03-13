from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

_log = logging.getLogger(__name__)



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
        _log.debug("operation failed", exc_info=True)
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
        _log.debug("operation failed", exc_info=True)
        return {}
    return out


def _analysis_payload(analysis_res: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    payload = analysis_res.get("analysis")
    return payload if isinstance(payload, dict) else None


def _parse_optional_float(value: Any) -> Optional[float]:
    try:
        return float(value) if value is not None else None
    except Exception:
        _log.debug("numeric conversion failed", exc_info=True)
        return None


def _extract_max_total(analysis_payload: Optional[Dict[str, Any]]) -> Optional[float]:
    if not analysis_payload:
        return None
    totals = analysis_payload.get("totals")
    if not isinstance(totals, dict):
        return None
    return _parse_optional_float(totals.get("max_total"))


def _collect_ids(items: Any, field_name: str) -> set[str]:
    out: set[str] = set()
    if not isinstance(items, list):
        return out
    for item in items:
        if not isinstance(item, dict):
            continue
        value = str(item.get(field_name) or "").strip()
        if value:
            out.add(value)
    return out


def _collect_needed_question_ids(analysis_payload: Optional[Dict[str, Any]]) -> set[str]:
    if not analysis_payload:
        return set()
    out = _collect_ids(analysis_payload.get("question_metrics"), "question_id")
    out.update(_collect_ids(analysis_payload.get("high_loss_questions"), "question_id"))
    return out


def _collect_needed_kp_ids(
    analysis_payload: Optional[Dict[str, Any]],
    *,
    needed_qids: set[str],
    q_kp_map_all: Dict[str, str],
) -> set[str]:
    out = _collect_ids((analysis_payload or {}).get("knowledge_points"), "kp_id")
    for qid in needed_qids:
        mapped_kp_id = q_kp_map_all.get(qid)
        if mapped_kp_id:
            out.add(mapped_kp_id)
    return out


def _trim_kp_context(
    *,
    needed_qids: set[str],
    needed_kp_ids: set[str],
    kp_catalog_all: Dict[str, Dict[str, str]],
    q_kp_map_all: Dict[str, str],
) -> tuple[Dict[str, Dict[str, str]], Dict[str, str]]:
    kp_catalog = {kp_id: kp_catalog_all[kp_id] for kp_id in needed_kp_ids if kp_id in kp_catalog_all}
    q_kp_map = {qid: q_kp_map_all[qid] for qid in needed_qids if qid in q_kp_map_all}
    return kp_catalog, q_kp_map


def _slim_result(result: Dict[str, Any], *, fields: tuple[str, ...], overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if not result.get("ok"):
        return result
    slim = {field: result.get(field) for field in fields}
    if overrides:
        slim.update(overrides)
    return slim


def build_exam_longform_context(exam_id: str, deps: ExamLongformDeps) -> Dict[str, Any]:
    overview = deps.exam_get(exam_id)
    analysis_res = deps.exam_analysis_get(exam_id)
    analysis_payload = _analysis_payload(analysis_res)
    max_total = _extract_max_total(analysis_payload)

    students_summary = summarize_exam_students(exam_id, max_total=max_total, deps=deps)
    kp_catalog_all = load_kp_catalog(deps)
    q_kp_map_all = load_question_kp_map(deps)

    needed_qids = _collect_needed_question_ids(analysis_payload)
    needed_kp_ids = _collect_needed_kp_ids(
        analysis_payload,
        needed_qids=needed_qids,
        q_kp_map_all=q_kp_map_all,
    )
    kp_catalog, q_kp_map = _trim_kp_context(
        needed_qids=needed_qids,
        needed_kp_ids=needed_kp_ids,
        kp_catalog_all=kp_catalog_all,
        q_kp_map_all=q_kp_map_all,
    )

    overview_slim = _slim_result(
        overview,
        fields=("ok", "exam_id", "generated_at", "meta", "counts", "totals_summary", "score_mode", "files"),
    )
    analysis_slim = _slim_result(
        analysis_res,
        fields=("ok", "exam_id", "source"),
        overrides={"analysis": analysis_payload},
    )

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
