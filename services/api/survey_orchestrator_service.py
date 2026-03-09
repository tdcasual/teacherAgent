from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List

from . import settings
from .analysis_specialist_failure_service import classify_specialist_failure
from .job_repository import load_survey_job, write_survey_job
from .specialist_agents.governor import SpecialistAgentRuntimeError
from .strategies.planner import build_handoff_plan, build_lineage_metadata
from .strategies.selector import StrategySelectionError, build_default_strategy_selector
from .survey.deps import build_survey_application_deps
from .survey_bundle_models import SurveyEvidenceBundle
from .survey_delivery_service import build_survey_delivery_deps, deliver_survey_report
from .survey_job_state_machine import is_terminal_survey_job_status, transition_survey_job_status
from .survey_repository import list_survey_raw_payloads, write_survey_bundle
from .survey_review_queue_service import build_survey_review_queue_deps, enqueue_survey_review_item
from .wiring.survey_wiring import build_survey_specialist_runtime


@dataclass(frozen=True)
class SurveyOrchestratorDeps:
    load_survey_job: Callable[[str], Dict[str, Any]]
    write_survey_job: Callable[[str, Dict[str, Any]], Dict[str, Any]]
    list_survey_raw_payloads: Callable[[str], List[Dict[str, Any]]]
    write_survey_bundle: Callable[[str, Dict[str, Any]], Any]
    normalize_structured_payload: Callable[..., SurveyEvidenceBundle]
    parse_report_payload: Callable[..., SurveyEvidenceBundle]
    merge_evidence_bundles: Callable[..., SurveyEvidenceBundle]
    specialist_runtime: Any
    deliver_survey_report: Callable[..., Dict[str, Any]]
    enqueue_survey_review_item: Callable[..., Dict[str, Any]]
    review_confidence_floor: Callable[[], float]
    domain_enabled: Callable[[], bool]
    domain_review_only: Callable[[], bool]
    diag_log: Callable[..., None]
    build_teacher_context: Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]



def build_survey_orchestrator_deps(core: Any | None = None) -> SurveyOrchestratorDeps:
    app_deps = build_survey_application_deps(core)
    delivery_deps = build_survey_delivery_deps(core)
    review_deps = build_survey_review_queue_deps(core)
    runtime = build_survey_specialist_runtime(core)
    diag_log = getattr(core, 'diag_log', lambda *_args, **_kwargs: None)
    return SurveyOrchestratorDeps(
        load_survey_job=lambda job_id: load_survey_job(job_id, core=core),
        write_survey_job=lambda job_id, updates: write_survey_job(job_id, updates, core=core),
        list_survey_raw_payloads=lambda job_id: list_survey_raw_payloads(job_id, core=core),
        write_survey_bundle=lambda job_id, payload: write_survey_bundle(job_id, payload, core=core),
        normalize_structured_payload=app_deps.normalize_structured_payload,
        parse_report_payload=app_deps.parse_report_payload,
        merge_evidence_bundles=app_deps.merge_evidence_bundles,
        specialist_runtime=runtime,
        deliver_survey_report=lambda **kwargs: deliver_survey_report(deps=delivery_deps, **kwargs),
        enqueue_survey_review_item=lambda **kwargs: enqueue_survey_review_item(deps=review_deps, **kwargs),
        review_confidence_floor=settings.survey_review_confidence_floor,
        domain_enabled=lambda: settings.analysis_domain_enabled('survey'),
        domain_review_only=lambda: settings.analysis_domain_review_only('survey'),
        diag_log=diag_log,
        build_teacher_context=lambda job, bundle: {
            'teacher_id': str(job.get('teacher_id') or '').strip(),
            'class_name': str(job.get('class_name') or '').strip(),
            'report_mode': 'teacher_report',
            'analysis_depth': 'survey_v1',
            'bundle_confidence': bundle.get('parse_confidence'),
        },
    )



def _transition_job(
    job_id: str,
    job: Dict[str, Any],
    target_status: str,
    deps: SurveyOrchestratorDeps,
    **updates: Any,
) -> Dict[str, Any]:
    status = transition_survey_job_status(job.get('status'), target_status)
    payload = dict(updates)
    payload['status'] = status
    return deps.write_survey_job(job_id, payload)



def _payload_has_unstructured_input(payload: Dict[str, Any]) -> bool:
    return any(key in payload and payload.get(key) for key in ('attachments', 'html', 'text', 'report_text'))



def _coerce_bundle(value: SurveyEvidenceBundle | Dict[str, Any]) -> SurveyEvidenceBundle:
    if isinstance(value, SurveyEvidenceBundle):
        return value
    return SurveyEvidenceBundle.model_validate(value)



def _review_queue_reason(strategy_reason: str) -> str:
    reason = str(strategy_reason or '').strip()
    if reason == 'low_confidence_review':
        return 'low_confidence_bundle'
    return reason or 'needs_review'




def _handle_specialist_runtime_failure(
    job_id: str,
    job: Dict[str, Any],
    bundle: SurveyEvidenceBundle,
    deps: SurveyOrchestratorDeps,
    *,
    exc: SpecialistAgentRuntimeError,
) -> Dict[str, Any]:
    decision = classify_specialist_failure(exc)
    deps.diag_log(
        'survey.orchestrator.specialist_failed',
        {'job_id': job_id, 'code': decision.reason, 'error': decision.error},
    )
    if decision.action != 'review':
        return _mark_job_failed(job_id, deps, error=decision.reason)
    confidence = float(bundle.parse_confidence) if bundle.parse_confidence is not None else None
    item = deps.enqueue_survey_review_item(job=job, reason=decision.reason, confidence=confidence)
    job = _transition_job(
        job_id,
        job,
        'review',
        deps,
        report_id=item['report_id'],
        review_reason=item['reason'],
        review_confidence=item.get('confidence'),
        error=decision.error,
    )
    return {'ok': True, 'job_id': job_id, 'status': job['status'], 'report_id': item['report_id']}


def _mark_job_failed(job_id: str, deps: SurveyOrchestratorDeps, *, error: str) -> Dict[str, Any]:
    job = deps.write_survey_job(job_id, {'status': 'failed', 'error': error})
    return {
        'ok': False,
        'job_id': job_id,
        'status': str(job.get('status') or 'failed'),
        'error': error,
    }



def process_survey_job(job_id: str, *, deps: SurveyOrchestratorDeps) -> Dict[str, Any]:
    job = deps.load_survey_job(job_id)
    if is_terminal_survey_job_status(job.get('status')):
        return {'ok': True, 'job_id': job_id, 'status': str(job.get('status') or '')}

    try:
        if not deps.domain_enabled():
            return _mark_job_failed(job_id, deps, error='analysis_domain_disabled')

        job = _transition_job(job_id, job, 'intake_validated', deps)
        raw_payloads = deps.list_survey_raw_payloads(job_id)
        payload = dict(raw_payloads[0]) if raw_payloads else {}
        provider = str(job.get('provider') or payload.get('provider') or 'provider').strip() or 'provider'

        structured_bundle = _coerce_bundle(deps.normalize_structured_payload(provider, payload))
        job = _transition_job(job_id, job, 'normalized', deps)

        bundle = structured_bundle
        if _payload_has_unstructured_input(payload):
            parsed_bundle = _coerce_bundle(deps.parse_report_payload(provider, payload))
            bundle = _coerce_bundle(
                deps.merge_evidence_bundles(
                    structured_bundle=structured_bundle,
                    parsed_bundle=parsed_bundle,
                )
            )

        deps.write_survey_bundle(job_id, bundle.model_dump())
        job = _transition_job(job_id, job, 'bundle_ready', deps, report_id=str(job.get('report_id') or job_id))

        teacher_context = deps.build_teacher_context(job, bundle.model_dump())
        artifact = bundle.to_artifact_envelope()
        try:
            strategy = build_default_strategy_selector(float(deps.review_confidence_floor())).select(
                role='teacher',
                artifact=artifact,
                task_kind='survey.analysis',
                target_scope='class',
                force_review_only=deps.domain_review_only(),
            )
        except StrategySelectionError as exc:
            if exc.code == 'strategy_disabled':
                return _mark_job_failed(job_id, deps, error='analysis_strategy_disabled')
            raise

        job = deps.write_survey_job(
            job_id,
            {
                'strategy_id': strategy.strategy_id,
                **build_lineage_metadata(strategy=strategy, artifact=artifact),
            },
        )
        if strategy.review_required:
            confidence = float(bundle.parse_confidence) if bundle.parse_confidence is not None else None
            item = deps.enqueue_survey_review_item(
                job=job,
                reason=_review_queue_reason(strategy.reason),
                confidence=confidence,
            )
            job = _transition_job(
                job_id,
                job,
                'review',
                deps,
                report_id=item['report_id'],
                review_reason=item['reason'],
                review_confidence=item.get('confidence'),
            )
            return {'ok': True, 'job_id': job_id, 'status': job['status'], 'report_id': item['report_id']}

        plan = build_handoff_plan(
            strategy=strategy,
            artifact=artifact,
            artifact_id=job_id,
            handoff_id=f'survey-handoff-{job_id}',
            from_agent='coordinator',
            goal='输出班级问卷洞察和教学建议',
            extra_constraints={'teacher_context': teacher_context},
            fallback_policy='enqueue_review',
        )
        job = _transition_job(job_id, job, 'analysis_running', deps)
        result = deps.specialist_runtime.run(plan.handoff)
        job = _transition_job(job_id, job, 'analysis_ready', deps, analysis_confidence=result.confidence)
        report = deps.deliver_survey_report(
            job=job,
            bundle=bundle.model_dump(),
            analysis_artifact=result.output,
        )
        job = _transition_job(job_id, job, 'teacher_notified', deps, report_id=report['report_id'])
        return {'ok': True, 'job_id': job_id, 'report_id': report['report_id'], 'status': job['status']}
    except SpecialistAgentRuntimeError as exc:
        return _handle_specialist_runtime_failure(job_id, job, bundle, deps, exc=exc)
    except Exception as exc:
        deps.diag_log('survey.orchestrator.failed', {'job_id': job_id, 'error': str(exc)[:200]})
        deps.write_survey_job(job_id, {'status': 'failed', 'error': str(exc)[:200]})
        raise
