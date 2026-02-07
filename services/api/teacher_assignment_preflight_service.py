from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional


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


def teacher_assignment_preflight(req: Any, *, deps: TeacherAssignmentPreflightDeps) -> Optional[str]:
    last_user_text = next((m.content for m in reversed(req.messages) if m.role == "user"), "") or ""
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

    required_tools = {"assignment.generate", "assignment.requirements.save"}
    allowed = set(deps.allowed_tools("teacher"))
    loaded = None
    try:
        from .skills.loader import load_skills
        from .skills.router import resolve_skill

        loaded = load_skills(deps.app_root / "skills")
        selection = resolve_skill(loaded, req.skill_id, "teacher")
        spec = selection.skill
        if spec:
            if spec.agent.tools.allow is not None:
                allowed &= set(spec.agent.tools.allow)
            if spec.agent.tools.deny:
                allowed -= set(spec.agent.tools.deny)
    except Exception as exc:
        deps.diag_log("teacher_preflight.skill_policy_failed", {"error": str(exc)[:200]})

    if not required_tools.issubset(allowed):
        title = "作业生成"
        try:
            if loaded:
                hw = loaded.skills.get("physics-homework-generator")
                if hw and hw.title:
                    title = hw.title
        except Exception:
            pass
        deps.diag_log("teacher_preflight.skip", {"reason": "skill_policy_denied"})
        return f"当前技能未开启作业生成功能。请切换到「{title}」技能后再试。"

    assignment_id = analysis.get("assignment_id") or req.assignment_id
    date_str = deps.parse_date_str(analysis.get("date") or req.assignment_date or deps.today_iso())

    missing = analysis.get("missing") or []
    if not assignment_id and "作业ID" not in missing:
        missing = ["作业ID"] + missing

    if missing:
        deps.diag_log("teacher_preflight.missing", {"missing": missing})
        prompt = analysis.get("next_prompt") or deps.format_requirements_prompt(errors=missing, include_assignment_id=not assignment_id)
        return prompt

    requirements_payload = analysis.get("requirements") or {}
    if requirements_payload:
        deps.save_assignment_requirements(assignment_id, requirements_payload, date_str, created_by="teacher", validate=False)

    if not analysis.get("ready_to_generate"):
        deps.diag_log("teacher_preflight.not_ready", {"assignment_id": assignment_id})
        return analysis.get("next_prompt") or "已保存作业要求。请补充知识点或上传截图题目后再生成作业。"

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
        "source": "teacher",
        "skip_validation": True,
    }
    result = deps.assignment_generate(args)
    if result.get("error"):
        deps.diag_log("teacher_preflight.generate_error", {"error": result.get("error")})
        return analysis.get("next_prompt") or deps.format_requirements_prompt(errors=[str(result.get("error"))])
    output = result.get("output", "")
    deps.diag_log(
        "teacher_preflight.generated",
        {
            "assignment_id": assignment_id,
            "mode": mode,
            "per_kp": per_kp,
        },
    )
    return (
        f"作业已生成：{assignment_id}\n"
        f"- 日期：{date_str}\n"
        f"- 模式：{mode}\n"
        f"- 每个知识点题量：{per_kp}\n"
        f"{output}"
    )
