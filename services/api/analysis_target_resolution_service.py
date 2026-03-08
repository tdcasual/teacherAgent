from __future__ import annotations

import re
from dataclasses import asdict
from typing import Any, Dict, Iterable, Optional

from .analysis_target_models import AnalysisTargetRef

_REPORT_ID_RE = re.compile(r"(?<![0-9A-Za-z_-])(report_[0-9A-Za-z_-]+)(?![0-9A-Za-z_-])", re.IGNORECASE)
_STRUCTURED_TARGET_ID_RE = re.compile(
    r"\b(?:target_id|report_id)\s*[:=]\s*([0-9A-Za-z][0-9A-Za-z_.:-]*)",
    re.IGNORECASE,
)
_TYPE_SPECIFIC_TARGET_KEYS = {
    'report': ['report_id'],
    'submission': ['submission_id'],
    'class': ['class_id'],
}


class AnalysisTargetResolutionError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def extract_report_id_from_text(text: Any) -> Optional[str]:
    raw = str(text or '')
    structured_match = _STRUCTURED_TARGET_ID_RE.search(raw)
    if structured_match:
        return structured_match.group(1)
    report_match = _REPORT_ID_RE.search(raw)
    if not report_match:
        return None
    return report_match.group(1)


def build_recent_target_from_messages(
    messages: Iterable[Dict[str, Any]],
    *,
    teacher_id: str,
    source_domain: str,
    artifact_type: str,
    target_type: str = 'report',
) -> Optional[Dict[str, Any]]:
    target_type_final = str(target_type or '').strip() or 'report'
    for message in reversed(list(messages or [])):
        report_id = extract_report_id_from_text(message.get('content'))
        if report_id:
            return asdict(
                AnalysisTargetRef(
                    target_type=target_type_final,
                    target_id=report_id,
                    artifact_type=str(artifact_type or '').strip(),
                    teacher_id=str(teacher_id or '').strip(),
                    source_domain=str(source_domain or '').strip(),
                    resolution_reason='message_history',
                    report_id=report_id if target_type_final == 'report' else None,
                )
            )
    return None


def resolve_analysis_target(
    *,
    explicit_target: Optional[Any] = None,
    explicit_target_id: Optional[str] = None,
    target_type: str,
    artifact_type: str,
    teacher_id: str,
    source_domain: str,
    candidates: Iterable[Dict[str, Any]],
    session_recent_target: Optional[Dict[str, Any]] = None,
) -> AnalysisTargetRef:
    teacher_id_final = str(teacher_id or '').strip()
    source_domain_final = str(source_domain or '').strip()
    artifact_type_final = str(artifact_type or '').strip()
    target_type_final = str(target_type or '').strip() or 'report'
    candidate_items = [item for item in (candidates or []) if isinstance(item, dict)]
    candidate_ids = {
        candidate_id
        for candidate_id in (_extract_candidate_target_id(item, target_type_final) for item in candidate_items)
        if candidate_id
    }

    explicit_target_ref = _coerce_explicit_target(
        explicit_target,
        fallback_target_type=target_type_final,
        fallback_artifact_type=artifact_type_final,
        fallback_teacher_id=teacher_id_final,
        fallback_source_domain=source_domain_final,
    )
    if explicit_target_ref is not None:
        return explicit_target_ref

    explicit_target_id_final = str(explicit_target_id or '').strip()
    if explicit_target_id_final:
        return AnalysisTargetRef(
            target_type=target_type_final,
            target_id=explicit_target_id_final,
            artifact_type=artifact_type_final,
            teacher_id=teacher_id_final,
            source_domain=source_domain_final,
            resolution_reason='explicit_target_id',
            report_id=explicit_target_id_final if target_type_final == 'report' else None,
        )

    recent_target_id = _extract_recent_target_id(session_recent_target, candidate_ids)
    if recent_target_id:
        return AnalysisTargetRef(
            target_type=target_type_final,
            target_id=recent_target_id,
            artifact_type=artifact_type_final,
            teacher_id=teacher_id_final,
            source_domain=source_domain_final,
            resolution_reason='session_recent_target',
            report_id=recent_target_id if target_type_final == 'report' else None,
        )

    if len(candidate_ids) == 1:
        candidate_target_id = next(iter(candidate_ids))
        return AnalysisTargetRef(
            target_type=target_type_final,
            target_id=candidate_target_id,
            artifact_type=artifact_type_final,
            teacher_id=teacher_id_final,
            source_domain=source_domain_final,
            resolution_reason='single_candidate',
            report_id=candidate_target_id if target_type_final == 'report' else None,
        )

    if len(candidate_ids) > 1:
        raise AnalysisTargetResolutionError(
            'ambiguous_target',
            f'Multiple {target_type_final} candidates found for teacher {teacher_id_final or "unknown"}',
        )

    raise AnalysisTargetResolutionError(
        'target_not_found',
        f'No {target_type_final} target found for teacher {teacher_id_final or "unknown"}',
    )


def _coerce_explicit_target(
    explicit_target: Optional[Any],
    *,
    fallback_target_type: str,
    fallback_artifact_type: str,
    fallback_teacher_id: str,
    fallback_source_domain: str,
) -> Optional[AnalysisTargetRef]:
    raw = _coerce_target_payload(explicit_target)
    if raw is None:
        return None

    target_id = _first_non_empty(raw.get('target_id'), raw.get('report_id'))
    if not target_id:
        return None

    target_type = _first_non_empty(raw.get('target_type'), fallback_target_type, 'report')
    artifact_type = _first_non_empty(raw.get('artifact_type'), fallback_artifact_type)
    teacher_id = _first_non_empty(raw.get('teacher_id'), fallback_teacher_id)
    source_domain = _first_non_empty(raw.get('source_domain'), raw.get('domain'), fallback_source_domain)
    report_id = _first_non_empty(raw.get('report_id'), target_id if target_type == 'report' else '') or None
    strategy_id = _first_non_empty(raw.get('strategy_id')) or None

    return AnalysisTargetRef(
        target_type=target_type,
        target_id=target_id,
        artifact_type=artifact_type,
        teacher_id=teacher_id,
        source_domain=source_domain,
        resolution_reason='explicit_target',
        report_id=report_id,
        strategy_id=strategy_id,
    )


def _coerce_target_payload(explicit_target: Optional[Any]) -> Optional[Dict[str, Any]]:
    if explicit_target is None:
        return None
    if isinstance(explicit_target, dict):
        return dict(explicit_target)
    model_dump = getattr(explicit_target, 'model_dump', None)
    if callable(model_dump):
        dumped = model_dump(exclude_none=True)
        if isinstance(dumped, dict):
            return dumped
    values: Dict[str, Any] = {}
    for key in ('target_type', 'target_id', 'report_id', 'source_domain', 'domain', 'artifact_type', 'teacher_id', 'strategy_id'):
        value = getattr(explicit_target, key, None)
        if value is not None:
            values[key] = value
    return values or None


def _extract_recent_target_id(
    session_recent_target: Optional[Dict[str, Any]],
    candidate_ids: set[str],
) -> Optional[str]:
    if not isinstance(session_recent_target, dict):
        return None
    target_id = str(session_recent_target.get('target_id') or '').strip()
    if not target_id:
        return None
    if candidate_ids and target_id not in candidate_ids:
        return None
    return target_id


def _extract_candidate_target_id(candidate: Dict[str, Any], target_type: str) -> str:
    keys = ['target_id']
    keys.extend(_TYPE_SPECIFIC_TARGET_KEYS.get(target_type, []))
    if target_type != 'report':
        keys.append('report_id')
    keys.append('id')
    for key in keys:
        value = str(candidate.get(key) or '').strip()
        if value:
            return value
    return ''


def _first_non_empty(*values: Any) -> str:
    for value in values:
        normalized = str(value or '').strip()
        if normalized:
            return normalized
    return ''
