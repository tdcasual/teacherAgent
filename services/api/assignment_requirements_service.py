from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class AssignmentRequirementsDeps:
    data_dir: Path
    now_iso: Callable[[], str]


def _resolve_assignment_dir(data_dir: Path, assignment_id: str) -> Path:
    root = (data_dir / "assignments").resolve()
    aid = str(assignment_id or "").strip()
    if not aid:
        raise ValueError("assignment_id is required")
    target = (root / aid).resolve()
    if target != root and root not in target.parents:
        raise ValueError("invalid assignment_id")
    return target


def parse_list_value(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        parts = [p.strip() for p in value.replace("，", ",").replace(";", ",").split(",")]
        return [p for p in parts if p]
    return []


def normalize_preferences(values: List[str]) -> Tuple[List[str], List[str]]:
    pref_map = {
        "A": "A基础",
        "基础": "A基础",
        "A基础": "A基础",
        "B": "B提升",
        "提升": "B提升",
        "B提升": "B提升",
        "C": "C生活应用",
        "生活应用": "C生活应用",
        "C生活应用": "C生活应用",
        "D": "D探究",
        "探究": "D探究",
        "D探究": "D探究",
        "E": "E小测验",
        "小测验": "E小测验",
        "E小测验": "E小测验",
        "F": "F错题反思",
        "错题反思": "F错题反思",
        "F错题反思": "F错题反思",
    }
    normalized: List[str] = []
    invalid: List[str] = []
    for val in values:
        key = str(val).strip()
        if not key:
            continue
        mapped = pref_map.get(key)
        if not mapped:
            invalid.append(key)
            continue
        if mapped not in normalized:
            normalized.append(mapped)
    return normalized, invalid


def normalize_class_level(value: str) -> Optional[str]:
    if not value:
        return None
    mapping = {
        "偏弱": "偏弱",
        "弱": "偏弱",
        "中等": "中等",
        "一般": "中等",
        "较强": "较强",
        "强": "较强",
        "混合": "混合",
    }
    return mapping.get(value.strip())


def parse_duration(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    text = str(value)
    match = re.search(r"\d+", text)
    if not match:
        return None
    try:
        return int(match.group(0))
    except Exception:
        return None


def normalize_difficulty(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "basic"
    lowered = raw.lower()
    mapping = {
        "basic": "basic",
        "medium": "medium",
        "advanced": "advanced",
        "challenge": "challenge",
        "easy": "basic",
        "intermediate": "medium",
        "hard": "advanced",
        "expert": "challenge",
        "very hard": "challenge",
        "very_hard": "challenge",
        "入门": "basic",
        "简单": "basic",
        "基础": "basic",
        "中等": "medium",
        "一般": "medium",
        "提高": "medium",
        "较难": "advanced",
        "困难": "advanced",
        "拔高": "advanced",
        "压轴": "challenge",
        "挑战": "challenge",
    }
    if lowered in mapping:
        return mapping[lowered]
    for key, norm in mapping.items():
        if key and key in raw:
            return norm
    return "basic"


def validate_requirements(payload: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    errors: List[str] = []

    subject = str(payload.get("subject", "")).strip()
    if not subject:
        errors.append("1) 学科 必填")

    topic = str(payload.get("topic", "")).strip()
    if not topic:
        errors.append("1) 本节课主题 必填")

    grade_level = str(payload.get("grade_level", "")).strip()
    if not grade_level:
        errors.append("2) 学生学段/年级 必填")

    class_level_raw = str(payload.get("class_level", "")).strip()
    class_level = normalize_class_level(class_level_raw)
    if not class_level:
        errors.append("2) 班级整体水平 必须是 偏弱/中等/较强/混合")

    core_concepts = parse_list_value(payload.get("core_concepts"))
    if len(core_concepts) < 3 or len(core_concepts) > 8:
        errors.append("3) 核心概念/公式/规律 需要 3-8 个关键词")

    typical_problem = str(payload.get("typical_problem", "")).strip()
    if not typical_problem:
        errors.append("4) 课堂典型题型/例题 必填")

    misconceptions = parse_list_value(payload.get("misconceptions"))
    if len(misconceptions) < 4:
        errors.append("5) 易错点/易混点 至少 4 条")

    duration = parse_duration(payload.get("duration_minutes") or payload.get("duration"))
    if duration not in {20, 40, 60}:
        errors.append("6) 作业时间 仅可选 20/40/60 分钟")

    preferences_raw = parse_list_value(payload.get("preferences"))
    preferences, invalid = normalize_preferences(preferences_raw)
    if invalid:
        errors.append(f"7) 作业偏好 无效项: {', '.join(invalid)}")
    if not preferences:
        errors.append("7) 作业偏好 至少选择 1 项")

    extra_constraints = str(payload.get("extra_constraints", "") or "").strip()

    if errors:
        return None, errors

    normalized = {
        "subject": subject,
        "topic": topic,
        "grade_level": grade_level,
        "class_level": class_level,
        "core_concepts": core_concepts,
        "typical_problem": typical_problem,
        "misconceptions": misconceptions,
        "duration_minutes": duration,
        "preferences": preferences,
        "extra_constraints": extra_constraints,
    }
    return normalized, []


def compute_requirements_missing(requirements: Dict[str, Any]) -> List[str]:
    missing: List[str] = []
    if not str(requirements.get("subject", "")).strip():
        missing.append("subject")
    if not str(requirements.get("topic", "")).strip():
        missing.append("topic")
    if not str(requirements.get("grade_level", "")).strip():
        missing.append("grade_level")
    class_level = normalize_class_level(str(requirements.get("class_level", "")).strip() or "")
    if not class_level:
        missing.append("class_level")
    core_concepts = parse_list_value(requirements.get("core_concepts"))
    if len(core_concepts) < 3:
        missing.append("core_concepts")
    if not str(requirements.get("typical_problem", "")).strip():
        missing.append("typical_problem")
    misconceptions = parse_list_value(requirements.get("misconceptions"))
    if len(misconceptions) < 4:
        missing.append("misconceptions")
    duration = parse_duration(requirements.get("duration_minutes") or requirements.get("duration"))
    if duration not in {20, 40, 60}:
        missing.append("duration_minutes")
    preferences_raw = parse_list_value(requirements.get("preferences"))
    preferences, _ = normalize_preferences(preferences_raw)
    if not preferences:
        missing.append("preferences")
    return missing


def merge_requirements(base: Dict[str, Any], update: Dict[str, Any], overwrite: bool = False) -> Dict[str, Any]:
    merged = dict(base or {})
    for key, val in (update or {}).items():
        if val in (None, "", [], {}):
            continue
        if overwrite:
            if isinstance(val, list):
                merged[key] = parse_list_value(val)
            else:
                merged[key] = val
            continue
        if isinstance(val, list):
            base_list = parse_list_value(merged.get(key))
            update_list = parse_list_value(val)
            if not base_list:
                merged[key] = update_list
            elif len(base_list) < 3:
                merged[key] = base_list + [item for item in update_list if item not in base_list]
            continue
        if not merged.get(key):
            merged[key] = val
    return merged


def save_assignment_requirements(
    assignment_id: str,
    requirements: Dict[str, Any],
    date_str: str,
    *,
    deps: AssignmentRequirementsDeps,
    created_by: str = "teacher",
    validate: bool = True,
) -> Dict[str, Any]:
    try:
        out_dir = _resolve_assignment_dir(deps.data_dir, assignment_id)
    except ValueError as exc:
        return {"error": "invalid_assignment_id", "detail": str(exc)}
    payload = requirements
    if validate:
        normalized, errors = validate_requirements(requirements)
        if errors:
            return {"error": "invalid_requirements", "errors": errors}
        payload = normalized or {}
    out_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "assignment_id": assignment_id,
        "date": date_str,
        "created_by": created_by,
        "created_at": deps.now_iso(),
        **(payload or {}),
    }
    req_path = out_dir / "requirements.json"
    req_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "path": str(req_path), "requirements": record}


def ensure_requirements_for_assignment(
    assignment_id: str,
    date_str: str,
    requirements: Optional[Dict[str, Any]],
    source: str,
    *,
    deps: AssignmentRequirementsDeps,
) -> Optional[Dict[str, Any]]:
    try:
        out_dir = _resolve_assignment_dir(deps.data_dir, assignment_id)
    except ValueError as exc:
        return {"error": "invalid_assignment_id", "detail": str(exc)}
    if source == "auto":
        return None
    if requirements:
        return save_assignment_requirements(
            assignment_id,
            requirements,
            date_str,
            created_by="teacher",
            deps=deps,
        )
    req_path = out_dir / "requirements.json"
    if not req_path.exists():
        return {"error": "requirements_missing", "detail": "请先提交作业要求（8项）。"}
    return None


def format_requirements_prompt(errors: Optional[List[str]] = None, include_assignment_id: bool = False) -> str:
    lines: List[str] = []
    if errors:
        lines.append("作业要求不完整或不规范，请补充/修正以下内容：")
        for err in errors:
            lines.append(f"- {err}")
        lines.append("")
    if include_assignment_id:
        lines.append("请先提供作业ID（建议包含日期，如 A2403_2026-02-04），然后补全作业要求。")
        lines.append("")
    lines.append("请按以下格式补全作业要求（8项）：")
    lines.append("1）学科 + 本节课主题：")
    lines.append("2）学生学段/年级 & 班级整体水平（偏弱/中等/较强/混合）：")
    lines.append("3）本节课核心概念/公式/规律（3–8个关键词）：")
    lines.append("4）课堂典型题型/例题（给1题题干或描述题型特征即可）：")
    lines.append("5）本节课易错点/易混点清单（至少4条，写清“错在哪里/混在哪里”）：")
    lines.append("6）作业时间：20/40/60分钟（选一个）：")
    lines.append("7）作业偏好（可多选）：A基础 B提升 C生活应用 D探究 E小测验 F错题反思：")
    lines.append("8）额外限制（可选）：是否允许画图/用计算器/步骤规范/拓展点等")
    return "\n".join(lines)
