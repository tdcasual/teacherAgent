from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

_log = logging.getLogger(__name__)

_SUBJECT_ID_ALIASES = {
    "physics": "physics",
    "math": "math",
    "generic": "generic",
    "物理": "physics",
    "数学": "math",
    "通用": "generic",
}


@dataclass(frozen=True)
class TeacherAssignmentPreflightDeps:
    app_root: Path
    detect_assignment_intent: Callable[[str], bool]
    llm_assignment_gate: Callable[[Any], Optional[Dict[str, Any]]]
    diag_log: Callable[[str, Dict[str, Any]], None]
    allowed_tools: Callable[[str], Any]
    parse_date_str: Callable[[Optional[str]], str]
    today_iso: Callable[[], str]
    format_requirements_prompt: Callable[..., str]
    save_assignment_requirements: Callable[..., Dict[str, Any]]
    assignment_generate: Callable[[Dict[str, Any]], Dict[str, Any]]


def _looks_like_full_template_prompt(prompt: str) -> bool:
    text = str(prompt or "").strip()
    if not text:
        return False
    if "共8项" in text or "请按此模板回复" in text:
        return True
    if "为了生成一份高质量的作业" in text and "1." in text and "8." in text:
        return True
    return False


def _build_incremental_missing_prompt(missing: List[str]) -> str:
    normalized = [str(item).strip() for item in (missing or []) if str(item).strip()]
    if not normalized:
        return "老师，请补充缺失信息后我将继续生成作业。"
    lines = ["老师，已收到大部分作业信息。请仅补充以下内容："]
    for idx, item in enumerate(normalized, start=1):
        lines.append(f"{idx}. {item}")
    lines.append("补充后我将继续生成作业。")
    return "\n".join(lines)


_LESSON_ID_FALLBACK_RE = re.compile(r"(?<![0-9A-Za-z_-])(L[0-9A-Za-z_-]{3,})(?![0-9A-Za-z_-])")


def _extract_lesson_id_from_messages(req: Any) -> Optional[str]:
    messages = list(getattr(req, "messages", []) or [])
    for msg in reversed(messages):
        content = str(getattr(msg, "content", "") or "")
        fallback = _LESSON_ID_FALLBACK_RE.search(content)
        if fallback:
            return fallback.group(1)
    return None


def _looks_like_ambiguous_student_focus_request(text: str) -> bool:
    content = str(text or "").strip()
    ambiguous_markers = ("这个学生", "该学生", "某个学生", "一位学生", "这个同学", "该同学")
    return any(marker in content for marker in ambiguous_markers)


def teacher_workflow_preflight_reply(
    req: Any,
    *,
    effective_skill_id: str,
    last_user_text: str,
    attachment_context: str,
    deps: TeacherAssignmentPreflightDeps,
) -> Optional[str]:
    skill_id = str(effective_skill_id or "").strip()
    attachment = str(attachment_context or "").strip()

    if skill_id == "physics-student-focus":
        student_id = str(getattr(req, "student_id", "") or "").strip()
        if not student_id and _looks_like_ambiguous_student_focus_request(last_user_text):
            deps.diag_log(
                "teacher_preflight.workflow_student_focus_missing_identity",
                {"skill_id": skill_id, "query_preview": str(last_user_text or "")[:160]},
            )
            return "当前按学生重点分析 workflow 处理。请补充学生姓名、学号或班级信息后继续。"

    if skill_id == "physics-lesson-capture":
        lesson_id = _extract_lesson_id_from_messages(req)
        if not attachment and not lesson_id:
            deps.diag_log(
                "teacher_preflight.workflow_lesson_capture_missing_material",
                {"skill_id": skill_id, "query_preview": str(last_user_text or "")[:160]},
            )
            return "当前按课堂材料采集 workflow 处理。请上传课堂材料，或提供课堂编号后继续。"

    return None


def _last_user_text(req: Any) -> str:
    return next((m.content for m in reversed(req.messages) if m.role == "user"), "") or ""


def _assignment_analysis_or_skip(
    req: Any,
    last_user_text: str,
    *,
    deps: TeacherAssignmentPreflightDeps,
) -> Optional[Dict[str, Any]]:
    if not deps.detect_assignment_intent(last_user_text):
        deps.diag_log("teacher_preflight.skip", {"reason": "no_assignment_intent"})
        return None

    analysis = deps.llm_assignment_gate(req)
    if not analysis:
        deps.diag_log("teacher_preflight.skip", {"reason": "llm_gate_none"})
        return None
    if analysis.get("intent") != "assignment":
        deps.diag_log("teacher_preflight.skip", {"reason": "intent_other"})
        return None
    return analysis


def _allowed_assignment_tools(
    req: Any,
    *,
    deps: TeacherAssignmentPreflightDeps,
) -> Tuple[set[str], Any]:
    allowed = set(deps.allowed_tools("teacher"))
    loaded = None
    try:
        from .skills.loader import load_skills
        from .skills.router import resolve_skill

        loaded = load_skills(deps.app_root / "skills")
        requested = str(getattr(req, "skill_id", "") or "").strip()
        selection = resolve_skill(
            loaded,
            requested,
            "teacher",
            extra_skill_ids=(requested,) if requested else (),
        )
        spec = selection.skill
        if spec:
            if spec.agent.tools.allow is not None:
                allowed &= set(spec.agent.tools.allow)
            if spec.agent.tools.deny:
                allowed -= set(spec.agent.tools.deny)
    except Exception as exc:
        _log.debug("operation failed", exc_info=True)
        deps.diag_log("teacher_preflight.skill_policy_failed", {"error": str(exc)[:200]})
    return allowed, loaded


def _disabled_assignment_generation_reply(
    loaded: Any, *, deps: TeacherAssignmentPreflightDeps
) -> str:
    title = "作业生成"
    try:
        if loaded:
            hw = loaded.skills.get("homework-generator") or loaded.skills.get("physics-homework-generator")
            if hw and hw.title:
                title = hw.title
    except Exception:
        _log.debug("operation failed", exc_info=True)
    deps.diag_log("teacher_preflight.skip", {"reason": "skill_policy_denied"})
    return f"当前技能未开启作业生成功能。请切换到「{title}」技能后再试。"


def _assignment_identity_and_date(
    req: Any,
    analysis: Dict[str, Any],
    *,
    deps: TeacherAssignmentPreflightDeps,
) -> Tuple[Any, str]:
    assignment_id = analysis.get("assignment_id") or req.assignment_id
    date_str = deps.parse_date_str(analysis.get("date") or req.assignment_date or deps.today_iso())
    return assignment_id, date_str


def _missing_fields(analysis: Dict[str, Any], assignment_id: Any) -> List[str]:
    missing = list(analysis.get("missing") or [])
    if not assignment_id and "作业ID" not in missing:
        missing = ["作业ID"] + missing
    return missing


def _missing_reply(
    analysis: Dict[str, Any],
    assignment_id: Any,
    missing: List[str],
    *,
    deps: TeacherAssignmentPreflightDeps,
) -> str:
    deps.diag_log("teacher_preflight.missing", {"missing": missing})
    prompt = analysis.get("next_prompt") or deps.format_requirements_prompt(
        errors=missing, include_assignment_id=not assignment_id
    )
    prompt_text = str(prompt or "")
    if len(missing) <= 3 and (not prompt_text or _looks_like_full_template_prompt(prompt_text)):
        return _build_incremental_missing_prompt(missing)
    return str(prompt)


def _maybe_save_requirements(
    analysis: Dict[str, Any],
    assignment_id: Any,
    date_str: str,
    *,
    deps: TeacherAssignmentPreflightDeps,
) -> None:
    requirements_payload = analysis.get("requirements") or {}
    if requirements_payload:
        deps.save_assignment_requirements(
            assignment_id, requirements_payload, date_str, created_by="teacher", validate=False
        )


def _preflight_subject_id(analysis: Dict[str, Any]) -> str:
    requirements = analysis.get("requirements")
    req = requirements if isinstance(requirements, dict) else {}
    raw = str(
        analysis.get("subject_id")
        or analysis.get("subject")
        or req.get("subject_id")
        or req.get("subject")
        or ""
    ).strip()
    if not raw:
        return ""
    return _SUBJECT_ID_ALIASES.get(raw) or _SUBJECT_ID_ALIASES.get(raw.lower()) or raw


def _generate_assignment_reply(
    analysis: Dict[str, Any],
    assignment_id: Any,
    date_str: str,
    *,
    deps: TeacherAssignmentPreflightDeps,
) -> str:
    if not analysis.get("ready_to_generate"):
        deps.diag_log("teacher_preflight.not_ready", {"assignment_id": assignment_id})
        return (
            analysis.get("next_prompt")
            or "已保存作业要求。请补充知识点或上传截图题目后再生成作业。"
        )

    kp_list = analysis.get("kp_list") or []
    question_ids = analysis.get("question_ids") or []
    per_kp = analysis.get("per_kp") or 5
    mode = analysis.get("mode") or "kp"
    args = {
        "assignment_id": assignment_id,
        "kp": ",".join(kp_list) if kp_list else "",
        "question_ids": ",".join(question_ids) if question_ids else "",
        "per_kp": per_kp,
        "mode": mode,
        "date": date_str,
        "due_at": str(analysis.get("due_at") or "").strip(),
        "subject_id": _preflight_subject_id(analysis),
        "source": "teacher",
        "skip_validation": True,
    }
    result = deps.assignment_generate(args)
    if result.get("error"):
        deps.diag_log("teacher_preflight.generate_error", {"error": result.get("error")})
        return analysis.get("next_prompt") or deps.format_requirements_prompt(
            errors=[str(result.get("error"))]
        )

    deps.diag_log(
        "teacher_preflight.generated",
        {
            "assignment_id": assignment_id,
            "mode": mode,
            "per_kp": per_kp,
        },
    )
    output = result.get("output", "")
    return (
        f"作业草稿已写入：{assignment_id}（visibility_status=draft，对学生不可见）。\n"
        f"- 日期：{date_str}\n"
        f"- 模式：{mode}\n"
        f"- 每个知识点题量：{per_kp}\n"
        f"请到工作台确认后再发布（assignment.publish）。\n"
        f"{output}"
    )


def teacher_assignment_preflight(
    req: Any, *, deps: TeacherAssignmentPreflightDeps
) -> Optional[str]:
    last_user_text = _last_user_text(req)

    analysis = _assignment_analysis_or_skip(req, last_user_text, deps=deps)
    if not analysis:
        return None

    required_tools = {"assignment.generate", "assignment.requirements.save"}
    allowed, loaded = _allowed_assignment_tools(req, deps=deps)
    if not required_tools.issubset(allowed):
        return _disabled_assignment_generation_reply(loaded, deps=deps)

    assignment_id, date_str = _assignment_identity_and_date(req, analysis, deps=deps)
    missing = _missing_fields(analysis, assignment_id)
    if missing:
        return _missing_reply(analysis, assignment_id, missing, deps=deps)

    _maybe_save_requirements(analysis, assignment_id, date_str, deps=deps)
    return _generate_assignment_reply(analysis, assignment_id, date_str, deps=deps)
