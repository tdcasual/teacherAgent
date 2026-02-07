from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .skills.loader import load_skills
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
    "physics-teacher-ops",
    "physics-student-coach",
]
_TIE_BREAK_INDEX = {skill_id: idx for idx, skill_id in enumerate(_TIE_BREAK_ORDER)}


@dataclass(frozen=True)
class _ScoreRow:
    skill_id: str
    score: int
    hits: List[str]


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


def _score_from_skill_config(
    skill_spec: Any,
    text: str,
    *,
    assignment_intent: bool,
    assignment_generation: bool,
) -> Tuple[int, List[str]]:
    routing = getattr(skill_spec, "routing", None)
    if routing is None:
        return 0, []

    score = 0
    hits: List[str] = []
    keywords = [str(x or "").strip().lower() for x in (getattr(routing, "keywords", []) or [])]
    negative_keywords = [str(x or "").strip().lower() for x in (getattr(routing, "negative_keywords", []) or [])]
    intents = [str(x or "").strip().lower() for x in (getattr(routing, "intents", []) or [])]
    raw_weights = dict(getattr(routing, "keyword_weights", {}) or {})
    keyword_weights = {
        str(key or "").strip().lower(): max(1, int(value))
        for key, value in raw_weights.items()
        if str(key or "").strip()
    }

    for key in keywords:
        if not key:
            continue
        if key in text:
            score += min(50, max(1, int(keyword_weights.get(key, 3))))
            hits.append(f"cfg:{key}")

    for key in negative_keywords:
        if not key:
            continue
        if key in text:
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

    return score, hits


def _score_teacher_skill(
    skill_id: str,
    text: str,
    *,
    assignment_intent: bool,
    assignment_generation: bool,
) -> Tuple[int, List[str]]:
    score = 0
    hits: List[str] = []

    if skill_id == "physics-homework-generator":
        if assignment_intent and assignment_generation:
            score += 8
            hits.append("assignment_generation")
        elif assignment_intent:
            score += 2
            hits.append("assignment_intent")
        for key, weight in (
            ("生成作业", 4),
            ("布置作业", 4),
            ("作业id", 4),
            ("作业 id", 4),
            ("课后作业", 3),
            ("每个知识点", 2),
            ("题量", 2),
            ("渲染作业", 2),
        ):
            if key in text:
                score += weight
                hits.append(key)
        if "作业" in text:
            score += 1
            hits.append("作业")
        return score, hits

    if skill_id == "physics-llm-routing":
        if _ROUTING_RE.search(text):
            score += 7
            hits.append("routing_regex")
        for key, weight in (
            ("teacher.llm_routing", 6),
            ("channel", 2),
            ("fallback", 2),
            ("provider", 2),
            ("model", 2),
        ):
            if key in text:
                score += weight
                hits.append(key)
        return score, hits

    if skill_id == "physics-lesson-capture":
        has_lesson = ("课堂" in text) or ("lesson" in text)
        has_capture = any(
            key in text
            for key in ("采集", "ocr", "识别", "抽取", "板书", "课件", "课堂材料")
        )
        if has_lesson and has_capture:
            score += 7
            hits.append("lesson_capture_combo")
        for key, weight in (
            ("课堂采集", 4),
            ("采集课堂", 4),
            ("lesson.capture", 4),
            ("ocr", 2),
            ("课堂材料", 2),
        ):
            if key in text:
                score += weight
                hits.append(key)
        return score, hits

    if skill_id == "physics-core-examples":
        if _CE_ID_RE.search(text):
            score += 5
            hits.append("ce_id")
        for key, weight in (
            ("核心例题", 5),
            ("变式题", 4),
            ("例题库", 3),
            ("登记例题", 3),
            ("标准解法", 2),
            ("core_example", 2),
        ):
            if key in text:
                score += weight
                hits.append(key)
        return score, hits

    if skill_id == "physics-student-focus":
        has_student = ("学生" in text) or ("同学" in text)
        has_focus = any(
            key in text
            for key in ("画像", "诊断", "最近作业", "薄弱", "个体", "个人", "针对")
        )
        if has_student and has_focus:
            score += 7
            hits.append("student_focus_combo")
        if _SINGLE_STUDENT_RE.search(text):
            score += 4
            hits.append("single_student_regex")
        return score, hits

    if skill_id == "physics-teacher-ops":
        for key, weight in (
            ("考试分析", 5),
            ("分析考试", 5),
            ("试卷", 3),
            ("讲评", 3),
            ("备课", 3),
            ("课前检测", 3),
            ("课堂讨论", 2),
            ("exam", 2),
        ):
            if key in text:
                score += weight
                hits.append(key)
        return score, hits

    return score, hits


def _score_role_skill(
    role_hint: Optional[str],
    skill_id: str,
    text: str,
    *,
    assignment_intent: bool,
    assignment_generation: bool,
) -> Tuple[int, List[str]]:
    role = str(role_hint or "").strip()
    if role == "teacher":
        return _score_teacher_skill(
            skill_id,
            text,
            assignment_intent=assignment_intent,
            assignment_generation=assignment_generation,
        )
    if role == "student":
        if skill_id == "physics-student-coach":
            score = 0
            hits: List[str] = []
            for key, weight in (
                ("开始今天作业", 4),
                ("开始作业", 3),
                ("开始练习", 3),
                ("诊断", 2),
                ("讲解", 2),
                ("错题", 2),
            ):
                if key in text:
                    score += weight
                    hits.append(key)
            return score, hits
        return 0, []
    return 0, []


def _confidence_for_auto(best: int, second: int) -> float:
    gap = max(0, best - second)
    base = 0.48 + min(0.30, best * 0.05)
    boost = 0.06 if gap >= 3 else (0.03 if gap >= 1 else 0.0)
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
) -> Dict[str, Any]:
    loaded = load_skills(app_root / "skills")
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
        cfg_score, cfg_hits = _score_from_skill_config(
            spec,
            text,
            assignment_intent=assignment_intent,
            assignment_generation=assignment_generation,
        )
        rule_score, rule_hits = _score_role_skill(
            role,
            skill_id,
            text,
            assignment_intent=assignment_intent,
            assignment_generation=assignment_generation,
        )
        score = int(cfg_score) + int(rule_score)
        hits = list(cfg_hits) + list(rule_hits)
        if score > 0:
            score_rows.append(_ScoreRow(skill_id=skill_id, score=score, hits=hits))

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
        reason_prefix = ""
        if requested and not requested_valid:
            reason_prefix = "requested_invalid_"
        elif requested and requested_valid and not requested_exists:
            reason_prefix = "requested_unknown_"
        elif requested and requested_valid and requested_exists and not requested_allowed:
            reason_prefix = "requested_not_allowed_"
        return {
            "requested_skill_id": requested,
            "effective_skill_id": best.skill_id,
            "reason": f"{reason_prefix}auto_rule",
            "confidence": _confidence_for_auto(best.score, second_score),
            "matched_rule": ",".join(best.hits[:3]) or "auto_rule",
            "candidates": candidates,
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
        "load_errors": len(loaded.errors or []),
    }
