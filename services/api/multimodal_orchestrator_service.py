from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict

from . import settings
from .analysis_specialist_failure_service import classify_specialist_failure
from .multimodal_report_service import (
    build_multimodal_report_deps,
    deliver_multimodal_report,
    enqueue_multimodal_review_item,
    load_multimodal_report_job,
    write_multimodal_report_job,
)
from .multimodal_repository import load_multimodal_submission_view
from .multimodal_submission_models import MultimodalSubmissionBundle
from .specialist_agents.governor import SpecialistAgentRuntimeError
from .specialist_agents.job_graph_models import JobGraphNode, SpecialistJobGraph
from .specialist_agents.job_graph_runtime import SpecialistJobGraphRuntime
from .strategies.planner import build_handoff_plan, build_lineage_metadata
from .strategies.selector import StrategySelectionError, build_default_strategy_selector
from .wiring.survey_wiring import build_multimodal_specialist_runtime


@dataclass(frozen=True)
class MultimodalOrchestratorDeps:
    load_submission: Callable[[str], Dict[str, Any]]
    load_job: Callable[[str], Dict[str, Any]]
    write_job: Callable[[str, Dict[str, Any]], Dict[str, Any]]
    specialist_runtime: Any
    deliver_report: Callable[..., Dict[str, Any]]
    enqueue_review_item: Callable[..., Dict[str, Any]]
    review_confidence_floor: Callable[[], float]
    domain_enabled: Callable[[], bool]
    domain_review_only: Callable[[], bool]
    diag_log: Callable[..., None]
    build_teacher_context: Callable[[Dict[str, Any]], Dict[str, Any]]



def build_multimodal_orchestrator_deps(core: Any | None = None) -> MultimodalOrchestratorDeps:
    service_deps = build_multimodal_report_deps(core)
    return MultimodalOrchestratorDeps(
        load_submission=lambda submission_id: load_multimodal_submission_view(submission_id, core=core),
        load_job=lambda submission_id: _load_job_optional(submission_id, service_deps),
        write_job=lambda submission_id, updates: write_multimodal_report_job(submission_id, updates, deps=service_deps),
        specialist_runtime=build_multimodal_specialist_runtime(core),
        deliver_report=lambda **kwargs: deliver_multimodal_report(deps=service_deps, **kwargs),
        enqueue_review_item=lambda **kwargs: enqueue_multimodal_review_item(deps=service_deps, **kwargs),
        review_confidence_floor=settings.survey_review_confidence_floor,
        domain_enabled=lambda: settings.analysis_domain_enabled('video_homework'),
        domain_review_only=lambda: settings.analysis_domain_review_only('video_homework'),
        diag_log=getattr(core, 'diag_log', lambda *_args, **_kwargs: None),
        build_teacher_context=lambda bundle: {
            'teacher_id': str((bundle.get('scope') or {}).get('teacher_id') or '').strip(),
            'student_id': str((bundle.get('scope') or {}).get('student_id') or '').strip(),
            'assignment_id': str((bundle.get('scope') or {}).get('assignment_id') or '').strip(),
            'submission_kind': str((bundle.get('scope') or {}).get('submission_kind') or '').strip(),
            'analysis_depth': 'video_homework_v1',
            'bundle_confidence': bundle.get('parse_confidence'),
        },
    )



def _review_queue_reason(strategy_reason: str) -> str:
    reason = str(strategy_reason or '').strip()
    if reason == 'low_confidence_review':
        return 'low_confidence_bundle'
    return reason or 'needs_review'



def _mark_job_failed(submission_id: str, deps: MultimodalOrchestratorDeps, *, error: str) -> Dict[str, Any]:
    job = deps.write_job(submission_id, {'status': 'failed', 'error': error})
    return {
        'ok': False,
        'submission_id': submission_id,
        'status': str(job.get('status') or 'failed'),
        'error': error,
    }



def process_multimodal_submission(submission_id: str, *, deps: MultimodalOrchestratorDeps) -> Dict[str, Any]:
    job = deps.load_job(submission_id)
    status = str(job.get('status') or '').strip().lower()
    if status in {'teacher_notified', 'analysis_ready', 'failed', 'review'}:
        return {'ok': True, 'submission_id': submission_id, 'status': str(job.get('status') or '')}

    try:
        if not deps.domain_enabled():
            return _mark_job_failed(submission_id, deps, error='analysis_domain_disabled')

        bundle = MultimodalSubmissionBundle.model_validate(deps.load_submission(submission_id))
        if bundle.extraction_status not in {'completed', 'partial'}:
            raise ValueError('multimodal_artifact_not_ready')

        teacher_id = str(bundle.scope.teacher_id or '').strip()
        report_id = str(job.get('report_id') or submission_id).strip() or submission_id
        job = deps.write_job(
            submission_id,
            {
                'submission_id': submission_id,
                'report_id': report_id,
                'teacher_id': teacher_id,
                'student_id': str(bundle.scope.student_id or '').strip() or None,
                'class_name': str(bundle.scope.class_name or '').strip() or None,
                'assignment_id': str(bundle.scope.assignment_id or '').strip() or None,
                'status': 'artifact_ready',
                'analysis_type': 'video_homework',
                'target_type': 'submission',
                'target_id': submission_id,
            },
        )

        artifact = bundle.to_artifact_envelope()
        try:
            strategy = build_default_strategy_selector(float(deps.review_confidence_floor())).select(
                role='teacher',
                artifact=artifact,
                task_kind='video_homework.analysis',
                target_scope='student',
                force_review_only=deps.domain_review_only(),
            )
        except StrategySelectionError as exc:
            if exc.code == 'strategy_disabled':
                return _mark_job_failed(submission_id, deps, error='analysis_strategy_disabled')
            raise

        job = deps.write_job(
            submission_id,
            {
                'strategy_id': strategy.strategy_id,
                **build_lineage_metadata(strategy=strategy, artifact=artifact),
            },
        )
        if strategy.review_required:
            item = deps.enqueue_review_item(
                report_id=report_id,
                teacher_id=teacher_id,
                reason=_review_queue_reason(strategy.reason),
                confidence=artifact.confidence,
                target_id=submission_id,
            )
            job = deps.write_job(
                submission_id,
                {
                    'status': 'review',
                    'report_id': item['report_id'],
                    'review_reason': item['reason'],
                    'review_confidence': item.get('confidence'),
                },
            )
            return {'ok': True, 'submission_id': submission_id, 'status': job['status'], 'report_id': item['report_id']}

        teacher_context = deps.build_teacher_context(bundle.model_dump())
        plan = build_handoff_plan(
            strategy=strategy,
            artifact=artifact,
            artifact_id=submission_id,
            handoff_id=f'video-homework-handoff-{submission_id}',
            from_agent='coordinator',
            goal='输出老师可读的视频作业反馈，包含完成度、表达信号、证据片段与教学建议',
            extra_constraints={'teacher_context': teacher_context},
            fallback_policy='enqueue_review',
        )
        graph = SpecialistJobGraph(
            graph_id=str(strategy.strategy_id),
            domain='video_homework',
            nodes=[
                JobGraphNode(
                    node_id='analyze',
                    node_type='analyze',
                    max_budget={
                        'max_tokens': float(plan.handoff.budget.max_tokens or 0),
                        'timeout_sec': float(plan.handoff.budget.timeout_sec or 0),
                        'max_steps': float(plan.handoff.budget.max_steps or 0),
                    },
                    handoff=plan.handoff.model_copy(update={'handoff_id': f'{plan.handoff.handoff_id}:analyze'}),
                ),
                JobGraphNode(
                    node_id='verify',
                    node_type='verify',
                    max_budget={
                        'max_tokens': float(plan.handoff.budget.max_tokens or 0),
                        'timeout_sec': float(plan.handoff.budget.timeout_sec or 0),
                        'max_steps': float(plan.handoff.budget.max_steps or 0),
                    },
                    handoff=plan.handoff.model_copy(
                        update={
                            'handoff_id': f'{plan.handoff.handoff_id}:verify',
                            'goal': '校验视频作业反馈结构完整性与证据一致性',
                        }
                    ),
                ),
            ]
        )
        job = deps.write_job(submission_id, {'status': 'analysis_running'})
        result = SpecialistJobGraphRuntime(executor=deps.specialist_runtime.run).run(graph).final_result
        job = deps.write_job(submission_id, {'status': 'analysis_ready', 'analysis_confidence': result.confidence})
        report = deps.deliver_report(job=job, bundle=bundle.model_dump(), analysis_artifact=result.output)
        job = deps.write_job(submission_id, {'status': 'teacher_notified', 'report_id': report['report_id']})
        return {'ok': True, 'submission_id': submission_id, 'report_id': report['report_id'], 'status': job['status']}
    except SpecialistAgentRuntimeError as exc:
        return _handle_specialist_runtime_failure(submission_id, report_id, teacher_id, job, artifact.confidence, deps, exc=exc)
    except Exception as exc:
        deps.diag_log('multimodal.orchestrator.failed', {'submission_id': submission_id, 'error': str(exc)[:200]})
        deps.write_job(submission_id, {'status': 'failed', 'error': str(exc)[:200]})
        raise




def _handle_specialist_runtime_failure(
    submission_id: str,
    report_id: str,
    teacher_id: str,
    job: Dict[str, Any],
    artifact_confidence: Any,
    deps: MultimodalOrchestratorDeps,
    *,
    exc: SpecialistAgentRuntimeError,
) -> Dict[str, Any]:
    decision = classify_specialist_failure(exc)
    deps.diag_log(
        'multimodal.orchestrator.specialist_failed',
        {'submission_id': submission_id, 'report_id': report_id, 'code': decision.reason, 'error': decision.error},
    )
    if decision.action != 'review':
        return _mark_job_failed(submission_id, deps, error=decision.reason)
    item = deps.enqueue_review_item(
        report_id=report_id,
        teacher_id=teacher_id,
        reason=decision.reason,
        confidence=artifact_confidence,
        target_id=submission_id,
    )
    job = deps.write_job(
        submission_id,
        {
            'status': 'review',
            'report_id': item['report_id'],
            'review_reason': item['reason'],
            'review_confidence': item.get('confidence'),
            'error': decision.error,
        },
    )
    return {'ok': True, 'submission_id': submission_id, 'status': job['status'], 'report_id': item['report_id']}


def _load_job_optional(submission_id: str, service_deps: Any) -> Dict[str, Any]:
    try:
        return load_multimodal_report_job(submission_id, deps=service_deps)
    except FileNotFoundError:
        return {}
