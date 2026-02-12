from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Callable, Dict, Optional

from .subject_score_guard_service import (
    looks_like_subject_score_request,
    should_guard_total_mode_subject_request,
    subject_display,
)

import logging
_log = logging.getLogger(__name__)


def _default_extract_exam_id(_text: str) -> Optional[str]:
    return None


def _default_exam_get(_exam_id: str) -> Dict[str, Any]:
    return {}


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
    extract_exam_id: Callable[[str], Optional[str]] = _default_extract_exam_id
    exam_get: Callable[[str], Dict[str, Any]] = _default_exam_get


_EXAM_ID_FALLBACK_RE = re.compile(r"(?<![0-9A-Za-z_-])(EX[0-9A-Za-z_-]{3,})(?![0-9A-Za-z_-])")


def _extract_exam_id_from_messages(req: Any, deps: TeacherAssignmentPreflightDeps) -> Optional[str]:
    messages = list(getattr(req, "messages", []) or [])
    for msg in reversed(messages):
        content = str(getattr(msg, "content", "") or "")
        exam_id = deps.extract_exam_id(content)
        if exam_id:
            return exam_id
        fallback = _EXAM_ID_FALLBACK_RE.search(content)
        if fallback:
            return fallback.group(1)
    return None


def _fmt_score(value: Any) -> str:
    try:
        return f"{float(value):.1f}"
    except Exception:
        _log.debug("numeric conversion failed", exc_info=True)
        return "-"


def _build_subject_total_mode_reply(
    exam_id: str,
    overview: Dict[str, Any],
    *,
    requested_subject: Optional[str],
    inferred_subject: Optional[str],
) -> str:
    totals = overview.get("totals_summary") if isinstance(overview.get("totals_summary"), dict) else {}
    avg_total = _fmt_score((totals or {}).get("avg_total"))
    median_total = _fmt_score((totals or {}).get("median_total"))
    max_total = _fmt_score((totals or {}).get("max_total_observed"))
    min_total = _fmt_score((totals or {}).get("min_total_observed"))

    requested_label = subject_display(requested_subject)
    inferred_label = subject_display(inferred_subject)

    unsupported_subject_line = (
        f"未提供可验证的{requested_label}单科分数字段。"
        if requested_subject
        else "未提供可验证的单科分数字段。"
    )
    cannot_treat_line = (
        f"因此我不能把总分当作{requested_label}单科成绩。"
        if requested_subject
        else "因此我不能把总分直接当作某一门单科成绩。"
    )

    inferred_hint = ""
    if inferred_subject and inferred_subject != requested_subject:
        inferred_hint = f"从试卷/答案文件名推断，该考试更可能是「{inferred_label}」单科总分。\n\n"

    return (
        f"## 考试 {exam_id} 单科成绩说明\n\n"
        "当前数据为**总分模式**（`score_mode: \"total\"`），系统仅有 `TOTAL` 总分字段，"
        f"{unsupported_subject_line}\n\n"
        f"{cannot_treat_line}\n\n"
        f"{inferred_hint}"
        "可提供的总分统计（供参考）：\n"
        f"- 平均分：{avg_total}\n"
        f"- 中位数：{median_total}\n"
        f"- 最高分：{max_total}\n"
        f"- 最低分：{min_total}\n\n"
        "如需更精准单科分析，请上传包含该学科列或每题得分的成绩表（xlsx）。"
    )


def _subject_score_total_mode_preflight(
    req: Any,
    last_user_text: str,
    deps: TeacherAssignmentPreflightDeps,
) -> Optional[str]:
    if not looks_like_subject_score_request(last_user_text):
        return None

    exam_id = _extract_exam_id_from_messages(req, deps)
    if not exam_id:
        return None

    overview = deps.exam_get(exam_id)
    if not isinstance(overview, dict) or not overview.get("ok"):
        return None

    should_guard, requested_subject, inferred_subject = should_guard_total_mode_subject_request(last_user_text, overview)
    if not should_guard:
        score_mode = str(overview.get("score_mode") or "").strip().lower()
        score_mode_source = str(overview.get("score_mode_source") or "").strip().lower()
        if score_mode_source == "subject_from_scores_file":
            deps.diag_log(
                "teacher_preflight.subject_total_auto_extract_subject",
                {
                    "exam_id": exam_id,
                    "score_mode": score_mode,
                    "score_mode_source": score_mode_source,
                    "requested_subject": requested_subject or "",
                    "inferred_subject": inferred_subject or "",
                    "last_user": last_user_text[:200],
                },
            )
        elif score_mode == "total":
            deps.diag_log(
                "teacher_preflight.subject_total_allow_single_subject",
                {
                    "exam_id": exam_id,
                    "score_mode": "total",
                    "requested_subject": requested_subject or "",
                    "inferred_subject": inferred_subject or "",
                    "last_user": last_user_text[:200],
                },
            )
        return None

    deps.diag_log(
        "teacher_preflight.subject_total_guard",
        {
            "exam_id": exam_id,
            "score_mode": "total",
            "requested_subject": requested_subject or "",
            "inferred_subject": inferred_subject or "",
            "last_user": last_user_text[:200],
        },
    )

    return _build_subject_total_mode_reply(
        exam_id,
        overview,
        requested_subject=requested_subject,
        inferred_subject=inferred_subject,
    )


def teacher_assignment_preflight(req: Any, *, deps: TeacherAssignmentPreflightDeps) -> Optional[str]:
    last_user_text = next((m.content for m in reversed(req.messages) if m.role == "user"), "") or ""

    subject_mode_reply = _subject_score_total_mode_preflight(req, last_user_text, deps)
    if subject_mode_reply:
        return subject_mode_reply

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
        _log.debug("operation failed", exc_info=True)
        deps.diag_log("teacher_preflight.skill_policy_failed", {"error": str(exc)[:200]})

    if not required_tools.issubset(allowed):
        title = "作业生成"
        try:
            if loaded:
                hw = loaded.skills.get("physics-homework-generator")
                if hw and hw.title:
                    title = hw.title
        except Exception:
            _log.debug("operation failed", exc_info=True)
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
