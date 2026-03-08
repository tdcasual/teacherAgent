from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict

from . import settings
from .artifacts.registry import build_platform_artifact_registry
from .artifacts.runtime import ArtifactAdapterRuntime
from .class_report_service import (
    build_class_report_deps,
    deliver_class_report,
    enqueue_class_report_review_item,
    load_class_report_job,
    write_class_report_job,
    write_class_signal_bundle,
)
from .class_signal_bundle_models import ClassSignalBundle
from .strategies.planner import build_handoff_plan, build_lineage_metadata
from .strategies.selector import StrategySelectionError, build_default_strategy_selector
from .wiring.survey_wiring import build_class_report_specialist_runtime


@dataclass(frozen=True)
class ClassReportOrchestratorDeps:
    load_job: Callable[[str], Dict[str, Any]]
    write_job: Callable[[str, Dict[str, Any]], Dict[str, Any]]
    write_bundle: Callable[[str, Dict[str, Any]], Dict[str, Any]]
    artifact_runtime: ArtifactAdapterRuntime
    specialist_runtime: Any
    deliver_report: Callable[..., Dict[str, Any]]
    enqueue_review_item: Callable[..., Dict[str, Any]]
    review_confidence_floor: Callable[[], float]
    domain_enabled: Callable[[], bool]
    domain_review_only: Callable[[], bool]
    diag_log: Callable[..., None]
    build_teacher_context: Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]



def build_class_report_orchestrator_deps(core: Any | None = None) -> ClassReportOrchestratorDeps:
    service_deps = build_class_report_deps(core)
    runtime = ArtifactAdapterRuntime(build_platform_artifact_registry(core))
    return ClassReportOrchestratorDeps(
        load_job=lambda job_id: load_class_report_job(job_id, deps=service_deps),
        write_job=lambda job_id, updates: write_class_report_job(job_id, updates, deps=service_deps),
        write_bundle=lambda job_id, payload: write_class_signal_bundle(job_id, payload, deps=service_deps),
        artifact_runtime=runtime,
        specialist_runtime=build_class_report_specialist_runtime(core),
        deliver_report=lambda **kwargs: deliver_class_report(deps=service_deps, **kwargs),
        enqueue_review_item=lambda **kwargs: enqueue_class_report_review_item(deps=service_deps, **kwargs),
        review_confidence_floor=settings.survey_review_confidence_floor,
        domain_enabled=lambda: settings.analysis_domain_enabled('class_report'),
        domain_review_only=lambda: settings.analysis_domain_review_only('class_report'),
        diag_log=getattr(core, 'diag_log', lambda *_args, **_kwargs: None),
        build_teacher_context=lambda job, bundle: {
            'teacher_id': str(job.get('teacher_id') or '').strip(),
            'class_name': str(job.get('class_name') or '').strip(),
            'report_mode': 'teacher_report',
            'analysis_depth': 'class_signal_v1',
            'bundle_confidence': bundle.get('parse_confidence'),
        },
    )



def _review_queue_reason(strategy_reason: str) -> str:
    reason = str(strategy_reason or '').strip()
    if reason == 'low_confidence_review':
        return 'low_confidence_bundle'
    return reason or 'needs_review'



def _mark_job_failed(job_id: str, deps: ClassReportOrchestratorDeps, *, error: str) -> Dict[str, Any]:
    job = deps.write_job(job_id, {'status': 'failed', 'error': error})
    return {
        'ok': False,
        'job_id': job_id,
        'status': str(job.get('status') or 'failed'),
        'error': error,
    }



def process_class_report_job(job_id: str, *, deps: ClassReportOrchestratorDeps) -> Dict[str, Any]:
    job = deps.load_job(job_id)
    status = str(job.get('status') or '').strip().lower()
    if status in {'teacher_notified', 'analysis_ready', 'failed', 'review'}:
        return {'ok': True, 'job_id': job_id, 'status': str(job.get('status') or '')}

    try:
        if not deps.domain_enabled():
            return _mark_job_failed(job_id, deps, error='analysis_domain_disabled')

        payload = dict(job.get('raw_payload') or {})
        input_type = str(job.get('input_type') or payload.get('input_type') or 'self_hosted_form_json').strip() or 'self_hosted_form_json'
        report_id = str(job.get('report_id') or job_id).strip() or job_id
        job = deps.write_job(
            job_id,
            {
                'status': 'intake_validated',
                'report_id': report_id,
                'analysis_type': 'class_report',
                'target_type': 'report',
                'target_id': report_id,
            },
        )

        artifact = deps.artifact_runtime.run(
            input_type=input_type,
            task_kind='class_report.analysis',
            payload=payload,
            context={'source_uri': job.get('source_uri') or payload.get('source_uri')},
        )
        bundle = ClassSignalBundle.model_validate(artifact.payload)
        deps.write_bundle(job_id, bundle.model_dump())
        job = deps.write_job(job_id, {'status': 'bundle_ready'})

        try:
            strategy = build_default_strategy_selector(float(deps.review_confidence_floor())).select(
                role='teacher',
                artifact=artifact,
                task_kind='class_report.analysis',
                target_scope='class',
                force_review_only=deps.domain_review_only(),
            )
        except StrategySelectionError as exc:
            if exc.code == 'strategy_disabled':
                return _mark_job_failed(job_id, deps, error='analysis_strategy_disabled')
            raise

        job = deps.write_job(
            job_id,
            {
                'strategy_id': strategy.strategy_id,
                **build_lineage_metadata(strategy=strategy, artifact=artifact),
            },
        )
        if strategy.review_required:
            item = deps.enqueue_review_item(
                report_id=report_id,
                teacher_id=str(job.get('teacher_id') or '').strip(),
                reason=_review_queue_reason(strategy.reason),
                confidence=artifact.confidence,
                target_id=report_id,
            )
            job = deps.write_job(
                job_id,
                {
                    'status': 'review',
                    'report_id': item['report_id'],
                    'review_reason': item['reason'],
                    'review_confidence': item.get('confidence'),
                },
            )
            return {'ok': True, 'job_id': job_id, 'status': job['status'], 'report_id': item['report_id']}

        teacher_context = deps.build_teacher_context(job, bundle.model_dump())
        plan = build_handoff_plan(
            strategy=strategy,
            artifact=artifact,
            artifact_id=job_id,
            handoff_id=f'class-report-handoff-{job_id}',
            from_agent='coordinator',
            goal='输出班级信号归纳、教学建议与证据缺口说明',
            extra_constraints={'teacher_context': teacher_context},
            fallback_policy='enqueue_review',
        )
        job = deps.write_job(job_id, {'status': 'analysis_running'})
        result = deps.specialist_runtime.run(plan.handoff)
        job = deps.write_job(job_id, {'status': 'analysis_ready', 'analysis_confidence': result.confidence})
        report = deps.deliver_report(job=job, bundle=bundle.model_dump(), analysis_artifact=result.output)
        job = deps.write_job(job_id, {'status': 'teacher_notified', 'report_id': report['report_id']})
        return {'ok': True, 'job_id': job_id, 'report_id': report['report_id'], 'status': job['status']}
    except Exception as exc:
        deps.diag_log('class_report.orchestrator.failed', {'job_id': job_id, 'error': str(exc)[:200]})
        deps.write_job(job_id, {'status': 'failed', 'error': str(exc)[:200]})
        raise
