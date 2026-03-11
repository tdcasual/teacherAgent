from __future__ import annotations

from ..artifacts.registry import ArtifactAdapterSpec
from ..specialist_agents.registry import SpecialistAgentSpec
from ..strategies.contracts import StrategySpec
from .manifest_models import DomainManifest, DomainReportBinding, DomainRuntimeBinding


class DomainManifestNotFoundError(KeyError):
    pass


class DomainManifestRegistry:
    def __init__(self) -> None:
        self._entries: dict[str, DomainManifest] = {}

    def register(self, manifest: DomainManifest) -> None:
        self._entries[str(manifest.domain_id or '').strip()] = manifest

    def get(self, domain_id: str) -> DomainManifest:
        entry = self._entries.get(str(domain_id or '').strip())
        if entry is None:
            raise DomainManifestNotFoundError(str(domain_id or ''))
        return entry

    def list(self) -> list[DomainManifest]:
        return [self._entries[key] for key in sorted(self._entries)]



def _survey_manifest(review_confidence_floor: float) -> DomainManifest:
    return DomainManifest(
        domain_id='survey',
        display_name='Survey Analysis',
        artifact_adapters=[
            ArtifactAdapterSpec(
                adapter_id='survey.bundle.adapter',
                accepted_inputs=['survey_bundle'],
                output_artifact_type='survey_evidence_bundle',
                task_kinds=['survey.analysis', 'survey.chat_followup'],
                validation_rules=[],
            ),
        ],
        strategies=[
            StrategySpec(
                strategy_id='survey.teacher.report',
                prompt_version='survey.teacher.report.prompt.v1',
                runtime_version='survey.runtime.v1',
                accepted_artifacts=['survey_evidence_bundle'],
                task_kinds=['survey.analysis'],
                specialist_agent='survey_analyst',
                review_policy='auto_on_low_confidence',
                delivery_mode='teacher_report',
                roles=['teacher'],
                target_scopes=['class'],
                confidence_floor=float(review_confidence_floor),
                budget={'max_tokens': 1600, 'timeout_sec': 45, 'max_steps': 2},
                return_schema={'type': 'analysis_artifact'},
            ),
            StrategySpec(
                strategy_id='survey.chat.followup',
                prompt_version='survey.chat_followup.prompt.v1',
                runtime_version='survey.runtime.v1',
                accepted_artifacts=['survey_evidence_bundle'],
                task_kinds=['survey.chat_followup'],
                specialist_agent='survey_analyst',
                review_policy='auto_on_low_confidence',
                delivery_mode='chat_reply',
                roles=['teacher'],
                target_scopes=['class'],
                confidence_floor=float(review_confidence_floor),
                budget={'max_tokens': 1600, 'timeout_sec': 45, 'max_steps': 2},
                return_schema={'type': 'analysis_artifact'},
            ),
        ],
        specialists=[
            SpecialistAgentSpec(
                agent_id='survey_analyst',
                display_name='Survey Analyst',
                roles=['teacher'],
                accepted_artifacts=['survey_evidence_bundle'],
                task_kinds=['survey.analysis'],
                direct_answer_capable=False,
                takeover_policy='coordinator_only',
                tool_allowlist=['llm.generate'],
                budgets={'default': {'max_tokens': 1600, 'timeout_sec': 45, 'max_steps': 2}},
                memory_policy='no_direct_memory_write',
                output_schema={'type': 'survey.analysis_artifact'},
                evaluation_suite=['survey_v1_golden'],
            ),
        ],
        runtime_binding=DomainRuntimeBinding(
            specialist_deps_factory='build_survey_analyst_deps',
            payload_constraint_key='survey_evidence_bundle',
        ),
        report_binding=DomainReportBinding(provider_factory='build_survey_analysis_report_provider'),
        rollout_stage='shadow_or_beta',
        feature_flags=['SURVEY_ANALYSIS_ENABLED', 'SURVEY_SHADOW_MODE', 'SURVEY_BETA_TEACHER_ALLOWLIST'],
    )



def _class_report_manifest(review_confidence_floor: float) -> DomainManifest:
    return DomainManifest(
        domain_id='class_report',
        display_name='Class Report Analysis',
        artifact_adapters=[
            ArtifactAdapterSpec(
                adapter_id='class_report.self_hosted_form.adapter',
                accepted_inputs=['self_hosted_form_json'],
                output_artifact_type='class_signal_bundle',
                task_kinds=['class_report.analysis'],
                validation_rules=['teacher_id_required'],
            ),
            ArtifactAdapterSpec(
                adapter_id='class_report.web_export.adapter',
                accepted_inputs=['web_export_html'],
                output_artifact_type='class_signal_bundle',
                task_kinds=['class_report.analysis'],
                validation_rules=['teacher_id_required'],
            ),
            ArtifactAdapterSpec(
                adapter_id='class_report.pdf_summary.adapter',
                accepted_inputs=['pdf_report_summary'],
                output_artifact_type='class_signal_bundle',
                task_kinds=['class_report.analysis'],
                validation_rules=['teacher_id_required'],
            ),
        ],
        strategies=[
            StrategySpec(
                strategy_id='class_signal.teacher.report',
                prompt_version='class_report.teacher.report.prompt.v1',
                runtime_version='class_report.runtime.v1',
                accepted_artifacts=['class_signal_bundle'],
                task_kinds=['class_report.analysis'],
                specialist_agent='class_signal_analyst',
                review_policy='auto_on_low_confidence',
                delivery_mode='teacher_report',
                roles=['teacher'],
                target_scopes=['class'],
                confidence_floor=float(review_confidence_floor),
                budget={'max_tokens': 1600, 'timeout_sec': 45, 'max_steps': 2},
                return_schema={'type': 'analysis_artifact'},
            ),
        ],
        specialists=[
            SpecialistAgentSpec(
                agent_id='class_signal_analyst',
                display_name='Class Signal Analyst',
                roles=['teacher'],
                accepted_artifacts=['class_signal_bundle'],
                task_kinds=['class_report.analysis'],
                direct_answer_capable=False,
                takeover_policy='coordinator_only',
                tool_allowlist=['llm.generate'],
                budgets={'default': {'max_tokens': 1600, 'timeout_sec': 45, 'max_steps': 2}},
                memory_policy='no_direct_memory_write',
                output_schema={'type': 'class_report.analysis_artifact'},
                evaluation_suite=['class_report_v1_golden'],
            ),
        ],
        runtime_binding=DomainRuntimeBinding(
            specialist_deps_factory='build_class_signal_analyst_deps',
            payload_constraint_key='class_signal_bundle',
        ),
        report_binding=DomainReportBinding(provider_factory='build_class_report_analysis_report_provider'),
        rollout_stage='internal_only',
        feature_flags=[],
    )



def _video_homework_manifest(review_confidence_floor: float) -> DomainManifest:
    return DomainManifest(
        domain_id='video_homework',
        display_name='Video Homework Analysis',
        artifact_adapters=[],
        strategies=[
            StrategySpec(
                strategy_id='video_homework.teacher.report',
                prompt_version='video_homework.teacher.report.prompt.v1',
                runtime_version='video_homework.runtime.v1',
                accepted_artifacts=['multimodal_submission_bundle'],
                task_kinds=['video_homework.analysis'],
                specialist_agent='video_homework_analyst',
                reviewer_agent='reviewer_analyst',
                review_policy='auto_on_low_confidence',
                delivery_mode='teacher_report',
                roles=['teacher'],
                target_scopes=['student'],
                confidence_floor=float(review_confidence_floor),
                budget={'max_tokens': 1600, 'timeout_sec': 45, 'max_steps': 2},
                return_schema={'type': 'analysis_artifact'},
            ),
        ],
        specialists=[
            SpecialistAgentSpec(
                agent_id='video_homework_analyst',
                display_name='Video Homework Analyst',
                roles=['teacher'],
                accepted_artifacts=['multimodal_submission_bundle'],
                task_kinds=['video_homework.analysis'],
                direct_answer_capable=False,
                takeover_policy='coordinator_only',
                tool_allowlist=['llm.generate'],
                budgets={'default': {'max_tokens': 1600, 'timeout_sec': 45, 'max_steps': 2}},
                memory_policy='no_direct_memory_write',
                output_schema={'type': 'video_homework.analysis_artifact'},
                evaluation_suite=['video_homework_v1_golden'],
            ),
            SpecialistAgentSpec(
                agent_id='reviewer_analyst',
                display_name='Reviewer Analyst',
                roles=['teacher'],
                accepted_artifacts=['multimodal_submission_bundle'],
                task_kinds=['video_homework.analysis'],
                direct_answer_capable=False,
                takeover_policy='coordinator_only',
                tool_allowlist=[],
                budgets={'default': {'max_tokens': 400, 'timeout_sec': 10, 'max_steps': 1}},
                memory_policy='no_direct_memory_write',
                output_schema={'type': 'reviewer_critique'},
                evaluation_suite=['video_homework_review_v1'],
            ),
        ],
        runtime_binding=DomainRuntimeBinding(
            specialist_deps_factory='build_video_homework_analyst_deps',
            payload_constraint_key='multimodal_submission_bundle',
        ),
        report_binding=DomainReportBinding(provider_factory='build_video_homework_analysis_report_provider'),
        rollout_stage='controlled_beta',
        feature_flags=[
            'MULTIMODAL_ENABLED',
            'MULTIMODAL_MAX_UPLOAD_BYTES',
            'MULTIMODAL_MAX_DURATION_SEC',
            'MULTIMODAL_EXTRACT_TIMEOUT_SEC',
        ],
    )



def build_default_domain_manifest_registry(review_confidence_floor: float = 0.7) -> DomainManifestRegistry:
    registry = DomainManifestRegistry()
    for manifest in (
        _class_report_manifest(review_confidence_floor),
        _survey_manifest(review_confidence_floor),
        _video_homework_manifest(review_confidence_floor),
    ):
        registry.register(manifest)
    return registry
