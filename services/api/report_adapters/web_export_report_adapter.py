from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..class_signal_bundle_models import (
    ClassSignalBundle,
    ClassSignalRiskLike,
    ClassSignalScope,
    ClassSignalSourceMeta,
    ClassSignalThemeLike,
)
from ..upload_text_service import extract_text_from_html, split_nonempty_lines


_ADAPTER_ID = 'class_report.web_export.adapter'


def adapt_web_export_html(payload: Dict[str, Any], context: Optional[Dict[str, Any]] = None):
    payload_final = dict(payload or {})
    context_final = dict(context or {})
    raw_html = str(payload_final.get('html') or '').strip()
    extracted_text = extract_text_from_html(raw_html)
    lines = split_nonempty_lines(extracted_text)
    teacher_id = str(payload_final.get('teacher_id') or '').strip()
    class_name = str(payload_final.get('class_name') or '').strip() or None
    report_id = str(payload_final.get('report_id') or '').strip() or None
    title = str(payload_final.get('title') or '网页导出报告').strip() or '网页导出报告'

    theme_like_signals = [
        ClassSignalThemeLike(theme=theme, summary=None, evidence_count=0, excerpts=[], evidence_refs=[f'theme:{theme}'])
        for theme in _extract_prefixed_values(lines, ('主题：', '主题:', 'Theme:'))
    ]
    risk_like_signals = [
        ClassSignalRiskLike(risk=risk, severity=None, summary=None, evidence_refs=[f'risk:{risk}'])
        for risk in _extract_prefixed_values(lines, ('风险：', '风险:', 'Risk:'))
    ]
    narrative_blocks = _extract_prefixed_values(lines, ('摘要：', '摘要:', 'Summary:'))
    recommendation_lines = _extract_prefixed_values(lines, ('建议：', '建议:', 'Recommendation:'))
    narrative_blocks.extend([item for item in recommendation_lines if item not in narrative_blocks])
    if not narrative_blocks and lines:
        narrative_blocks.append(lines[0])

    bundle = ClassSignalBundle(
        source_meta=ClassSignalSourceMeta(
            title=title,
            provider='web_export',
            source_type='web_export_html',
            report_id=report_id,
        ),
        class_scope=ClassSignalScope(
            teacher_id=teacher_id or None,
            class_name=class_name,
        ),
        question_like_signals=[],
        theme_like_signals=theme_like_signals,
        risk_like_signals=risk_like_signals,
        narrative_blocks=narrative_blocks,
        attachments=_source_attachment(context_final, payload_final, default_name='web-export-report.html', mime_type='text/html'),
        parse_confidence=float(payload_final.get('parse_confidence') or 0.74),
        missing_fields=_missing_fields(theme_like_signals, risk_like_signals, narrative_blocks),
        provenance={
            'adapter_id': _ADAPTER_ID,
            'source_uri': str(context_final.get('source_uri') or payload_final.get('source_uri') or '').strip() or None,
            'provider': 'web_export',
            'text_length': len(extracted_text),
        },
    )
    return bundle.to_artifact_envelope()



def _extract_prefixed_values(lines: List[str], prefixes: tuple[str, ...]) -> List[str]:
    values: List[str] = []
    for line in lines:
        stripped = str(line or '').strip()
        for prefix in prefixes:
            if stripped.startswith(prefix):
                value = stripped[len(prefix):].strip()
                if value and value not in values:
                    values.append(value)
    return values



def _missing_fields(
    theme_like_signals: List[ClassSignalThemeLike],
    risk_like_signals: List[ClassSignalRiskLike],
    narrative_blocks: List[str],
) -> List[str]:
    missing: List[str] = []
    if not theme_like_signals:
        missing.append('theme_like_signals')
    if not risk_like_signals:
        missing.append('risk_like_signals')
    if not narrative_blocks:
        missing.append('narrative_blocks')
    return missing



def _source_attachment(context: Dict[str, Any], payload: Dict[str, Any], *, default_name: str, mime_type: str) -> List[Dict[str, Any]]:
    source_uri = str(context.get('source_uri') or payload.get('source_uri') or '').strip()
    if not source_uri:
        return []
    return [
        {
            'name': default_name,
            'kind': 'source',
            'uri': source_uri,
            'mime_type': mime_type,
        }
    ]
