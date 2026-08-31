from __future__ import annotations

import pytest

from services.api.specialist_agents.contracts import HandoffContract, SpecialistAgentResult
from services.api.specialist_agents.governor import (
    SpecialistAgentGovernor,
    SpecialistAgentRuntimeError,
)
from services.api.specialist_agents.registry import SpecialistAgentSpec


def _spec(schema_type: str = 'video_homework.analysis_artifact') -> SpecialistAgentSpec:
    return SpecialistAgentSpec(
        agent_id='video_homework_analyst',
        display_name='Video Homework Analyst',
        roles=['teacher'],
        accepted_artifacts=['video_homework_bundle'],
        task_kinds=['video_homework.analysis'],
        budgets={'default': {'max_tokens': 1600, 'timeout_sec': 5, 'max_steps': 2}},
        output_schema={'type': schema_type},
        evaluation_suite=['video_homework_v1_golden'],
    )



def _handoff() -> HandoffContract:
    return HandoffContract(
        handoff_id='handoff_1',
        from_agent='coordinator',
        to_agent='video_homework_analyst',
        task_kind='video_homework.analysis',
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



def test_governor_accepts_valid_typed_video_homework_analysis_artifact() -> None:
    governor = SpecialistAgentGovernor()

    result = governor.run(
        handoff=_handoff(),
        spec=_spec(),
        runner=lambda handoff: SpecialistAgentResult(
            handoff_id=handoff.handoff_id,
            agent_id=handoff.to_agent,
            status='completed',
            output={
                'executive_summary': '已完成视频作业分析。',
                'completion_overview': {'status': 'complete', 'summary': '学生讲完了推导'},
                'key_signals': [{'title': '推理断点', 'detail': '第二步卡住', 'evidence_refs': ['t:12']}],
                'expression_signals': [],
                'evidence_clips': [],
                'teaching_recommendations': ['让学生重述第二步。'],
                'confidence_and_gaps': {'confidence': 0.82, 'gaps': []},
            },
        ),
    )

    assert result.status == 'completed'
    assert result.output['executive_summary'] == '已完成视频作业分析。'



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
                    'completion_overview': {'status': 'complete', 'summary': '讲完了'},
                    'key_signals': [{'title': '推理断点', 'detail': '第二步卡住', 'evidence_refs': ['t:12']}],
                    'expression_signals': [],
                    'evidence_clips': [],
                    'teaching_recommendations': [],
                    'confidence_and_gaps': {'confidence': 0.82, 'gaps': []},
                },
            ),
        )

    assert exc_info.value.code == 'invalid_output'
