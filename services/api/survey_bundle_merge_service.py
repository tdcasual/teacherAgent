from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List

from .survey_bundle_models import (
    SurveyAudienceScope,
    SurveyEvidenceBundle,
    SurveyFreeTextSignal,
    SurveyGroupBreakdown,
    SurveyMeta,
    SurveyQuestionSummary,
)



def _to_bundle(value: SurveyEvidenceBundle | Dict[str, Any]) -> SurveyEvidenceBundle:
    if isinstance(value, SurveyEvidenceBundle):
        return value
    return SurveyEvidenceBundle.model_validate(value)



def _pick(primary: Any, secondary: Any) -> Any:
    if primary is None:
        return secondary
    if isinstance(primary, str) and not primary.strip():
        return secondary
    if isinstance(primary, list) and not primary:
        return secondary
    return primary



def _dedupe_strings(values: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    result: List[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result



def _merge_question_summaries(
    structured_items: List[SurveyQuestionSummary],
    parsed_items: List[SurveyQuestionSummary],
) -> List[SurveyQuestionSummary]:
    merged: Dict[str, SurveyQuestionSummary] = {
        item.question_id: SurveyQuestionSummary(**item.model_dump()) for item in structured_items
    }
    for item in parsed_items:
        existing = merged.get(item.question_id)
        if existing is None:
            merged[item.question_id] = SurveyQuestionSummary(**item.model_dump())
            continue
        existing.prompt = existing.prompt or item.prompt
        existing.response_type = existing.response_type or item.response_type
        for key, value in item.stats.items():
            existing.stats.setdefault(key, value)
    return [merged[key] for key in sorted(merged.keys())]



def _merge_group_breakdowns(
    structured_items: List[SurveyGroupBreakdown],
    parsed_items: List[SurveyGroupBreakdown],
) -> List[SurveyGroupBreakdown]:
    merged: Dict[str, SurveyGroupBreakdown] = {
        item.group_name: SurveyGroupBreakdown(**item.model_dump()) for item in structured_items
    }
    for item in parsed_items:
        existing = merged.get(item.group_name)
        if existing is None:
            merged[item.group_name] = SurveyGroupBreakdown(**item.model_dump())
            continue
        existing.sample_size = existing.sample_size or item.sample_size
        for key, value in item.stats.items():
            existing.stats.setdefault(key, value)
    return [merged[key] for key in sorted(merged.keys())]



def _merge_free_text_signals(
    structured_items: List[SurveyFreeTextSignal],
    parsed_items: List[SurveyFreeTextSignal],
) -> List[SurveyFreeTextSignal]:
    merged: Dict[str, SurveyFreeTextSignal] = {
        item.theme: SurveyFreeTextSignal(**item.model_dump()) for item in structured_items
    }
    for item in parsed_items:
        existing = merged.get(item.theme)
        if existing is None:
            merged[item.theme] = SurveyFreeTextSignal(**item.model_dump())
            continue
        existing.evidence_count = max(int(existing.evidence_count or 0), int(item.evidence_count or 0))
        existing.excerpts = _dedupe_strings([*existing.excerpts, *item.excerpts])
    return [merged[key] for key in sorted(merged.keys())]



def _merge_attachments(structured_items: List[Dict[str, Any]], parsed_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for item in [*structured_items, *parsed_items]:
        key = json.dumps(item, ensure_ascii=False, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        merged.append(dict(item))
    return merged



def merge_survey_evidence_bundles(
    *,
    structured_bundle: SurveyEvidenceBundle | Dict[str, Any],
    parsed_bundle: SurveyEvidenceBundle | Dict[str, Any],
) -> SurveyEvidenceBundle:
    structured = _to_bundle(structured_bundle)
    parsed = _to_bundle(parsed_bundle)

    return SurveyEvidenceBundle(
        survey_meta=SurveyMeta(
            title=_pick(structured.survey_meta.title, parsed.survey_meta.title),
            provider=_pick(structured.survey_meta.provider, parsed.survey_meta.provider),
            submission_id=_pick(structured.survey_meta.submission_id, parsed.survey_meta.submission_id),
        ),
        audience_scope=SurveyAudienceScope(
            teacher_id=_pick(structured.audience_scope.teacher_id, parsed.audience_scope.teacher_id),
            class_name=_pick(structured.audience_scope.class_name, parsed.audience_scope.class_name),
            sample_size=_pick(structured.audience_scope.sample_size, parsed.audience_scope.sample_size),
        ),
        question_summaries=_merge_question_summaries(structured.question_summaries, parsed.question_summaries),
        group_breakdowns=_merge_group_breakdowns(structured.group_breakdowns, parsed.group_breakdowns),
        free_text_signals=_merge_free_text_signals(structured.free_text_signals, parsed.free_text_signals),
        attachments=_merge_attachments(structured.attachments, parsed.attachments),
        parse_confidence=round(
            min(float(structured.parse_confidence or 0.0), float(parsed.parse_confidence or 0.0)),
            4,
        ),
        missing_fields=_dedupe_strings([*structured.missing_fields, *parsed.missing_fields]),
        provenance={
            "source": "merged",
            "provider": _pick(structured.survey_meta.provider, parsed.survey_meta.provider),
            "sources": [structured.provenance, parsed.provenance],
        },
    )
