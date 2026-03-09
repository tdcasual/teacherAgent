from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .analysis_report_models import (
    AnalysisReportDetail,
    AnalysisReportSummary,
    AnalysisReviewQueueDomainSummary,
    AnalysisReviewQueueItemSummary,
    AnalysisReviewQueueSummary,
)
from .class_report_service import (
    ClassReportServiceError,
    build_class_report_deps,
    get_class_report,
    list_class_report_review_queue,
    list_class_reports,
    rerun_class_report,
)
from .domains.binding_resolver import resolve_manifest_binding
from .domains.manifest_registry import (
    DomainManifestRegistry,
    build_default_domain_manifest_registry,
)
from .multimodal_report_service import (
    MultimodalReportServiceError,
    build_multimodal_report_deps,
    get_multimodal_report,
    list_multimodal_reports,
    list_multimodal_review_queue,
    rerun_multimodal_report,
)
from .review_queue_service import (
    ReviewQueueDeps,
    dismiss_review_item,
    escalate_review_item,
    reject_review_item,
    resolve_review_item,
    retry_review_item,
)
from .strategies.planner import build_replay_request
from .survey_report_service import (
    SurveyReportServiceError,
    build_survey_report_deps,
    get_survey_report,
    list_survey_reports,
    list_survey_review_queue,
    rerun_survey_report,
)

_OPEN_REVIEW_STATUSES = {'queued', 'claimed', 'escalated', 'retry_requested'}


class AnalysisReportServiceError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = int(status_code)
        self.detail = str(detail)


@dataclass(frozen=True)
class AnalysisReportProvider:
    domain: str
    default_strategy_id: str
    now_iso: Callable[[], str]
    list_reports: Callable[[str, Optional[str]], Dict[str, Any]]
    get_report: Callable[[str, str], Dict[str, Any]]
    rerun_report: Callable[[str, str, Optional[str]], Dict[str, Any]]
    list_review_queue: Callable[[str], Dict[str, Any]]
    operate_review_queue_item: Callable[[str, str, str, Optional[str]], Dict[str, Any]]




def build_survey_analysis_report_provider(core: Any | None = None) -> AnalysisReportProvider:
    survey_deps = build_survey_report_deps(core)

    def list_reports(teacher_id: str, status: str | None = None) -> Dict[str, Any]:
        return list_survey_reports(teacher_id=teacher_id, status=status, deps=survey_deps)

    def get_report(report_id: str, teacher_id: str) -> Dict[str, Any]:
        return get_survey_report(report_id=report_id, teacher_id=teacher_id, deps=survey_deps)

    def rerun_report(report_id: str, teacher_id: str, reason: str | None = None) -> Dict[str, Any]:
        return rerun_survey_report(
            report_id=report_id,
            teacher_id=teacher_id,
            reason=reason,
            deps=survey_deps,
        )

    def list_review_queue(teacher_id: str) -> Dict[str, Any]:
        return list_survey_review_queue(teacher_id=teacher_id, deps=survey_deps)

    def operate_review_queue_item(
        item_id: str,
        action: str,
        reviewer_id: str,
        operator_note: str | None = None,
    ) -> Dict[str, Any]:
        return _operate_review_queue_item_with_deps(
            item_id=item_id,
            action=action,
            reviewer_id=reviewer_id,
            operator_note=operator_note,
            queue_deps=survey_deps.review_queue_deps,
        )

    return AnalysisReportProvider(
        domain='survey',
        default_strategy_id='survey.teacher.report',
        now_iso=survey_deps.now_iso,
        list_reports=list_reports,
        get_report=get_report,
        rerun_report=rerun_report,
        list_review_queue=list_review_queue,
        operate_review_queue_item=operate_review_queue_item,
    )


def build_class_report_analysis_report_provider(core: Any | None = None) -> AnalysisReportProvider:
    class_report_deps = build_class_report_deps(core)

    def list_reports(teacher_id: str, status: str | None = None) -> Dict[str, Any]:
        return list_class_reports(teacher_id=teacher_id, status=status, deps=class_report_deps)

    def get_report(report_id: str, teacher_id: str) -> Dict[str, Any]:
        return get_class_report(report_id=report_id, teacher_id=teacher_id, deps=class_report_deps)

    def rerun_report(report_id: str, teacher_id: str, reason: str | None = None) -> Dict[str, Any]:
        return rerun_class_report(
            report_id=report_id,
            teacher_id=teacher_id,
            reason=reason,
            deps=class_report_deps,
        )

    def list_review_queue(teacher_id: str) -> Dict[str, Any]:
        return list_class_report_review_queue(teacher_id=teacher_id, deps=class_report_deps)

    def operate_review_queue_item(
        item_id: str,
        action: str,
        reviewer_id: str,
        operator_note: str | None = None,
    ) -> Dict[str, Any]:
        return _operate_review_queue_item_with_deps(
            item_id=item_id,
            action=action,
            reviewer_id=reviewer_id,
            operator_note=operator_note,
            queue_deps=class_report_deps.review_queue_deps,
        )

    return AnalysisReportProvider(
        domain='class_report',
        default_strategy_id='class_signal.teacher.report',
        now_iso=class_report_deps.now_iso,
        list_reports=list_reports,
        get_report=get_report,
        rerun_report=rerun_report,
        list_review_queue=list_review_queue,
        operate_review_queue_item=operate_review_queue_item,
    )


def build_video_homework_analysis_report_provider(core: Any | None = None) -> AnalysisReportProvider:
    multimodal_deps = build_multimodal_report_deps(core)

    def list_reports(teacher_id: str, status: str | None = None) -> Dict[str, Any]:
        return list_multimodal_reports(
            teacher_id=teacher_id,
            status=status,
            deps=multimodal_deps,
        )

    def get_report(report_id: str, teacher_id: str) -> Dict[str, Any]:
        return get_multimodal_report(
            report_id=report_id,
            teacher_id=teacher_id,
            deps=multimodal_deps,
        )

    def rerun_report(report_id: str, teacher_id: str, reason: str | None = None) -> Dict[str, Any]:
        return rerun_multimodal_report(
            report_id=report_id,
            teacher_id=teacher_id,
            reason=reason,
            deps=multimodal_deps,
        )

    def list_review_queue(teacher_id: str) -> Dict[str, Any]:
        return list_multimodal_review_queue(teacher_id=teacher_id, deps=multimodal_deps)

    def operate_review_queue_item(
        item_id: str,
        action: str,
        reviewer_id: str,
        operator_note: str | None = None,
    ) -> Dict[str, Any]:
        return _operate_review_queue_item_with_deps(
            item_id=item_id,
            action=action,
            reviewer_id=reviewer_id,
            operator_note=operator_note,
            queue_deps=multimodal_deps.review_queue_deps,
        )

    return AnalysisReportProvider(
        domain='video_homework',
        default_strategy_id='video_homework.teacher.report',
        now_iso=multimodal_deps.now_iso,
        list_reports=list_reports,
        get_report=get_report,
        rerun_report=rerun_report,
        list_review_queue=list_review_queue,
        operate_review_queue_item=operate_review_queue_item,
    )


_REPORT_PROVIDER_FACTORY_LOOKUP = {
    'build_class_report_analysis_report_provider': build_class_report_analysis_report_provider,
    'build_survey_analysis_report_provider': build_survey_analysis_report_provider,
    'build_video_homework_analysis_report_provider': build_video_homework_analysis_report_provider,
}


@dataclass(frozen=True)
class AnalysisReportDeps:
    providers: Dict[str, AnalysisReportProvider]
    now_iso: Callable[[], str]
    list_review_queue: Callable[[str, Optional[str], Optional[str]], Dict[str, Any]]



def build_analysis_report_deps(
    core: Any | None = None,
    *,
    manifest_registry: DomainManifestRegistry | None = None,
) -> AnalysisReportDeps:
    manifest_registry = manifest_registry or build_default_domain_manifest_registry()
    providers: Dict[str, AnalysisReportProvider] = {}
    for manifest in manifest_registry.list():
        report_binding = manifest.report_binding
        if report_binding is None:
            raise ValueError(f'invalid report binding for domain {manifest.domain_id}')
        provider_factory = resolve_manifest_binding(
            report_binding.provider_factory,
            lookup=_REPORT_PROVIDER_FACTORY_LOOKUP,
            domain_id=manifest.domain_id,
            label='report binding',
        )
        provider = provider_factory(core)
        providers[provider.domain] = provider

    def default_now_iso() -> str:
        return datetime.now().isoformat(timespec='seconds')

    now_iso = next(iter(providers.values())).now_iso if providers else default_now_iso

    def list_review_queue(
        teacher_id: str,
        domain: str | None = None,
        status: str | None = None,
    ) -> Dict[str, Any]:
        return _list_review_queue_with_providers(
            teacher_id=teacher_id,
            domain=domain,
            status=status,
            providers=providers,
            now_iso=now_iso,
        )

    return AnalysisReportDeps(
        providers=providers,
        now_iso=now_iso,
        list_review_queue=list_review_queue,
    )



def list_analysis_reports(
    *,
    teacher_id: str,
    domain: str | None,
    status: str | None,
    strategy_id: str | None,
    target_type: str | None,
    deps: AnalysisReportDeps,
) -> Dict[str, Any]:
    review_queue = deps.list_review_queue(teacher_id, domain, 'queued')
    open_review_ids = {str(item.get('report_id') or '').strip() for item in review_queue.get('items') or [] if str(item.get('report_id') or '').strip()}
    items: List[Dict[str, Any]] = []
    for provider in _iter_providers(deps.providers, domain):
        payload = provider.list_reports(teacher_id, status)
        for raw in payload.get('items') or []:
            summary = _to_analysis_summary(provider, raw, report_id_hint=str(raw.get('report_id') or ''))
            if strategy_id and summary.strategy_id != strategy_id:
                continue
            if target_type and summary.target_type != target_type:
                continue
            summary.review_required = summary.report_id in open_review_ids
            items.append(summary.model_dump())
    items.sort(key=lambda item: (str(item.get('updated_at') or ''), str(item.get('created_at') or ''), str(item.get('report_id') or '')), reverse=True)
    return {'items': items}



def get_analysis_report(*, report_id: str, teacher_id: str, domain: str | None, deps: AnalysisReportDeps) -> Dict[str, Any]:
    provider = _resolve_provider(deps.providers, domain)
    try:
        detail = provider.get_report(report_id, teacher_id)
    except (SurveyReportServiceError, ClassReportServiceError, MultimodalReportServiceError) as exc:
        raise AnalysisReportServiceError(exc.status_code, exc.detail)
    review_queue = deps.list_review_queue(teacher_id, provider.domain, 'queued')
    report = _to_analysis_summary(provider, detail.get('report') or {}, report_id_hint=report_id)
    report.review_required = any(str(item.get('report_id') or '') == report.report_id for item in review_queue.get('items') or [])
    analysis_artifact = dict(detail.get('analysis_artifact') or {})
    artifact_meta = dict(detail.get('bundle_meta') or detail.get('artifact_meta') or {})
    replay_context = _build_replay_context(provider=provider, report=report.model_dump(), detail=detail, artifact_meta=artifact_meta, analysis_artifact=analysis_artifact)
    generic_detail = AnalysisReportDetail(
        report=report,
        analysis_artifact=analysis_artifact,
        artifact_meta=artifact_meta,
        replay_context=replay_context,
    )
    return generic_detail.model_dump()



def rerun_analysis_report(
    *,
    report_id: str,
    teacher_id: str,
    domain: str | None,
    reason: str | None,
    deps: AnalysisReportDeps,
) -> Dict[str, Any]:
    provider = _resolve_provider(deps.providers, domain)
    try:
        result = provider.rerun_report(report_id, teacher_id, reason)
    except (SurveyReportServiceError, ClassReportServiceError, MultimodalReportServiceError) as exc:
        raise AnalysisReportServiceError(exc.status_code, exc.detail)
    payload = dict(result or {})
    payload['domain'] = provider.domain
    return payload



def list_analysis_review_queue(
    *,
    teacher_id: str,
    domain: str | None,
    status: str | None,
    deps: AnalysisReportDeps,
) -> Dict[str, Any]:
    payload = deps.list_review_queue(teacher_id, domain, status)
    domain_final = str(domain or '').strip() or None
    status_final = str(status or '').strip() or None
    items = []
    for item in payload.get('items') or []:
        item_dict = dict(item)
        if domain_final and str(item_dict.get('domain') or '').strip() != domain_final:
            continue
        if status_final and not _matches_review_status(str(item_dict.get('status') or '').strip(), status_final):
            continue
        items.append(item_dict)
    return {
        'items': items,
        'summary': dict(payload.get('summary') or {}),
    }



def operate_analysis_review_queue_item(
    *,
    item_id: str,
    teacher_id: str,
    domain: str | None,
    action: str,
    reviewer_id: str | None,
    operator_note: str | None,
    deps: AnalysisReportDeps,
) -> Dict[str, Any]:
    teacher_id_final = str(teacher_id or '').strip()
    if not teacher_id_final:
        raise AnalysisReportServiceError(400, 'teacher_id_required')
    action_final = str(action or '').strip().lower()
    reviewer_id_final = str(reviewer_id or '').strip() or teacher_id_final
    operator_note_final = str(operator_note or '').strip() or None
    provider = _resolve_review_queue_provider(deps.providers, teacher_id=teacher_id_final, item_id=item_id, domain=domain)
    try:
        result = provider.operate_review_queue_item(item_id, action_final, reviewer_id_final, operator_note_final)
    except KeyError:
        raise AnalysisReportServiceError(404, 'review_queue_item_not_found')
    payload = dict(result or {})
    payload['domain'] = payload.get('domain') or provider.domain
    return payload



def _iter_providers(providers: Dict[str, AnalysisReportProvider], domain: str | None) -> List[AnalysisReportProvider]:
    domain_final = str(domain or '').strip()
    if domain_final:
        return [_resolve_provider(providers, domain_final)]
    return [providers[key] for key in sorted(providers.keys())]



def _resolve_provider(providers: Dict[str, AnalysisReportProvider], domain: str | None) -> AnalysisReportProvider:
    domain_final = str(domain or '').strip() or 'survey'
    provider = providers.get(domain_final)
    if provider is None:
        raise AnalysisReportServiceError(404, 'analysis_domain_not_found')
    return provider



def _resolve_review_queue_provider(
    providers: Dict[str, AnalysisReportProvider],
    *,
    teacher_id: str,
    item_id: str,
    domain: str | None,
) -> AnalysisReportProvider:
    item_id_final = str(item_id or '').strip()
    for provider in _iter_providers(providers, domain):
        payload = provider.list_review_queue(teacher_id)
        for raw in payload.get('items') or []:
            if str(raw.get('item_id') or '').strip() == item_id_final:
                return provider
    raise AnalysisReportServiceError(404, 'review_queue_item_not_found')



def _to_analysis_summary(provider: AnalysisReportProvider, raw: Dict[str, Any], *, report_id_hint: str) -> AnalysisReportSummary:
    report_id = str(raw.get('report_id') or report_id_hint or '').strip()
    domain = provider.domain
    default_strategy_id = str(provider.default_strategy_id or '').strip() or 'survey.teacher.report'
    return AnalysisReportSummary(
        report_id=report_id,
        analysis_type=str(raw.get('analysis_type') or domain).strip() or domain,
        target_type=str(raw.get('target_type') or 'report').strip() or 'report',
        target_id=str(raw.get('target_id') or report_id).strip() or report_id,
        strategy_id=str(raw.get('strategy_id') or default_strategy_id).strip() or default_strategy_id,
        strategy_version=str(raw.get('strategy_version') or 'v1').strip() or 'v1',
        prompt_version=str(raw.get('prompt_version') or 'v1').strip() or 'v1',
        adapter_version=str(raw.get('adapter_version') or 'v1').strip() or 'v1',
        runtime_version=str(raw.get('runtime_version') or 'v1').strip() or 'v1',
        teacher_id=str(raw.get('teacher_id') or '').strip(),
        status=str(raw.get('status') or 'unknown').strip() or 'unknown',
        confidence=_safe_float(raw.get('confidence')),
        summary=str(raw.get('summary') or '').strip() or None,
        review_required=bool(raw.get('review_required')),
        created_at=str(raw.get('created_at') or '').strip() or None,
        updated_at=str(raw.get('updated_at') or '').strip() or None,
    )



def _build_replay_context(
    *,
    provider: AnalysisReportProvider,
    report: Dict[str, Any],
    detail: Dict[str, Any],
    artifact_meta: Dict[str, Any],
    analysis_artifact: Dict[str, Any],
) -> Dict[str, Any]:
    artifact_payload = dict(detail.get('replay_artifact') or {})
    if not artifact_payload:
        return {}
    try:
        return build_replay_request(
            domain=provider.domain,
            report=report,
            artifact_payload=artifact_payload,
            artifact_meta=artifact_meta,
            analysis_artifact=analysis_artifact,
        )
    except ValueError:
        return {}



def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None



def _to_analysis_review_queue_item(provider: AnalysisReportProvider, raw: Dict[str, Any], *, index: int) -> AnalysisReviewQueueItemSummary:
    return AnalysisReviewQueueItemSummary(
        item_id=str(raw.get('item_id') or raw.get('report_id') or f'{provider.domain}_{index + 1}').strip() or f'{provider.domain}_{index + 1}',
        domain=provider.domain,
        report_id=str(raw.get('report_id') or '').strip(),
        teacher_id=str(raw.get('teacher_id') or '').strip(),
        strategy_id=str(raw.get('strategy_id') or provider.default_strategy_id).strip() or provider.default_strategy_id,
        status=str(raw.get('status') or 'queued').strip() or 'queued',
        reason=str(raw.get('reason') or '').strip(),
        reason_code=str(raw.get('reason_code') or '').strip() or None,
        disposition=str(raw.get('disposition') or '').strip() or None,
        reviewer_id=str(raw.get('reviewer_id') or '').strip() or None,
        operator_note=str(raw.get('operator_note') or raw.get('resolution_note') or '').strip() or None,
        confidence=_safe_float(raw.get('confidence')),
        created_at=str(raw.get('created_at') or '').strip() or None,
        updated_at=str(raw.get('updated_at') or '').strip() or None,
        claimed_at=str(raw.get('claimed_at') or '').strip() or None,
        resolved_at=str(raw.get('resolved_at') or '').strip() or None,
        rejected_at=str(raw.get('rejected_at') or '').strip() or None,
        dismissed_at=str(raw.get('dismissed_at') or '').strip() or None,
        escalated_at=str(raw.get('escalated_at') or '').strip() or None,
        retried_at=str(raw.get('retried_at') or '').strip() or None,
    )



def _matches_review_status(item_status: str, requested_status: Optional[str]) -> bool:
    if not requested_status:
        return True
    if requested_status == 'unresolved':
        return str(item_status or '').strip() in _OPEN_REVIEW_STATUSES
    return str(item_status or '').strip() == requested_status



def _list_review_queue_with_providers(
    *,
    teacher_id: str,
    domain: str | None,
    status: str | None,
    providers: Dict[str, AnalysisReportProvider],
    now_iso: Callable[[], str],
) -> Dict[str, Any]:
    normalized_status = str(status or '').strip() or None
    all_items: List[AnalysisReviewQueueItemSummary] = []
    for provider in _iter_providers(providers, domain):
        payload = provider.list_review_queue(teacher_id)
        for index, raw in enumerate(payload.get('items') or []):
            all_items.append(_to_analysis_review_queue_item(provider, raw, index=index))
    filtered_items = [
        item.model_dump(exclude_none=True)
        for item in all_items
        if _matches_review_status(item.status, normalized_status)
    ]
    return {
        'items': filtered_items,
        'summary': _build_analysis_review_summary(all_items, generated_at=now_iso()).model_dump(exclude_none=True),
    }



def _build_analysis_review_summary(
    items: List[AnalysisReviewQueueItemSummary],
    *,
    generated_at: str,
) -> AnalysisReviewQueueSummary:
    status_counts: Dict[str, int] = {}
    reason_counts: Dict[str, int] = {}
    domains: Dict[str, AnalysisReviewQueueDomainSummary] = {}
    unresolved_items = 0
    for item in items:
        status_counts[item.status] = status_counts.get(item.status, 0) + 1
        reason_code = str(item.reason_code or 'unknown').strip() or 'unknown'
        reason_counts[reason_code] = reason_counts.get(reason_code, 0) + 1
        domain_summary = domains.get(item.domain)
        if domain_summary is None:
            domain_summary = AnalysisReviewQueueDomainSummary(domain=item.domain)
            domains[item.domain] = domain_summary
        domain_summary.total_items += 1
        domain_summary.status_counts[item.status] = domain_summary.status_counts.get(item.status, 0) + 1
        domain_summary.reason_counts[reason_code] = domain_summary.reason_counts.get(reason_code, 0) + 1
        if item.status in _OPEN_REVIEW_STATUSES:
            unresolved_items += 1
            domain_summary.unresolved_items += 1
    return AnalysisReviewQueueSummary(
        total_items=len(items),
        unresolved_items=unresolved_items,
        status_counts=status_counts,
        reason_counts=reason_counts,
        domains=[domains[key] for key in sorted(domains.keys())],
        generated_at=str(generated_at or '').strip() or None,
    )



def _operate_review_queue_item_with_deps(
    *,
    item_id: str,
    action: str,
    reviewer_id: str,
    operator_note: Optional[str],
    queue_deps: ReviewQueueDeps,
) -> Dict[str, Any]:
    if action == 'resolve':
        return resolve_review_item(item_id=item_id, reviewer_id=reviewer_id, resolution_note=operator_note or '', deps=queue_deps)
    if action == 'reject':
        return reject_review_item(item_id=item_id, reviewer_id=reviewer_id, resolution_note=operator_note or '', deps=queue_deps)
    if action == 'dismiss':
        return dismiss_review_item(item_id=item_id, reviewer_id=reviewer_id, operator_note=operator_note or '', deps=queue_deps)
    if action == 'escalate':
        return escalate_review_item(item_id=item_id, reviewer_id=reviewer_id, operator_note=operator_note or '', deps=queue_deps)
    if action == 'retry':
        return retry_review_item(item_id=item_id, reviewer_id=reviewer_id, operator_note=operator_note or '', deps=queue_deps)
    raise AnalysisReportServiceError(400, 'review_queue_action_not_supported')
