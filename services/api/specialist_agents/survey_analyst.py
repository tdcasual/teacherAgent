from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from ..config import APP_ROOT
from ..survey_bundle_models import SurveyEvidenceBundle
from ..upload_llm_service import parse_llm_json
from .contracts import ArtifactRef, HandoffContract, SpecialistAgentResult

_PROMPT_PATH = APP_ROOT / "prompts" / "v1" / "teacher" / "agents" / "survey_analyst.md"
_DISALLOWED_OUTPUT_KEYS = {
    "student_list",
    "student_profiles",
    "student_actions",
    "action_plan",
    "assignment_plan",
}


@dataclass(frozen=True)
class SurveyAnalystDeps:
    call_llm: Callable[..., Dict[str, Any]]
    prompt_loader: Callable[[], str]
    diag_log: Callable[..., None]



def load_survey_analyst_prompt() -> str:
    try:
        return _PROMPT_PATH.read_text(encoding="utf-8")
    except Exception:
        return "你是问卷分析 specialist agent，只输出 analysis_artifact 的严格 JSON。"



def _to_bundle(value: SurveyEvidenceBundle | Dict[str, Any]) -> SurveyEvidenceBundle:
    if isinstance(value, SurveyEvidenceBundle):
        return value
    return SurveyEvidenceBundle.model_validate(value)



def _dedupe_strings(values: List[str]) -> List[str]:
    seen: set[str] = set()
    result: List[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result



def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None



def _question_signal_fallback(bundle: SurveyEvidenceBundle) -> tuple[List[Dict[str, Any]], List[str]]:
    if not bundle.question_summaries:
        return [], []
    question = bundle.question_summaries[0]
    total = sum(int(value or 0) for value in question.stats.values())
    top_label = ""
    top_count = 0
    for label, count in question.stats.items():
        count_value = int(count or 0)
        if count_value > top_count:
            top_label = str(label)
            top_count = count_value
    detail = question.prompt or question.question_id
    if top_label and total > 0:
        detail = f"{detail} 中，‘{top_label}’反馈 {top_count}/{total}。"
    return (
        [
            {
                "title": question.prompt or question.question_id,
                "detail": detail,
                "evidence_refs": [f"question:{question.question_id}"],
            }
        ],
        [f"围绕‘{question.prompt or question.question_id}’增加分步讲解与当堂检测。"],
    )


def _free_text_signal_fallback(bundle: SurveyEvidenceBundle) -> tuple[List[Dict[str, Any]], List[str]]:
    if not bundle.free_text_signals:
        return [], []
    signal = bundle.free_text_signals[0]
    return (
        [
            {
                "title": f"高频反馈：{signal.theme}",
                "detail": f"共有 {int(signal.evidence_count or 0)} 条反馈提到‘{signal.theme}’。",
                "evidence_refs": [f"theme:{signal.theme}"],
            }
        ],
        [f"针对‘{signal.theme}’补充示例、板书拆解或复盘练习。"],
    )


def _group_differences_fallback(bundle: SurveyEvidenceBundle) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for group in bundle.group_breakdowns[:3]:
        stats_desc = ""
        if group.stats:
            first_key = next(iter(group.stats.keys()))
            stats_desc = f"，{first_key}={group.stats[first_key]}"
        items.append(
            {
                "group_name": group.group_name,
                "summary": f"样本 {group.sample_size or '未知'}{stats_desc}。",
            }
        )
    return items


def _fallback_executive_summary(bundle: SurveyEvidenceBundle, key_signals: List[Dict[str, Any]]) -> str:
    summary_parts: List[str] = []
    if bundle.audience_scope.class_name:
        summary_parts.append(f"{bundle.audience_scope.class_name} 的问卷结果已完成初步分析")
    if key_signals:
        summary_parts.append(str(key_signals[0].get("detail") or key_signals[0].get("title") or ""))
    return "；".join([part for part in summary_parts if part]) or "已生成基于问卷证据的初步班级分析。"


def _fallback_artifact(bundle: SurveyEvidenceBundle) -> Dict[str, Any]:
    key_signals, teaching_recommendations = _question_signal_fallback(bundle)
    free_text_signals, free_text_recommendations = _free_text_signal_fallback(bundle)
    key_signals.extend(free_text_signals)
    teaching_recommendations.extend(free_text_recommendations)
    group_differences = _group_differences_fallback(bundle)
    if not teaching_recommendations:
        teaching_recommendations.append("先基于当前问卷结果做一次针对性复盘，并补充下一轮验证题。")

    return {
        "executive_summary": _fallback_executive_summary(bundle, key_signals),
        "key_signals": key_signals,
        "group_differences": group_differences,
        "teaching_recommendations": _dedupe_strings(teaching_recommendations),
        "confidence_and_gaps": {
            "confidence": float(bundle.parse_confidence),
            "gaps": list(bundle.missing_fields or []),
        },
    }



def _normalize_key_signals(value: Any, fallback: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return fallback
    items: List[Dict[str, Any]] = []
    for index, raw in enumerate(value):
        if isinstance(raw, str):
            items.append({"title": raw, "detail": raw, "evidence_refs": []})
            continue
        if not isinstance(raw, dict):
            continue
        fallback_refs = []
        if index < len(fallback):
            fallback_refs = [str(ref) for ref in fallback[index].get("evidence_refs") or [] if str(ref).strip()]
        evidence_refs = [str(ref) for ref in raw.get("evidence_refs") or [] if str(ref).strip()]
        items.append(
            {
                "title": str(raw.get("title") or raw.get("signal") or raw.get("summary") or "").strip(),
                "detail": str(raw.get("detail") or raw.get("summary") or raw.get("title") or "").strip(),
                "evidence_refs": evidence_refs or fallback_refs,
            }
        )
    return [item for item in items if item["title"] or item["detail"]] or fallback



def _normalize_group_differences(value: Any, fallback: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return fallback
    items: List[Dict[str, Any]] = []
    for raw in value:
        if isinstance(raw, str):
            items.append({"group_name": "班级差异", "summary": raw})
            continue
        if not isinstance(raw, dict):
            continue
        items.append(
            {
                "group_name": str(raw.get("group_name") or raw.get("group") or "班级差异").strip() or "班级差异",
                "summary": str(raw.get("summary") or raw.get("detail") or "").strip(),
            }
        )
    return [item for item in items if item["summary"]] or fallback



def _normalize_recommendations(value: Any, fallback: List[str]) -> List[str]:
    if not isinstance(value, list):
        return fallback
    items = [str(item or "").strip() for item in value if str(item or "").strip()]
    return items or fallback



def _normalize_artifact(parsed: Dict[str, Any], fallback: Dict[str, Any]) -> Dict[str, Any]:
    for key in list(parsed.keys()):
        if key in _DISALLOWED_OUTPUT_KEYS:
            parsed.pop(key, None)

    raw_confidence_and_gaps = parsed.get("confidence_and_gaps")
    confidence_and_gaps: Dict[str, Any] = raw_confidence_and_gaps if isinstance(raw_confidence_and_gaps, dict) else {}
    confidence = _safe_float(confidence_and_gaps.get("confidence"))
    if confidence is None:
        confidence = _safe_float((fallback.get("confidence_and_gaps") or {}).get("confidence"))
    gaps = _dedupe_strings(
        [str(item) for item in (confidence_and_gaps.get("gaps") or []) if str(item or "").strip()]
        + [str(item) for item in ((fallback.get("confidence_and_gaps") or {}).get("gaps") or []) if str(item or "").strip()]
    )

    artifact = {
        "executive_summary": str(parsed.get("executive_summary") or fallback.get("executive_summary") or "").strip()
        or str(fallback.get("executive_summary") or "").strip(),
        "key_signals": _normalize_key_signals(parsed.get("key_signals"), list(fallback.get("key_signals") or [])),
        "group_differences": _normalize_group_differences(
            parsed.get("group_differences"),
            list(fallback.get("group_differences") or []),
        ),
        "teaching_recommendations": _normalize_recommendations(
            parsed.get("teaching_recommendations"),
            list(fallback.get("teaching_recommendations") or []),
        ),
        "confidence_and_gaps": {
            "confidence": float(confidence or 0.0),
            "gaps": gaps,
        },
    }
    return artifact



def run_survey_analyst(
    *,
    handoff: HandoffContract,
    survey_evidence_bundle: SurveyEvidenceBundle | Dict[str, Any],
    teacher_context: Dict[str, Any],
    task_goal: str,
    deps: SurveyAnalystDeps,
) -> SpecialistAgentResult:
    request = HandoffContract.model_validate(handoff)
    bundle = _to_bundle(survey_evidence_bundle)
    fallback_artifact = _fallback_artifact(bundle)
    artifact = dict(fallback_artifact)

    try:
        prompt = deps.prompt_loader()
        resp = deps.call_llm(
            [
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "task_goal": str(task_goal or request.goal),
                            "teacher_context": teacher_context,
                            "survey_evidence_bundle": bundle.model_dump(),
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            role_hint="teacher",
            kind="survey.analysis",
            max_tokens=int(request.budget.max_tokens or 1600),
        )
        content = resp.get("choices", [{}])[0].get("message", {}).get("content", "")
        parsed = parse_llm_json(content)
        if isinstance(parsed, dict):
            artifact = _normalize_artifact(parsed, fallback_artifact)
        else:
            deps.diag_log("survey.analyst.fallback", {"reason": "parse_failed"})
    except Exception as exc:
        deps.diag_log("survey.analyst.error", {"error": str(exc)[:200]})

    confidence = _safe_float((artifact.get("confidence_and_gaps") or {}).get("confidence")) or float(bundle.parse_confidence)
    return SpecialistAgentResult(
        handoff_id=request.handoff_id,
        agent_id=request.to_agent,
        status="completed",
        output=artifact,
        confidence=confidence,
        artifacts=[ArtifactRef(artifact_id=f"{request.handoff_id}:analysis", artifact_type="analysis_artifact")],
    )
