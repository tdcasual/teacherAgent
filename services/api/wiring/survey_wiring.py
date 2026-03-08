from __future__ import annotations

from typing import Any, Optional

from ..artifacts.registry import ArtifactAdapterRegistry, build_artifact_registry_from_manifests
from ..artifacts.runtime import ArtifactAdapterRuntime
from ..class_signal_bundle_models import ClassSignalBundle
from ..domains.manifest_registry import DomainManifestRegistry, build_default_domain_manifest_registry
from ..multimodal_submission_models import MultimodalSubmissionBundle
from ..specialist_agents.class_signal_analyst import (
    ClassSignalAnalystDeps,
    load_class_signal_analyst_prompt,
    run_class_signal_analyst,
)
from ..specialist_agents.governor import SpecialistAgentGovernor
from ..specialist_agents.registry import SpecialistAgentRegistry
from ..specialist_agents.runtime import SpecialistAgentRuntime
from ..specialist_agents.survey_analyst import SurveyAnalystDeps, load_survey_analyst_prompt, run_survey_analyst
from ..specialist_agents.video_homework_analyst import (
    VideoHomeworkAnalystDeps,
    load_video_homework_analyst_prompt,
    run_video_homework_analyst,
)
from ..survey.deps import SurveyApplicationDeps, build_survey_application_deps
from ..survey_report_service import (
    build_survey_report_deps,
    get_survey_report as _get_survey_report_impl,
    list_survey_reports as _list_survey_reports_impl,
    list_survey_review_queue as _list_survey_review_queue_impl,
    rerun_survey_report as _rerun_survey_report_impl,
)
from ..survey_repository import load_survey_bundle as _load_survey_bundle_impl
from . import get_app_core as _app_core



def build_survey_deps(core: Any) -> SurveyApplicationDeps:
    return build_survey_application_deps(core)



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



def _domain_manifests() -> DomainManifestRegistry:
    return build_default_domain_manifest_registry()



def build_survey_artifact_registry(core: Any) -> ArtifactAdapterRegistry:
    _ = core
    manifests = _domain_manifests()
    return build_artifact_registry_from_manifests([manifests.get('survey')])



def build_survey_artifact_runtime(core: Any) -> ArtifactAdapterRuntime:
    return ArtifactAdapterRuntime(build_survey_artifact_registry(core))



def build_survey_specialist_registry(core: Any) -> SpecialistAgentRegistry:
    registry = SpecialistAgentRegistry()
    analyst_deps = build_survey_analyst_deps(core)
    manifest_spec = _domain_manifests().get('survey').specialists[0]

    def _runner(handoff):
        constraints = handoff.constraints if isinstance(handoff.constraints, dict) else {}
        return run_survey_analyst(
            handoff=handoff,
            survey_evidence_bundle=dict(constraints.get('survey_evidence_bundle') or {}),
            teacher_context=dict(constraints.get('teacher_context') or {}),
            task_goal=str(handoff.goal or '').strip(),
            deps=analyst_deps,
        )

    registry.register(manifest_spec, runner=_runner)
    return registry



def build_class_report_specialist_registry(core: Any) -> SpecialistAgentRegistry:
    registry = SpecialistAgentRegistry()
    analyst_deps = build_class_signal_analyst_deps(core)
    manifest_spec = _domain_manifests().get('class_report').specialists[0]

    def _runner(handoff):
        constraints = handoff.constraints if isinstance(handoff.constraints, dict) else {}
        return run_class_signal_analyst(
            handoff=handoff,
            class_signal_bundle=ClassSignalBundle.model_validate(dict(constraints.get('class_signal_bundle') or {})),
            teacher_context=dict(constraints.get('teacher_context') or {}),
            task_goal=str(handoff.goal or '').strip(),
            deps=analyst_deps,
        )

    registry.register(manifest_spec, runner=_runner)
    return registry



def build_multimodal_specialist_registry(core: Any) -> SpecialistAgentRegistry:
    registry = SpecialistAgentRegistry()
    analyst_deps = build_video_homework_analyst_deps(core)
    manifest_spec = _domain_manifests().get('video_homework').specialists[0]

    def _runner(handoff):
        constraints = handoff.constraints if isinstance(handoff.constraints, dict) else {}
        return run_video_homework_analyst(
            handoff=handoff,
            multimodal_submission_bundle=MultimodalSubmissionBundle.model_validate(
                dict(constraints.get('multimodal_submission_bundle') or {})
            ),
            teacher_context=dict(constraints.get('teacher_context') or {}),
            task_goal=str(handoff.goal or '').strip(),
            deps=analyst_deps,
        )

    registry.register(manifest_spec, runner=_runner)
    return registry



def _build_specialist_runtime(registry: SpecialistAgentRegistry, core: Any) -> SpecialistAgentRuntime:
    diag_log = getattr(core, 'diag_log', lambda *_args, **_kwargs: None)

    def _event_sink(event) -> None:
        diag_log(
            f'specialist.runtime.{event.phase}',
            {
                'handoff_id': event.handoff_id,
                'agent_id': event.agent_id,
                'task_kind': event.task_kind,
                **dict(event.metadata or {}),
            },
        )

    return SpecialistAgentRuntime(
        registry,
        governor=SpecialistAgentGovernor(event_sink=_event_sink),
    )



def build_survey_specialist_runtime(core: Any) -> SpecialistAgentRuntime:
    return _build_specialist_runtime(build_survey_specialist_registry(core), core)



def build_class_report_specialist_runtime(core: Any) -> SpecialistAgentRuntime:
    return _build_specialist_runtime(build_class_report_specialist_registry(core), core)



def build_multimodal_specialist_runtime(core: Any) -> SpecialistAgentRuntime:
    return _build_specialist_runtime(build_multimodal_specialist_registry(core), core)



def survey_list_reports(teacher_id: str, status: Optional[str] = None, *, core: Any | None = None):
    return _list_survey_reports_impl(
        teacher_id=teacher_id,
        status=status,
        deps=build_survey_report_deps(_app_core(core)),
    )



def survey_get_report(report_id: str, teacher_id: str, *, core: Any | None = None):
    return _get_survey_report_impl(
        report_id=report_id,
        teacher_id=teacher_id,
        deps=build_survey_report_deps(_app_core(core)),
    )



def survey_rerun_report(report_id: str, teacher_id: str, reason: Optional[str] = None, *, core: Any | None = None):
    return _rerun_survey_report_impl(
        report_id=report_id,
        teacher_id=teacher_id,
        reason=reason,
        deps=build_survey_report_deps(_app_core(core)),
    )



def survey_list_review_queue(teacher_id: str, *, core: Any | None = None):
    return _list_survey_review_queue_impl(
        teacher_id=teacher_id,
        deps=build_survey_report_deps(_app_core(core)),
    )



def survey_load_bundle(job_id: str, *, core: Any | None = None):
    return _load_survey_bundle_impl(job_id, core=_app_core(core))
