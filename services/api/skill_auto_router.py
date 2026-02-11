from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .skills.loader import load_skills
from .skills.auto_route_rules import score_role_skill
from .skills.router import default_skill_id_for_role


_SKILL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{1,80}$")
_CE_ID_RE = re.compile(r"\bCE\d+\b", flags=re.I)
_SINGLE_STUDENT_RE = re.compile(r"(某个学生|单个学生|该学生|同学.*(画像|诊断|表现))")
_ROUTING_RE = re.compile(r"(llm\s*routing|模型路由|路由(配置|仿真|回滚|策略|规则))", flags=re.I)

_TIE_BREAK_ORDER = [
    "physics-llm-routing",
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

    score = 0
    hits: List[str] = []
    keywords = [str(x or "").strip().lower() for x in (getattr(routing, "keywords", []) or [])]
    negative_keywords = [str(x or "").strip().lower() for x in (getattr(routing, "negative_keywords", []) or [])]
    intents = [str(x or "").strip().lower() for x in (getattr(routing, "intents", []) or [])]
    raw_weights = dict(getattr(routing, "keyword_weights", {}) or {})
    match_mode = str(getattr(routing, "match_mode", "substring") or "substring").strip().lower()
    min_score = max(1, int(getattr(routing, "min_score", 3) or 3))
    min_margin = max(0, int(getattr(routing, "min_margin", 1) or 1))
    confidence_floor = float(getattr(routing, "confidence_floor", 0.28) or 0.28)
    confidence_floor = max(0.0, min(0.95, confidence_floor))

    keyword_weights = {
        str(key or "").strip().lower(): max(1, int(value))
        for key, value in raw_weights.items()
        if str(key or "").strip()
    }

    for key in keywords:
        if not key:
            continue
        if _keyword_hit(text, key, match_mode):
            score += min(50, max(1, int(keyword_weights.get(key, 3))))
            hits.append(f"cfg:{key}")

    for key in negative_keywords:
        if not key:
            continue
        if _keyword_hit(text, key, match_mode):
            score -= 3
            hits.append(f"cfg-neg:{key}")

    if "assignment_generate" in intents and assignment_generation:
        score += 8
        hits.append("cfg-intent:assignment_generate")
    elif "assignment" in intents and assignment_intent:
        score += 4
        hits.append("cfg-intent:assignment")

    if "routing" in intents and _ROUTING_RE.search(text):
        score += 6
        hits.append("cfg-intent:routing")
    if "student_focus" in intents and (("学生" in text) or ("画像" in text) or ("诊断" in text)):
        score += 4
        hits.append("cfg-intent:student_focus")
    if "lesson_capture" in intents and (("课堂" in text) or ("lesson" in text)) and (
        ("采集" in text) or ("ocr" in text) or ("识别" in text)
    ):
        score += 4
        hits.append("cfg-intent:lesson_capture")
    if "core_examples" in intents and (("例题" in text) or ("变式题" in text) or bool(_CE_ID_RE.search(text))):
        score += 4
        hits.append("cfg-intent:core_examples")
    if "teacher_ops" in intents and (("考试" in text) or ("讲评" in text) or ("备课" in text)):
        score += 3
        hits.append("cfg-intent:teacher_ops")
    if "student_coach" in intents and (("开始作业" in text) or ("开始练习" in text) or ("讲解错题" in text)):
        score += 4
        hits.append("cfg-intent:student_coach")

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


def resolve_effective_skill(
    *,
    app_root: Path,
    role_hint: Optional[str],
    requested_skill_id: Optional[str],
    last_user_text: str,
    detect_assignment_intent: Optional[Callable[[str], bool]] = None,
    teacher_skills_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    loaded = load_skills(app_root / "skills", teacher_skills_dir=teacher_skills_dir)
    skills = dict(loaded.skills or {})
    role = str(role_hint or "").strip()
    text = str(last_user_text or "").strip().lower()

    available_ids = sorted(
        [skill_id for skill_id, spec in skills.items() if _role_allowed(spec, role)]
    )
    default_skill_id = _default_from_available(role, available_ids)

    requested = str(requested_skill_id or "").strip()
    requested_valid = bool(requested and _SKILL_ID_RE.match(requested))
    requested_exists = requested in skills
    requested_allowed = requested in set(available_ids)

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
            "load_errors": len(loaded.errors or []),
        }

    assignment_intent = False
    if role == "teacher" and callable(detect_assignment_intent):
        try:
            assignment_intent = bool(detect_assignment_intent(last_user_text or ""))
        except Exception:
            assignment_intent = False
    assignment_generation = _is_explicit_assignment_generation(text)

    score_rows: List[_ScoreRow] = []
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
        score = int(cfg_score) + int(rule_score)
        hits = list(cfg_hits) + list(rule_hits)
        if score > 0:
            score_rows.append(
                _ScoreRow(
                    skill_id=skill_id,
                    score=score,
                    hits=hits,
                    min_score=min_score,
                    min_margin=min_margin,
                    confidence_floor=confidence_floor,
                )
            )

    score_rows.sort(
        key=lambda row: (
            -row.score,
            _TIE_BREAK_INDEX.get(row.skill_id, 999),
            row.skill_id,
        )
    )
    best = score_rows[0] if score_rows else None
    second_score = score_rows[1].score if len(score_rows) > 1 else 0

    candidates = [
        {"skill_id": row.skill_id, "score": row.score, "hits": row.hits[:6]}
        for row in score_rows[:3]
    ]

    if best is not None:
        threshold_blocked = best.score < int(best.min_score)
        margin = max(0, int(best.min_margin))
        ambiguous = (best.score - second_score) < margin
        reason_prefix = ""
        if requested and not requested_valid:
            reason_prefix = "requested_invalid_"
        elif requested and requested_valid and not requested_exists:
            reason_prefix = "requested_unknown_"
        elif requested and requested_valid and requested_exists and not requested_allowed:
            reason_prefix = "requested_not_allowed_"

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
                "load_errors": len(loaded.errors or []),
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
            "load_errors": len(loaded.errors or []),
        }

    if requested and requested_valid and requested_exists and not requested_allowed:
        reason = "requested_not_allowed_default"
    elif requested and requested_valid and not requested_exists:
        reason = "requested_unknown_default"
    elif requested and not requested_valid:
        reason = "requested_invalid_default"
    else:
        reason = "role_default"

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
        "load_errors": len(loaded.errors or []),
    }
