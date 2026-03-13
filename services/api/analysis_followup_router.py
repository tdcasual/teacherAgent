from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from .analysis_target_models import AnalysisTargetRef
from .analysis_target_resolution_service import (
    AnalysisTargetResolutionError,
    build_recent_target_from_messages,
    extract_report_id_from_text,
    resolve_analysis_target,
)
from .strategies.planner import build_handoff_plan
from .strategies.selector import build_default_strategy_selector
from .survey_bundle_models import SurveyEvidenceBundle

_GENERIC_AMBIGUOUS_REPLY = '当前有多个可分析的问卷报告，请先告诉我 report_id（例如 report_123），我再继续深入复盘。'
_LOW_CONFIDENCE_REPLY = '当前问卷证据置信度偏低，建议先进入复核队列，确认后我再继续深入复盘。'


def _wants_survey_followup(
    *,
    deps: Any,
    explicit_target: Optional[Dict[str, Any]],
    last_user_text: str,
) -> bool:
    wants_survey_followup = _is_survey_target(explicit_target) or _looks_like_survey_followup_request(last_user_text)
    if not wants_survey_followup:
        return False
    return getattr(deps, 'survey_specialist_runtime', None) is not None


def _ready_survey_report_items(deps: Any, teacher_id: str) -> List[Dict[str, Any]]:
    reports = deps.survey_list_reports(teacher_id, 'analysis_ready')
    items = reports.get('items') if isinstance(reports, dict) else []
    return items if isinstance(items, list) else []


def _resolve_survey_followup_target(
    *,
    explicit_target: Optional[Dict[str, Any]],
    last_user_text: str,
    messages: List[Dict[str, Any]],
    teacher_id: str,
    items: List[Dict[str, Any]],
) -> AnalysisTargetRef:
    return resolve_analysis_target(
        explicit_target=explicit_target if _is_survey_target(explicit_target) else None,
        explicit_target_id=None if _is_survey_target(explicit_target) else extract_report_id_from_text(last_user_text),
        target_type='report',
        artifact_type='survey_evidence_bundle',
        teacher_id=teacher_id,
        source_domain='survey',
        candidates=items,
        session_recent_target=build_recent_target_from_messages(
            messages[:-1] if messages else [],
            teacher_id=teacher_id,
            source_domain='survey',
            artifact_type='survey_evidence_bundle',
        ),
    )


def _find_survey_report_item(items: List[Dict[str, Any]], report_id: str) -> Dict[str, Any]:
    return next(
        (
            item
            for item in items
            if isinstance(item, dict)
            and str(item.get('report_id') or item.get('target_id') or '').strip() == report_id
        ),
        {},
    )


def _load_survey_followup_bundle(
    deps: Any,
    *,
    report_id: str,
    teacher_id: str,
) -> Optional[Dict[str, Any]]:
    detail = deps.survey_get_report(report_id, teacher_id)
    if not isinstance(detail, dict):
        return None
    raw_bundle_meta = detail.get('bundle_meta')
    bundle_meta: Dict[str, Any] = raw_bundle_meta if isinstance(raw_bundle_meta, dict) else {}
    job_id = str(bundle_meta.get('job_id') or report_id).strip()
    bundle = deps.load_survey_bundle(job_id) if job_id else {}
    if not isinstance(bundle, dict) or not bundle:
        return None
    return {
        'detail': detail,
        'job_id': job_id,
        'bundle': bundle,
    }


def _run_survey_followup_specialist(
    deps: Any,
    *,
    teacher_id: str,
    report_id: str,
    latest: Dict[str, Any],
    detail: Dict[str, Any],
    job_id: str,
    bundle: Dict[str, Any],
    resolution_reason: str,
    event_sink: Optional[Callable[[str, Dict[str, Any]], None]],
) -> Dict[str, Any]:
    artifact = SurveyEvidenceBundle.model_validate(bundle).to_artifact_envelope()
    strategy = build_default_strategy_selector().select(
        role='teacher',
        artifact=artifact,
        task_kind='survey.chat_followup',
        target_scope='class',
    )
    plan = build_handoff_plan(
        strategy=strategy,
        artifact=artifact,
        artifact_id=job_id,
        handoff_id=f'chat-survey-{report_id}',
        from_agent='coordinator',
        goal='输出班级问卷洞察和教学建议',
        extra_constraints={
            'teacher_context': {
                'teacher_id': teacher_id,
                'class_name': latest.get('class_name'),
                'report_mode': 'chat_followup',
                'analysis_depth': 'deeper',
            }
        },
        fallback_policy='ask_user_to_clarify',
    )
    if plan.review_required:
        return {'reply': _LOW_CONFIDENCE_REPLY}

    result = deps.survey_specialist_runtime.run(plan.handoff)
    if callable(event_sink):
        event_sink(
            'analysis.followup',
            {
                'domain': 'survey',
                'report_id': report_id,
                'agent_id': plan.handoff.to_agent,
                'resolution_reason': resolution_reason,
                'strategy_id': plan.strategy_id,
            },
        )
    return {'reply': _format_survey_followup_reply(detail.get('report') or latest, result.output)}


def maybe_route_analysis_followup(
    deps: Any,
    *,
    messages: List[Dict[str, Any]],
    last_user_text: str,
    teacher_id: Optional[str],
    analysis_target: Optional[Any] = None,
    event_sink: Optional[Callable[[str, Dict[str, Any]], None]] = None,
) -> Optional[Dict[str, Any]]:
    teacher_id_final = str(teacher_id or '').strip()
    if not teacher_id_final:
        return None

    explicit_target = _coerce_analysis_target(analysis_target)
    if not _wants_survey_followup(
        deps=deps,
        explicit_target=explicit_target,
        last_user_text=last_user_text,
    ):
        return None

    try:
        items = _ready_survey_report_items(deps, teacher_id_final)
        if not items:
            return None

        target = _resolve_survey_followup_target(
            explicit_target=explicit_target,
            last_user_text=last_user_text,
            messages=messages,
            teacher_id=teacher_id_final,
            items=items,
        )
        report_id = target.target_id
        latest = _find_survey_report_item(items, report_id)
        loaded = _load_survey_followup_bundle(
            deps,
            report_id=report_id,
            teacher_id=teacher_id_final,
        )
        if loaded is None:
            return None
        return _run_survey_followup_specialist(
            deps,
            teacher_id=teacher_id_final,
            report_id=report_id,
            latest=latest,
            detail=loaded['detail'],
            job_id=str(loaded['job_id']),
            bundle=loaded['bundle'],
            resolution_reason=target.resolution_reason,
            event_sink=event_sink,
        )
    except AnalysisTargetResolutionError as exc:
        if exc.code == 'ambiguous_target':
            return {'reply': _GENERIC_AMBIGUOUS_REPLY}
        deps.diag_log(
            'analysis.followup.target_resolution_failed',
            {'domain': 'survey', 'code': exc.code, 'error': str(exc)[:200]},
        )
        return None
    except Exception as exc:  # policy: allowed-broad-except
        deps.diag_log(
            'analysis.followup.failed',
            {'domain': 'survey', 'error': str(exc)[:200]},
        )
        return None


def _coerce_analysis_target(raw_target: Optional[Any]) -> Optional[Dict[str, Any]]:
    if raw_target is None:
        return None
    if isinstance(raw_target, dict):
        return dict(raw_target)
    model_dump = getattr(raw_target, 'model_dump', None)
    if callable(model_dump):
        dumped = model_dump(exclude_none=True)
        if isinstance(dumped, dict):
            return dumped
    values: Dict[str, Any] = {}
    for key in ('target_type', 'target_id', 'report_id', 'source_domain', 'artifact_type', 'strategy_id', 'teacher_id'):
        value = getattr(raw_target, key, None)
        if value is not None:
            values[key] = value
    return values or None


def _is_survey_target(target: Optional[Dict[str, Any]]) -> bool:
    if not isinstance(target, dict):
        return False
    domain = str(target.get('source_domain') or target.get('domain') or '').strip()
    artifact_type = str(target.get('artifact_type') or '').strip()
    return domain == 'survey' or artifact_type == 'survey_evidence_bundle'


def _looks_like_survey_followup_request(text: str) -> bool:
    content = str(text or '').strip()
    if not content:
        return False
    lowered = content.lower()
    if '问卷' not in content and 'survey' not in lowered:
        return False
    keywords = ('深入', '深挖', '复盘', '进一步', '教学建议', '洞察')
    return any(token in content for token in keywords)


def _format_survey_followup_reply(report: Dict[str, Any], artifact: Dict[str, Any]) -> str:
    summary = str(artifact.get('executive_summary') or report.get('summary') or '已完成问卷分析。').strip()
    recommendations = [
        str(item or '').strip()
        for item in (artifact.get('teaching_recommendations') or [])
        if str(item or '').strip()
    ]
    lines = [summary]
    if recommendations:
        lines.append('教学建议：')
        lines.extend(f'- {item}' for item in recommendations[:3])
    confidence = (artifact.get('confidence_and_gaps') or {}).get('confidence')
    if confidence is not None:
        lines.append(f'证据置信度：{confidence}')
    return '\n'.join(lines).strip()
