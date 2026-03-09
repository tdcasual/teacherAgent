from __future__ import annotations

from typing import Any, Callable

from ..specialist_agents.class_signal_analyst import (
    ClassSignalAnalystDeps,
    load_class_signal_analyst_prompt,
    run_class_signal_analyst,
)
from ..specialist_agents.governor import SpecialistAgentGovernor
from ..specialist_agents.registry import SpecialistAgentRegistry
from ..specialist_agents.runtime import SpecialistAgentRuntime
from ..specialist_agents.survey_analyst import (
    SurveyAnalystDeps,
    load_survey_analyst_prompt,
    run_survey_analyst,
)
from ..specialist_agents.video_homework_analyst import (
    VideoHomeworkAnalystDeps,
    load_video_homework_analyst_prompt,
    run_video_homework_analyst,
)
from .manifest_registry import DomainManifestRegistry, build_default_domain_manifest_registry

Runner = Callable[..., Any]
DepsFactory = Callable[[Any], Any]


def build_survey_analyst_deps(core: Any) -> SurveyAnalystDeps:
    return SurveyAnalystDeps(
        call_llm=getattr(core, 'call_llm', lambda *_args, **_kwargs: {}),
        prompt_loader=load_survey_analyst_prompt,
        diag_log=getattr(core, 'diag_log', lambda *_args, **_kwargs: None),
    )



def build_class_signal_analyst_deps(core: Any) -> ClassSignalAnalystDeps:
    return ClassSignalAnalystDeps(
        call_llm=getattr(core, 'call_llm', lambda *_args, **_kwargs: {}),
        prompt_loader=load_class_signal_analyst_prompt,
        diag_log=getattr(core, 'diag_log', lambda *_args, **_kwargs: None),
    )



def build_video_homework_analyst_deps(core: Any) -> VideoHomeworkAnalystDeps:
    return VideoHomeworkAnalystDeps(
        call_llm=getattr(core, 'call_llm', lambda *_args, **_kwargs: {}),
        prompt_loader=load_video_homework_analyst_prompt,
        diag_log=getattr(core, 'diag_log', lambda *_args, **_kwargs: None),
    )


_DEPS_FACTORY_LOOKUP: dict[str, DepsFactory] = {
    'build_survey_analyst_deps': build_survey_analyst_deps,
    'build_class_signal_analyst_deps': build_class_signal_analyst_deps,
    'build_video_homework_analyst_deps': build_video_homework_analyst_deps,
}


_RUNNER_LOOKUP: dict[str, Runner] = {
    'survey_analyst': run_survey_analyst,
    'class_signal_analyst': run_class_signal_analyst,
    'video_homework_analyst': run_video_homework_analyst,
}



def build_domain_specialist_registry(
    *,
    domain_id: str,
    manifests: DomainManifestRegistry | None = None,
    core: Any,
) -> SpecialistAgentRegistry:
    manifest_registry = manifests or build_default_domain_manifest_registry()
    manifest = manifest_registry.get(domain_id)
    binding = manifest.runtime_binding
    if binding is None:
        raise ValueError(f'invalid runtime binding for domain {domain_id}')
    deps_factory_name = str(binding.specialist_deps_factory or '').strip()
    payload_constraint_key = str(binding.payload_constraint_key or '').strip()
    teacher_context_key = str(binding.teacher_context_constraint_key or '').strip() or 'teacher_context'
    if not deps_factory_name or not payload_constraint_key:
        raise ValueError(f'invalid runtime binding for domain {domain_id}')

    deps_factory = _DEPS_FACTORY_LOOKUP.get(deps_factory_name)
    if deps_factory is None:
        raise ValueError(f'invalid runtime binding for domain {domain_id}')
    deps = deps_factory(core)

    registry = SpecialistAgentRegistry()
    for spec in manifest.specialists:
        runner_impl = _RUNNER_LOOKUP.get(spec.agent_id)
        if runner_impl is None:
            raise ValueError(f'invalid runtime binding for domain {domain_id}')
        registry.register(
            spec,
            runner=_build_runner(
                runner_impl=runner_impl,
                deps=deps,
                payload_constraint_key=payload_constraint_key,
                teacher_context_key=teacher_context_key,
            ),
        )
    return registry



def build_domain_specialist_runtime(
    *,
    domain_id: str,
    manifests: DomainManifestRegistry | None = None,
    core: Any,
) -> SpecialistAgentRuntime:
    registry = build_domain_specialist_registry(domain_id=domain_id, manifests=manifests, core=core)
    diag_log = getattr(core, 'diag_log', lambda *_args, **_kwargs: None)
    metrics = getattr(core, 'analysis_metrics_service', None)

    def _event_sink(event) -> None:
        diag_log(
            f'specialist.runtime.{event.phase}',
            {
                'handoff_id': event.handoff_id,
                'agent_id': event.agent_id,
                'task_kind': event.task_kind,
                'domain': event.domain,
                'strategy_id': event.strategy_id,
                'reason_code': event.reason_code,
                **dict(event.metadata or {}),
            },
        )
        if hasattr(metrics, 'record'):
            metrics.record(event)

    return SpecialistAgentRuntime(
        registry,
        governor=SpecialistAgentGovernor(event_sink=_event_sink),
    )



def _build_runner(
    *,
    runner_impl: Runner,
    deps: Any,
    payload_constraint_key: str,
    teacher_context_key: str,
):
    def _runner(handoff):
        constraints = handoff.constraints if isinstance(handoff.constraints, dict) else {}
        return runner_impl(
            handoff=handoff,
            teacher_context=dict(constraints.get(teacher_context_key) or {}),
            task_goal=str(handoff.goal or '').strip(),
            deps=deps,
            **{payload_constraint_key: dict(constraints.get(payload_constraint_key) or {})},
        )

    return _runner
