from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..class_signal_bundle_models import (
    ClassSignalBundle,
    ClassSignalQuestionLike,
    ClassSignalRiskLike,
    ClassSignalScope,
    ClassSignalSourceMeta,
    ClassSignalThemeLike,
)

_ADAPTER_ID = 'class_report.self_hosted_form.adapter'


def adapt_self_hosted_form_json(payload: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload_final = dict(payload or {})
    context_final = dict(context or {})
    teacher_id = str(payload_final.get('teacher_id') or '').strip()
    class_name = str(payload_final.get('class_name') or '').strip() or None
    sample_size = _safe_int(payload_final.get('sample_size'))
    report_id = str(payload_final.get('report_id') or payload_final.get('submission_id') or '').strip() or None
    title = str(payload_final.get('title') or payload_final.get('name') or '班级信号报告').strip() or '班级信号报告'

    question_like_signals = [
        ClassSignalQuestionLike(
            signal_id=str(item.get('id') or item.get('question_id') or f'question_{index + 1}').strip() or f'question_{index + 1}',
            title=str(item.get('prompt') or item.get('title') or item.get('label') or f'问题 {index + 1}').strip() or f'问题 {index + 1}',
            summary=str(item.get('summary') or item.get('insight') or '').strip() or None,
            stats=dict(item.get('stats') or {}),
            evidence_refs=_string_list(item.get('evidence_refs') or []),
        )
        for index, item in enumerate(payload_final.get('questions') or payload_final.get('question_summaries') or [])
        if isinstance(item, dict)
    ]
    theme_like_signals = [
        ClassSignalThemeLike(
            theme=str(item.get('theme') or item.get('title') or f'主题 {index + 1}').strip() or f'主题 {index + 1}',
            summary=str(item.get('summary') or item.get('detail') or '').strip() or None,
            evidence_count=int(_safe_int(item.get('evidence_count')) or 0),
            excerpts=_string_list(item.get('excerpts') or []),
            evidence_refs=_string_list(item.get('evidence_refs') or []),
        )
        for index, item in enumerate(payload_final.get('themes') or payload_final.get('theme_signals') or [])
        if isinstance(item, dict)
    ]
    risk_like_signals = [
        ClassSignalRiskLike(
            risk=str(item.get('risk') or item.get('title') or f'风险 {index + 1}').strip() or f'风险 {index + 1}',
            severity=str(item.get('severity') or '').strip() or None,
            summary=str(item.get('summary') or item.get('detail') or '').strip() or None,
            evidence_refs=_string_list(item.get('evidence_refs') or []),
        )
        for index, item in enumerate(payload_final.get('risks') or payload_final.get('risk_signals') or [])
        if isinstance(item, dict)
    ]
    narrative_blocks = _string_list([payload_final.get('summary'), payload_final.get('teacher_note')])
    attachments = _attachments_from_payload(payload_final, context_final, default_name='self-hosted-form.json', mime_type='application/json')
    missing_fields = _missing_fields(question_like_signals, theme_like_signals, risk_like_signals, narrative_blocks)
    provenance = {
        'adapter_id': _ADAPTER_ID,
        'source_uri': str(context_final.get('source_uri') or '').strip() or None,
        'provider': 'self_hosted_form',
    }

    bundle = ClassSignalBundle(
        source_meta=ClassSignalSourceMeta(
            title=title,
            provider='self_hosted_form',
            source_type='self_hosted_form_json',
            report_id=report_id,
        ),
        class_scope=ClassSignalScope(
            teacher_id=teacher_id or None,
            class_name=class_name,
            sample_size=sample_size,
        ),
        question_like_signals=question_like_signals,
        theme_like_signals=theme_like_signals,
        risk_like_signals=risk_like_signals,
        narrative_blocks=narrative_blocks,
        attachments=attachments,
        parse_confidence=float(payload_final.get('parse_confidence') or 0.92),
        missing_fields=missing_fields,
        provenance={key: value for key, value in provenance.items() if value is not None},
    )
    return bundle.to_artifact_envelope()



def _attachments_from_payload(payload: Dict[str, Any], context: Dict[str, Any], *, default_name: str, mime_type: str) -> List[Dict[str, Any]]:
    attachments = [dict(item) for item in (payload.get('attachments') or []) if isinstance(item, dict)]
    source_uri = str(context.get('source_uri') or payload.get('source_uri') or '').strip()
    if source_uri:
        attachments.append(
            {
                'name': default_name,
                'kind': 'source',
                'uri': source_uri,
                'mime_type': mime_type,
            }
        )
    return attachments



def _missing_fields(
    question_like_signals: List[ClassSignalQuestionLike],
    theme_like_signals: List[ClassSignalThemeLike],
    risk_like_signals: List[ClassSignalRiskLike],
    narrative_blocks: List[str],
) -> List[str]:
    missing: List[str] = []
    if not question_like_signals:
        missing.append('question_like_signals')
    if not theme_like_signals:
        missing.append('theme_like_signals')
    if not risk_like_signals:
        missing.append('risk_like_signals')
    if not narrative_blocks:
        missing.append('narrative_blocks')
    return missing



def _string_list(value: Any) -> List[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]



def _safe_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None
