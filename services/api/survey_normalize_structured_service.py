from __future__ import annotations

from typing import Any, Dict, List

from .survey_bundle_models import (
    SurveyAudienceScope,
    SurveyEvidenceBundle,
    SurveyFreeTextSignal,
    SurveyGroupBreakdown,
    SurveyMeta,
    SurveyQuestionSummary,
)


def _missing_fields(payload: Dict[str, Any]) -> List[str]:
    required = ("title", "teacher_id", "class_name")
    return [name for name in required if not str(payload.get(name) or "").strip()]



def _confidence_for_missing(missing_fields: List[str]) -> float:
    penalty = 0.15 * len(missing_fields)
    return max(0.2, round(1.0 - penalty, 4))



def normalize_structured_survey_payload(*, provider: str, payload: Dict[str, Any]) -> SurveyEvidenceBundle:
    missing_fields = _missing_fields(payload)
    question_summaries = [
        SurveyQuestionSummary(
            question_id=str(item.get("id") or item.get("question_id") or f"Q{idx + 1}"),
            prompt=str(item.get("prompt") or "").strip() or None,
            response_type=str(item.get("response_type") or "").strip() or None,
            stats=dict(item.get("stats") or {}),
        )
        for idx, item in enumerate(payload.get("questions") or [])
        if isinstance(item, dict)
    ]
    group_breakdowns = [
        SurveyGroupBreakdown(
            group_name=str(item.get("group_name") or item.get("name") or "group").strip() or "group",
            sample_size=int(item.get("sample_size") or 0) or None,
            stats=dict(item.get("stats") or {}),
        )
        for item in (payload.get("groups") or [])
        if isinstance(item, dict)
    ]
    free_text_signals = [
        SurveyFreeTextSignal(
            theme=str(item.get("theme") or "未分类反馈").strip() or "未分类反馈",
            evidence_count=int(item.get("evidence_count") or 0),
            excerpts=[str(x) for x in (item.get("excerpts") or []) if str(x or "").strip()],
        )
        for item in (payload.get("text_signals") or [])
        if isinstance(item, dict)
    ]

    return SurveyEvidenceBundle(
        survey_meta=SurveyMeta(
            title=str(payload.get("title") or "").strip() or None,
            provider=str(provider or "structured").strip() or "structured",
            submission_id=str(payload.get("submission_id") or payload.get("report_id") or "").strip() or None,
        ),
        audience_scope=SurveyAudienceScope(
            teacher_id=str(payload.get("teacher_id") or "").strip() or None,
            class_name=str(payload.get("class_name") or "").strip() or None,
            sample_size=int(payload.get("sample_size") or 0) or None,
        ),
        question_summaries=question_summaries,
        group_breakdowns=group_breakdowns,
        free_text_signals=free_text_signals,
        attachments=list(payload.get("attachments") or []),
        parse_confidence=_confidence_for_missing(missing_fields),
        missing_fields=missing_fields,
        provenance={"source": "structured", "provider": provider},
    )
