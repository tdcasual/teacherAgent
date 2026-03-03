from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .skills.auto_route_rules import score_role_skill
from .skills.loader import load_skills
from .skills.router import default_skill_id_for_role

_log = logging.getLogger(__name__)



_SKILL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{1,80}$")
_CE_ID_RE = re.compile(r"\bCE\d+\b", flags=re.I)
_SINGLE_STUDENT_RE = re.compile(r"(某个学生|单个学生|该学生|同学.*(画像|诊断|表现))")
_TIE_BREAK_ORDER = [
    "physics-homework-generator",
    "physics-lesson-capture",
    "physics-core-examples",
    "physics-student-focus",
    "physics-student-coach",
    "physics-teacher-ops",
]
_TIE_BREAK_INDEX = {skill_id: idx for idx, skill_id in enumerate(_TIE_BREAK_ORDER)}


@dataclass(frozen=True)
class _ScoreRow:
    skill_id: str
    score: int
    hits: List[str]
    min_score: int
    min_margin: int
    confidence_floor: float


def _role_allowed(spec: Any, role_hint: Optional[str]) -> bool:
    role = str(role_hint or "").strip()
    roles = list(getattr(spec, "allowed_roles", []) or [])
    if not role:
        return True
    if not roles:
        return True
    return role in set(roles)


def _default_from_available(role_hint: Optional[str], available_ids: List[str]) -> str:
    if not available_ids:
        return ""
    fallback = default_skill_id_for_role(role_hint)
    if fallback in set(available_ids):
        return fallback
    return sorted(available_ids)[0]


def _keyword_hit(text: str, key: str, mode: str) -> bool:
    if not key:
        return False
    if mode == "word_boundary":
        pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(key)}(?![A-Za-z0-9_])", flags=re.I)
        return bool(pattern.search(text))
    return key in text


def _normalized_tokens(values: Any) -> List[str]:
    return [str(item or "").strip().lower() for item in (values or []) if str(item or "").strip()]


def _build_keyword_weights(raw_weights: Any) -> Dict[str, int]:
    output: Dict[str, int] = {}
    for key, value in dict(raw_weights or {}).items():
        normalized = str(key or "").strip().lower()
        if not normalized:
            continue
        output[normalized] = max(1, int(value))
    return output


def _score_keyword_matches(
    text: str,
    keys: List[str],
    *,
    match_mode: str,
    keyword_weights: Dict[str, int],
    delta: int,
    hit_prefix: str,
) -> Tuple[int, List[str]]:
    score = 0
    hits: List[str] = []
    for key in keys:
        if not _keyword_hit(text, key, match_mode):
            continue
        if delta > 0:
            score += min(50, max(1, int(keyword_weights.get(key, delta))))
        else:
            score += delta
        hits.append(f"{hit_prefix}:{key}")
    return score, hits


def _score_intent_matches(intents: List[str], text: str, *, assignment_intent: bool, assignment_generation: bool) -> Tuple[int, List[str]]:
    score = 0
    hits: List[str] = []
    if "assignment_generate" in intents and assignment_generation:
        score += 8
        hits.append("cfg-intent:assignment_generate")
    elif "assignment" in intents and assignment_intent:
        score += 4
        hits.append("cfg-intent:assignment")

    intent_rules = (
        ("student_focus", ("学生", "画像", "诊断"), 4),
        ("core_examples", ("例题", "变式题"), 4),
        ("teacher_ops", ("考试", "讲评", "备课"), 3),
        ("student_coach", ("开始作业", "开始练习", "讲解错题"), 4),
    )
    for intent_name, markers, delta in intent_rules:
        if intent_name not in intents:
            continue
        if any(marker in text for marker in markers):
            score += delta
            hits.append(f"cfg-intent:{intent_name}")
    if "core_examples" in intents and bool(_CE_ID_RE.search(text)) and "cfg-intent:core_examples" not in hits:
        score += 4
        hits.append("cfg-intent:core_examples")
    if "lesson_capture" in intents:
        lesson_hit = any(marker in text for marker in ("课堂", "lesson"))
        capture_hit = any(marker in text for marker in ("采集", "ocr", "识别"))
        if lesson_hit and capture_hit:
            score += 4
            hits.append("cfg-intent:lesson_capture")
    return score, hits


def _score_from_skill_config(
    skill_spec: Any,
    text: str,
    *,
    assignment_intent: bool,
    assignment_generation: bool,
) -> Tuple[int, List[str], int, int, float]:
    routing = getattr(skill_spec, "routing", None)
    if routing is None:
        return 0, [], 3, 1, 0.28

    keywords = _normalized_tokens(getattr(routing, "keywords", []))
    negative_keywords = _normalized_tokens(getattr(routing, "negative_keywords", []))
    intents = _normalized_tokens(getattr(routing, "intents", []))
    match_mode = str(getattr(routing, "match_mode", "substring") or "substring").strip().lower()
    min_score = max(1, int(getattr(routing, "min_score", 3) or 3))
    min_margin = max(0, int(getattr(routing, "min_margin", 1) or 1))
    confidence_floor = float(getattr(routing, "confidence_floor", 0.28) or 0.28)
    confidence_floor = max(0.0, min(0.95, confidence_floor))
    keyword_weights = _build_keyword_weights(getattr(routing, "keyword_weights", {}))

    pos_score, pos_hits = _score_keyword_matches(
        text,
        keywords,
        match_mode=match_mode,
        keyword_weights=keyword_weights,
        delta=3,
        hit_prefix="cfg",
    )
    neg_score, neg_hits = _score_keyword_matches(
        text,
        negative_keywords,
        match_mode=match_mode,
        keyword_weights=keyword_weights,
        delta=-3,
        hit_prefix="cfg-neg",
    )
    intent_score, intent_hits = _score_intent_matches(
        intents,
        text,
        assignment_intent=assignment_intent,
        assignment_generation=assignment_generation,
    )
    score = pos_score + neg_score + intent_score
    hits = pos_hits + neg_hits + intent_hits

    return score, hits, min_score, min_margin, confidence_floor


def _confidence_for_auto(best: int, second: int, floor: float) -> float:
    gap = max(0, best - second)
    base = floor + min(0.35, best * 0.04)
    boost = 0.08 if gap >= 4 else (0.04 if gap >= 2 else 0.0)
    return max(0.0, min(0.95, base + boost))


def _is_explicit_assignment_generation(text: str) -> bool:
    if not text:
        return False
    if re.search(r"(创建|新建|新增|安排|布置|生成|发)\S{0,6}作业", text):
        return True
    for key in ("作业id", "作业 id", "每个知识点", "渲染作业"):
        if key in text:
            return True
    return False


def _requested_state(requested: str, skills: Dict[str, Any], available_ids: List[str]) -> Tuple[bool, bool, bool]:
    requested_valid = bool(requested and _SKILL_ID_RE.match(requested))
    requested_exists = requested in skills
    requested_allowed = requested in set(available_ids)
    return requested_valid, requested_exists, requested_allowed


def _requested_reason_prefix(
    requested: str,
    *,
    requested_valid: bool,
    requested_exists: bool,
    requested_allowed: bool,
) -> str:
    if requested and not requested_valid:
        return "requested_invalid_"
    if requested and requested_valid and not requested_exists:
        return "requested_unknown_"
    if requested and requested_valid and requested_exists and not requested_allowed:
        return "requested_not_allowed_"
    return ""


def _resolve_assignment_intent(
    role: str,
    *,
    last_user_text: str,
    detect_assignment_intent: Optional[Callable[[str], bool]],
) -> bool:
    if role != "teacher" or not callable(detect_assignment_intent):
        return False
    try:
        return bool(detect_assignment_intent(last_user_text or ""))
    except Exception:
        _log.debug("operation failed", exc_info=True)
        return False


def _build_score_rows(
    *,
    available_ids: List[str],
    skills: Dict[str, Any],
    role: str,
    text: str,
    assignment_intent: bool,
    assignment_generation: bool,
) -> List[_ScoreRow]:
    rows: List[_ScoreRow] = []
    for skill_id in available_ids:
        spec = skills.get(skill_id)
        cfg_score, cfg_hits, min_score, min_margin, confidence_floor = _score_from_skill_config(
            spec,
            text,
            assignment_intent=assignment_intent,
            assignment_generation=assignment_generation,
        )
        rule_score, rule_hits = score_role_skill(
            role,
            skill_id,
            text,
            assignment_intent=assignment_intent,
            assignment_generation=assignment_generation,
        )
        total_score = int(cfg_score) + int(rule_score)
        if total_score <= 0:
            continue
        rows.append(
            _ScoreRow(
                skill_id=skill_id,
                score=total_score,
                hits=list(cfg_hits) + list(rule_hits),
                min_score=min_score,
                min_margin=min_margin,
                confidence_floor=confidence_floor,
            )
        )
    rows.sort(key=lambda row: (-row.score, _TIE_BREAK_INDEX.get(row.skill_id, 999), row.skill_id))
    return rows


def _build_candidates(score_rows: List[_ScoreRow]) -> List[Dict[str, Any]]:
    return [{"skill_id": row.skill_id, "score": row.score, "hits": row.hits[:6]} for row in score_rows[:3]]


def _resolve_default_reason(
    requested: str,
    *,
    requested_valid: bool,
    requested_exists: bool,
    requested_allowed: bool,
) -> str:
    if requested and requested_valid and requested_exists and not requested_allowed:
        return "requested_not_allowed_default"
    if requested and requested_valid and not requested_exists:
        return "requested_unknown_default"
    if requested and not requested_valid:
        return "requested_invalid_default"
    return "role_default"


def _build_best_match_result(
    *,
    best: _ScoreRow,
    second_score: int,
    requested: str,
    requested_valid: bool,
    requested_exists: bool,
    requested_allowed: bool,
    default_skill_id: str,
    candidates: List[Dict[str, Any]],
    load_errors: int,
) -> Dict[str, Any]:
    threshold_blocked = best.score < int(best.min_score)
    margin = max(0, int(best.min_margin))
    ambiguous = (best.score - second_score) < margin
    reason_prefix = _requested_reason_prefix(
        requested,
        requested_valid=requested_valid,
        requested_exists=requested_exists,
        requested_allowed=requested_allowed,
    )
    if not threshold_blocked and not ambiguous:
        return {
            "requested_skill_id": requested,
            "effective_skill_id": best.skill_id,
            "reason": f"{reason_prefix}auto_rule",
            "confidence": _confidence_for_auto(best.score, second_score, best.confidence_floor),
            "matched_rule": ",".join(best.hits[:3]) or "auto_rule",
            "candidates": candidates,
            "best_score": int(best.score),
            "second_score": int(second_score),
            "threshold_blocked": False,
            "load_errors": load_errors,
        }

    blocked_reason = "ambiguous_auto_rule_default" if ambiguous else "auto_threshold_blocked_default"
    reason = f"{reason_prefix}{blocked_reason}" if reason_prefix else blocked_reason
    return {
        "requested_skill_id": requested,
        "effective_skill_id": default_skill_id,
        "reason": reason,
        "confidence": float(best.confidence_floor),
        "matched_rule": "default",
        "candidates": candidates,
        "best_score": int(best.score),
        "second_score": int(second_score),
        "threshold_blocked": bool(threshold_blocked),
        "load_errors": load_errors,
    }


def resolve_effective_skill(
    *,
    app_root: Path,
    role_hint: Optional[str],
    requested_skill_id: Optional[str],
    last_user_text: str,
    detect_assignment_intent: Optional[Callable[[str], bool]] = None,
) -> Dict[str, Any]:
    loaded = load_skills(app_root / "skills")
    skills = dict(loaded.skills or {})
    role = str(role_hint or "").strip()
    text = str(last_user_text or "").strip().lower()
    load_errors = len(loaded.errors or [])

    available_ids = sorted([skill_id for skill_id, spec in skills.items() if _role_allowed(spec, role)])
    default_skill_id = _default_from_available(role, available_ids)

    requested = str(requested_skill_id or "").strip()
    requested_valid, requested_exists, requested_allowed = _requested_state(requested, skills, available_ids)

    if requested and requested_valid and requested_allowed:
        return {
            "requested_skill_id": requested,
            "effective_skill_id": requested,
            "reason": "explicit",
            "confidence": 1.0,
            "matched_rule": "explicit",
            "candidates": [],
            "best_score": 0,
            "second_score": 0,
            "threshold_blocked": False,
            "load_errors": load_errors,
        }

    assignment_intent = _resolve_assignment_intent(
        role,
        last_user_text=last_user_text,
        detect_assignment_intent=detect_assignment_intent,
    )
    assignment_generation = _is_explicit_assignment_generation(text)
    score_rows = _build_score_rows(
        available_ids=available_ids,
        skills=skills,
        role=role,
        text=text,
        assignment_intent=assignment_intent,
        assignment_generation=assignment_generation,
    )
    best = score_rows[0] if score_rows else None
    second_score = score_rows[1].score if len(score_rows) > 1 else 0
    candidates = _build_candidates(score_rows)

    if best is not None:
        return _build_best_match_result(
            best=best,
            second_score=second_score,
            requested=requested,
            requested_valid=requested_valid,
            requested_exists=requested_exists,
            requested_allowed=requested_allowed,
            default_skill_id=default_skill_id,
            candidates=candidates,
            load_errors=load_errors,
        )

    reason = _resolve_default_reason(
        requested,
        requested_valid=requested_valid,
        requested_exists=requested_exists,
        requested_allowed=requested_allowed,
    )

    effective = default_skill_id or (requested if requested_allowed else "")
    if not effective and available_ids:
        effective = available_ids[0]
        reason = f"{reason}_first_available"

    return {
        "requested_skill_id": requested,
        "effective_skill_id": effective,
        "reason": reason,
        "confidence": 0.28 if effective else 0.0,
        "matched_rule": "default",
        "candidates": candidates,
        "best_score": 0,
        "second_score": 0,
        "threshold_blocked": False,
        "load_errors": load_errors,
    }
