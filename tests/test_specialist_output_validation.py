from __future__ import annotations

import pytest

from services.api.specialist_agents.contracts import HandoffContract, SpecialistAgentResult
from services.api.specialist_agents.governor import (
    SpecialistAgentGovernor,
    SpecialistAgentRuntimeError,
)
from services.api.specialist_agents.registry import SpecialistAgentSpec


def _spec(schema_type: str = 'survey.analysis_artifact') -> SpecialistAgentSpec:
    return SpecialistAgentSpec(
        agent_id='survey_analyst',
        display_name='Survey Analyst',
        roles=['teacher'],
        accepted_artifacts=['survey_evidence_bundle'],
        task_kinds=['survey.analysis'],
        budgets={'default': {'max_tokens': 1600, 'timeout_sec': 5, 'max_steps': 2}},
        output_schema={'type': schema_type},
        evaluation_suite=['survey_v1_golden'],
    )



def _handoff() -> HandoffContract:
    return HandoffContract(
        handoff_id='handoff_1',
        from_agent='coordinator',
        to_agent='survey_analyst',
        task_kind='survey.analysis',
        artifact_refs=[],
        goal='提炼班级洞察',
        constraints={},
        budget={'max_tokens': 800, 'timeout_sec': 5, 'max_steps': 2},
        return_schema={'type': 'analysis_artifact'},
        status='prepared',
    )



def test_governor_rejects_missing_required_typed_output_fields() -> None:
    governor = SpecialistAgentGovernor()

    with pytest.raises(SpecialistAgentRuntimeError) as exc_info:
        governor.run(
            handoff=_handoff(),
            spec=_spec(),
            runner=lambda handoff: SpecialistAgentResult(
                handoff_id=handoff.handoff_id,
                agent_id=handoff.to_agent,
                status='completed',
                output={'executive_summary': '只有摘要，不是完整 artifact'},
            ),
        )

    assert exc_info.value.code == 'invalid_output'



def test_governor_accepts_valid_typed_survey_analysis_artifact() -> None:
    governor = SpecialistAgentGovernor()

    result = governor.run(
        handoff=_handoff(),
        spec=_spec(),
        runner=lambda handoff: SpecialistAgentResult(
            handoff_id=handoff.handoff_id,
            agent_id=handoff.to_agent,
            status='completed',
            output={
                'executive_summary': '已完成班级问卷分析。',
                'key_signals': [{'title': '课堂节奏', 'detail': '多数学生认为偏快', 'evidence_refs': ['question:q1']}],
                'group_differences': [{'group_name': '前排', 'summary': '反馈更积极'}],
                'teaching_recommendations': ['放慢新概念讲解节奏。'],
                'confidence_and_gaps': {'confidence': 0.82, 'gaps': []},
            },
        ),
    )

    assert result.status == 'completed'
    assert result.output['executive_summary'] == '已完成班级问卷分析。'



def test_governor_rejects_empty_teaching_recommendations_in_typed_artifact() -> None:
    governor = SpecialistAgentGovernor()

    with pytest.raises(SpecialistAgentRuntimeError) as exc_info:
        governor.run(
            handoff=_handoff(),
            spec=_spec(),
            runner=lambda handoff: SpecialistAgentResult(
                handoff_id=handoff.handoff_id,
                agent_id=handoff.to_agent,
                status='completed',
                output={
                    'executive_summary': '表面上结构完整，但没有任何教学建议。',
                    'key_signals': [{'title': '课堂节奏', 'detail': '多数学生认为偏快', 'evidence_refs': ['question:q1']}],
                    'group_differences': [{'group_name': '前排', 'summary': '反馈更积极'}],
                    'teaching_recommendations': [],
                    'confidence_and_gaps': {'confidence': 0.82, 'gaps': []},
                },
            ),
        )

    assert exc_info.value.code == 'invalid_output'
