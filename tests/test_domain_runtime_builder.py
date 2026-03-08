from __future__ import annotations

import pytest

from services.api.domains.manifest_models import DomainManifest, DomainRuntimeBinding
from services.api.domains.manifest_registry import DomainManifestRegistry, build_default_domain_manifest_registry
from services.api.domains.runtime_builder import build_domain_specialist_runtime
from services.api.specialist_agents.contracts import HandoffContract
from services.api.specialist_agents.registry import SpecialistAgentSpec


@pytest.mark.parametrize(
    ('domain_id', 'to_agent', 'task_kind', 'constraints'),
    [
        (
            'survey',
            'survey_analyst',
            'survey.analysis',
            {
                'teacher_context': {'teacher_id': 'teacher_1'},
                'survey_evidence_bundle': {
                    'survey_meta': {'provider': 'provider_a', 'title': '班级问卷'},
                    'audience_scope': {'teacher_id': 'teacher_1', 'class_name': '高一(1)班'},
                    'question_summaries': [{'question_id': 'q1', 'prompt': '课堂节奏', 'stats': {'偏快': 8}}],
                    'parse_confidence': 0.92,
                },
            },
        ),
        (
            'class_report',
            'class_signal_analyst',
            'class_report.analysis',
            {
                'teacher_context': {'teacher_id': 'teacher_1'},
                'class_signal_bundle': {
                    'source_meta': {'provider': 'self_hosted', 'source_type': 'self_hosted_form', 'title': '班级周报'},
                    'class_scope': {'teacher_id': 'teacher_1', 'class_name': '高一(1)班'},
                    'question_like_signals': [
                        {'signal_id': 'signal_1', 'title': '作业完成度', 'summary': '整体完成度一般'}
                    ],
                    'parse_confidence': 0.87,
                },
            },
        ),
        (
            'video_homework',
            'video_homework_analyst',
            'video_homework.analysis',
            {
                'teacher_context': {'teacher_id': 'teacher_1'},
                'multimodal_submission_bundle': {
                    'source_meta': {'source_type': 'upload', 'title': '实验讲解视频', 'submission_id': 'submission_1'},
                    'scope': {'teacher_id': 'teacher_1', 'student_id': 'student_1', 'submission_kind': 'video_homework'},
                    'media_files': [{'file_id': 'file_1', 'kind': 'video', 'bytes': 1024, 'duration_sec': 12.0}],
                    'extraction_status': 'completed',
                    'parse_confidence': 0.89,
                },
            },
        ),
    ],
)
def test_runtime_builder_creates_specialist_runtime_from_manifest(
    domain_id: str,
    to_agent: str,
    task_kind: str,
    constraints: dict,
) -> None:
    manifests = build_default_domain_manifest_registry()

    runtime = build_domain_specialist_runtime(domain_id=domain_id, manifests=manifests, core=object())
    result = runtime.run(
        HandoffContract(
            handoff_id=f'{domain_id}_handoff',
            from_agent='coordinator',
            to_agent=to_agent,
            task_kind=task_kind,
            artifact_refs=[],
            goal='生成教师可读分析',
            constraints=constraints,
            budget={'max_tokens': 800, 'timeout_sec': 5, 'max_steps': 2},
            return_schema={'type': 'analysis_artifact'},
            status='prepared',
        )
    )

    assert result.agent_id == to_agent
    assert result.status == 'completed'


def test_manifest_requires_runtime_binding_metadata() -> None:
    registry = DomainManifestRegistry()
    registry.register(
        DomainManifest(
            domain_id='broken',
            display_name='Broken',
            specialists=[
                SpecialistAgentSpec(
                    agent_id='broken_analyst',
                    display_name='Broken Analyst',
                    roles=['teacher'],
                    accepted_artifacts=['broken_artifact'],
                    task_kinds=['broken.analysis'],
                    budgets={'default': {'max_tokens': 100, 'timeout_sec': 5, 'max_steps': 1}},
                    output_schema={'type': 'analysis_artifact'},
                )
            ],
            runtime_binding=DomainRuntimeBinding(
                specialist_deps_factory='',
                payload_constraint_key='',
            ),
        )
    )

    with pytest.raises(ValueError, match='runtime binding'):
        build_domain_specialist_runtime(domain_id='broken', manifests=registry, core=object())
