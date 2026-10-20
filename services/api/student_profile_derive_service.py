from __future__ import annotations

from typing import Any, Dict, Iterable, List, Sequence, Tuple

_FALLBACK_NOTE = "提交未产生逐题分，已用作业目标知识点更新画像。"


def _as_str_list(value: Any) -> List[str]:
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if not isinstance(value, Iterable) or isinstance(value, (bytes, dict)):
        return []
    out: List[str] = []
    for item in value:
        text = str(item or "").strip()
        if text and text not in out:
            out.append(text)
    return out


def _question_map(assignment_questions: Sequence[dict[str, Any]]) -> Dict[str, dict[str, Any]]:
    mapping: Dict[str, dict[str, Any]] = {}
    for row in assignment_questions:
        if not isinstance(row, dict):
            continue
        qid = str(row.get("question_id") or "").strip()
        if qid:
            mapping[qid] = row
    return mapping


def _item_kp(item: dict[str, Any], questions: Dict[str, dict[str, Any]]) -> str:
    kp = str(item.get("kp_id") or "").strip()
    if kp and kp != "uncategorized":
        return kp
    qid = str(item.get("question_id") or "").strip()
    row = questions.get(qid) or {}
    joined = str(row.get("kp_id") or "").strip()
    if joined and joined != "uncategorized":
        return joined
    return ""


def _item_correct(item: dict[str, Any]) -> bool:
    status = str(item.get("status") or "").strip().lower()
    if status == "matched":
        return True
    if status in {"missed", "ungraded"}:
        return False
    if item.get("matched") is True:
        return True
    try:
        return float(item.get("score") or 0.0) > 0
    except (TypeError, ValueError):
        return False


def _fallback_kps(
    *,
    target_kp: Sequence[str],
    requirements: dict[str, Any],
) -> Tuple[List[str], str]:
    req = requirements if isinstance(requirements, dict) else {}
    chain: List[Tuple[List[str], str]] = [
        (_as_str_list(target_kp), "ungraded_fallback"),
        (_as_str_list(req.get("core_concepts")), "ungraded_fallback"),
        (_as_str_list(req.get("discussion_goals")), "brief_fallback"),
    ]
    for kps, source in chain:
        trimmed = kps[:3]
        if trimmed:
            return trimmed, source
    return [], "brief_fallback"


def _empty_graded() -> Dict[str, Any]:
    return {
        "recent_weak_kp": [],
        "recent_medium_kp": [],
        "recent_strong_kp": [],
        "next_focus": "",
        "source": "graded",
        "mastery_by_kp": {},
        "interaction_note": "",
        "question_ids": [],
    }


def _is_ungraded_report(report: dict[str, Any], counted: int) -> bool:
    if bool(report.get("received_without_items")):
        return True
    items = report.get("items")
    if not isinstance(items, list) or not items:
        return True
    return counted <= 0


def _bucket_for(acc: float, *, total: int, correct: int) -> str:
    if acc < 0.5 or (total >= 1 and correct == 0):
        return "weak"
    if acc >= 0.8:
        return "strong"
    return "medium"


def derive_profile_from_grading_report(
    *,
    report: dict[str, Any],
    assignment_questions: list[dict[str, Any]],
    requirements: dict[str, Any],
    target_kp: list[str],
) -> dict[str, Any]:
    """weak: acc < 0.5 or (total>=1 and correct==0)
    medium: 0.5 <= acc < 0.8
    strong: acc >= 0.8
    next_focus: first weak else first medium else ""
    source: "graded" | "ungraded_fallback" | "brief_fallback"
    """
    payload = report if isinstance(report, dict) else {}
    questions = _question_map(assignment_questions)
    raw_items = payload.get("items")
    items: list[Any] = raw_items if isinstance(raw_items, list) else []
    stats: Dict[str, Dict[str, int]] = {}
    order: List[str] = []
    question_ids: List[str] = []
    counted = 0
    for raw in items:
        if not isinstance(raw, dict):
            continue
        qid = str(raw.get("question_id") or "").strip()
        if qid and qid not in question_ids:
            question_ids.append(qid)
        if str(raw.get("status") or "").strip().lower() == "ungraded":
            continue
        kp = _item_kp(raw, questions)
        if not kp:
            continue
        counted += 1
        bucket = stats.setdefault(kp, {"correct": 0, "total": 0})
        bucket["total"] += 1
        if _item_correct(raw):
            bucket["correct"] += 1
        if kp not in order:
            order.append(kp)

    if _is_ungraded_report(payload, counted):
        kps, source = _fallback_kps(target_kp=target_kp, requirements=requirements)
        derived = _empty_graded()
        derived["recent_weak_kp"] = list(kps)
        derived["next_focus"] = kps[0] if kps else ""
        derived["source"] = source
        derived["interaction_note"] = _FALLBACK_NOTE
        derived["question_ids"] = question_ids
        return derived

    weak: List[str] = []
    medium: List[str] = []
    strong: List[str] = []
    mastery: Dict[str, Any] = {}
    for kp in order:
        stat = stats[kp]
        total = int(stat["total"])
        correct = int(stat["correct"])
        acc = (correct / total) if total else 0.0
        mastery[kp] = {"accuracy": round(acc, 3), "attempts": total}
        level = _bucket_for(acc, total=total, correct=correct)
        if level == "weak":
            weak.append(kp)
        elif level == "strong":
            strong.append(kp)
        else:
            medium.append(kp)

    next_focus = weak[0] if weak else (medium[0] if medium else "")
    return {
        "recent_weak_kp": weak,
        "recent_medium_kp": medium,
        "recent_strong_kp": strong,
        "next_focus": next_focus,
        "source": "graded",
        "mastery_by_kp": mastery,
        "interaction_note": "",
        "question_ids": question_ids,
    }
