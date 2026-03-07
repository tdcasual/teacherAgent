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
) -> Optional[Dict[str, str]]:
    for message in reversed(list(messages or [])):
        report_id = extract_report_id_from_text(message.get('content'))
        if report_id:
            return asdict(
                AnalysisTargetRef(
                    target_type=target_type,
                    target_id=report_id,
                    artifact_type=artifact_type,
                    teacher_id=str(teacher_id or '').strip(),
                    source_domain=str(source_domain or '').strip(),
                    resolution_reason='message_history',
                )
            )
    return None


def resolve_analysis_target(
    *,
    explicit_target_id: Optional[str],
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

    explicit_target_id_final = str(explicit_target_id or '').strip()
    if explicit_target_id_final:
        return AnalysisTargetRef(
            target_type=target_type_final,
            target_id=explicit_target_id_final,
            artifact_type=artifact_type_final,
            teacher_id=teacher_id_final,
            source_domain=source_domain_final,
            resolution_reason='explicit_target_id',
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
        )

    if len(candidate_ids) == 1:
        return AnalysisTargetRef(
            target_type=target_type_final,
            target_id=next(iter(candidate_ids)),
            artifact_type=artifact_type_final,
            teacher_id=teacher_id_final,
            source_domain=source_domain_final,
            resolution_reason='single_candidate',
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
    if target_type == 'report':
        keys.append('report_id')
    keys.append('id')
    for key in keys:
        value = str(candidate.get(key) or '').strip()
        if value:
            return value
    return ''
