from __future__ import annotations

from typing import Any, Optional

from ..artifacts.registry import ArtifactAdapterRegistry, build_artifact_registry_from_manifests
from ..artifacts.runtime import ArtifactAdapterRuntime
from ..domains.manifest_registry import DomainManifestRegistry, build_default_domain_manifest_registry
from ..domains.runtime_builder import (
    build_class_signal_analyst_deps as _build_class_signal_analyst_deps,
    build_domain_specialist_registry,
    build_domain_specialist_runtime,
    build_survey_analyst_deps as _build_survey_analyst_deps,
    build_video_homework_analyst_deps as _build_video_homework_analyst_deps,
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
    return _build_survey_analyst_deps(core)



def build_class_signal_analyst_deps(core: Any) -> ClassSignalAnalystDeps:
    return _build_class_signal_analyst_deps(core)



def build_video_homework_analyst_deps(core: Any) -> VideoHomeworkAnalystDeps:
    return _build_video_homework_analyst_deps(core)



def _domain_manifests() -> DomainManifestRegistry:
    return build_default_domain_manifest_registry()



def build_survey_artifact_registry(core: Any) -> ArtifactAdapterRegistry:
    _ = core
    manifests = _domain_manifests()
    return build_artifact_registry_from_manifests([manifests.get('survey')])



def build_survey_artifact_runtime(core: Any) -> ArtifactAdapterRuntime:
    return ArtifactAdapterRuntime(build_survey_artifact_registry(core))



def build_survey_specialist_registry(core: Any) -> SpecialistAgentRegistry:
    return build_domain_specialist_registry(domain_id='survey', manifests=_domain_manifests(), core=core)



def build_class_report_specialist_registry(core: Any) -> SpecialistAgentRegistry:
    return build_domain_specialist_registry(domain_id='class_report', manifests=_domain_manifests(), core=core)



def build_multimodal_specialist_registry(core: Any) -> SpecialistAgentRegistry:
    return build_domain_specialist_registry(domain_id='video_homework', manifests=_domain_manifests(), core=core)



def build_survey_specialist_runtime(core: Any) -> SpecialistAgentRuntime:
    return build_domain_specialist_runtime(domain_id='survey', manifests=_domain_manifests(), core=core)



def build_class_report_specialist_runtime(core: Any) -> SpecialistAgentRuntime:
    return build_domain_specialist_runtime(domain_id='class_report', manifests=_domain_manifests(), core=core)



def build_multimodal_specialist_runtime(core: Any) -> SpecialistAgentRuntime:
    return build_domain_specialist_runtime(domain_id='video_homework', manifests=_domain_manifests(), core=core)



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
