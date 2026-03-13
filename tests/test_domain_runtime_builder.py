from __future__ import annotations

import pytest

from services.api.domains.manifest_models import DomainManifest, DomainRuntimeBinding
from services.api.domains.manifest_registry import (
    DomainManifestRegistry,
    build_default_domain_manifest_registry,
)
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



def _callable_deps_factory(_core: object) -> object:
    return object()


def _callable_runner(*, handoff, teacher_context, task_goal, deps, custom_payload):
    return {
        'handoff_id': handoff.handoff_id,
        'agent_id': handoff.to_agent,
        'status': 'completed',
        'output': {'executive_summary': f"{task_goal}:{custom_payload.get('summary', 'ok')}"},
        'confidence': 0.93,
        'artifacts': [],
    }


def test_runtime_builder_supports_manifest_declared_callable_bindings() -> None:
    registry = DomainManifestRegistry()
    registry.register(
        DomainManifest(
            domain_id='callable',
            display_name='Callable Runtime',
            specialists=[
                SpecialistAgentSpec(
                    agent_id='callable_analyst',
                    display_name='Callable Analyst',
                    roles=['teacher'],
                    accepted_artifacts=['callable_artifact'],
                    task_kinds=['callable.analysis'],
                    budgets={'default': {'max_tokens': 100, 'timeout_sec': 5, 'max_steps': 1}},
                    output_schema={'type': 'analysis_artifact'},
                    runner_factory=_callable_runner,
                )
            ],
            runtime_binding=DomainRuntimeBinding(
                specialist_deps_factory=_callable_deps_factory,
                payload_constraint_key='custom_payload',
            ),
        )
    )

    runtime = build_domain_specialist_runtime(domain_id='callable', manifests=registry, core=object())
    result = runtime.run(
        HandoffContract(
            handoff_id='callable_handoff',
            from_agent='coordinator',
            to_agent='callable_analyst',
            task_kind='callable.analysis',
            artifact_refs=[],
            goal='生成可复用结论',
            constraints={
                'teacher_context': {'teacher_id': 'teacher_1'},
                'custom_payload': {'summary': 'callable manifest'},
            },
            budget={'max_tokens': 50, 'timeout_sec': 5, 'max_steps': 1},
            return_schema={'type': 'analysis_artifact'},
            status='prepared',
        )
    )

    assert result.agent_id == 'callable_analyst'
    assert result.output['executive_summary'] == '生成可复用结论:callable manifest'


def test_runtime_builder_uses_shared_binding_registry_for_named_bindings(monkeypatch) -> None:
    from services.api.domains import binding_registry

    registry = DomainManifestRegistry()
    registry.register(
        DomainManifest(
            domain_id='shared',
            display_name='Shared',
            specialists=[
                SpecialistAgentSpec(
                    agent_id='shared_analyst',
                    display_name='Shared Analyst',
                    roles=['teacher'],
                    accepted_artifacts=['shared_artifact'],
                    task_kinds=['shared.analysis'],
                    budgets={'default': {'max_tokens': 100, 'timeout_sec': 5, 'max_steps': 1}},
                    output_schema={'type': 'analysis_artifact'},
                    runner_factory='shared_runner',
                )
            ],
            runtime_binding=DomainRuntimeBinding(
                specialist_deps_factory='shared_deps',
                payload_constraint_key='custom_payload',
            ),
        )
    )

    monkeypatch.setattr(binding_registry, 'runtime_deps_factory_lookup', lambda: {'shared_deps': _callable_deps_factory})
    monkeypatch.setattr(binding_registry, 'runtime_runner_lookup', lambda: {'shared_runner': _callable_runner})

    runtime = build_domain_specialist_runtime(domain_id='shared', manifests=registry, core=object())
    result = runtime.run(
        HandoffContract(
            handoff_id='shared_handoff',
            from_agent='coordinator',
            to_agent='shared_analyst',
            task_kind='shared.analysis',
            artifact_refs=[],
            goal='生成可复用结论',
            constraints={
                'teacher_context': {'teacher_id': 'teacher_1'},
                'custom_payload': {'summary': 'shared lookup'},
            },
            budget={'max_tokens': 100, 'timeout_sec': 5, 'max_steps': 1},
            return_schema={'type': 'analysis_artifact'},
            status='prepared',
        )
    )

    assert result.agent_id == 'shared_analyst'
    assert result.output['executive_summary'] == '生成可复用结论:shared lookup'
