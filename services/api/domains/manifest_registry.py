from __future__ import annotations

from ..specialist_agents.registry import SpecialistAgentSpec
from ..strategies.contracts import StrategySpec
from .manifest_models import DomainManifest, DomainRuntimeBinding


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
        report_binding=None,
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
    for manifest in (_video_homework_manifest(review_confidence_floor),):
        registry.register(manifest)
    return registry
