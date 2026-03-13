from __future__ import annotations

from services.api.specialist_agents.contracts import HandoffContract, SpecialistAgentResult
from services.api.specialist_agents.reviewer_analyst import (
    ReviewerAnalystDeps,
    run_reviewer_analyst,
)


def _analysis_result(*, recommendations: list[str], evidence_ref: str | None = 'segment:asr_1') -> SpecialistAgentResult:
    evidence_clips = []
    if evidence_ref:
        evidence_clips.append(
            {
                'label': '器材介绍',
                'start_sec': 0.0,
                'end_sec': 4.0,
                'evidence_ref': evidence_ref,
                'excerpt': '首先介绍实验器材与步骤。',
            }
        )
    return SpecialistAgentResult(
        handoff_id='video-homework-handoff:analyze',
        agent_id='video_homework_analyst',
        status='completed',
        confidence=0.86,
        output={
            'executive_summary': '学生能完整展示实验步骤，但口头表达仍偏简略。',
            'completion_overview': {'status': 'completed', 'summary': '已完成主要实验流程展示。', 'duration_sec': 58.0},
            'key_signals': [
                {'title': '步骤表达较完整', 'detail': '能够按顺序介绍器材与步骤。', 'evidence_refs': ['segment:asr_1']}
            ],
            'expression_signals': [
                {'title': '步骤表达较完整', 'detail': '能够按顺序介绍器材与步骤。', 'evidence_refs': ['segment:asr_1']}
            ],
            'evidence_clips': evidence_clips,
            'teaching_recommendations': recommendations,
            'confidence_and_gaps': {'confidence': 0.86, 'gaps': ['teacher_rubric']},
        },
    )



def _review_handoff(previous_result: SpecialistAgentResult) -> HandoffContract:
    return HandoffContract(
        handoff_id='video-homework-handoff:verify',
        from_agent='coordinator',
        to_agent='reviewer_analyst',
        task_kind='video_homework.analysis',
        strategy_id='video_homework.teacher.report',
        artifact_refs=[],
        goal='校验视频作业反馈结构完整性与证据一致性',
        constraints={
            'teacher_context': {'teacher_id': 'teacher_1', 'student_id': 'student_1'},
            'job_graph_previous_result': previous_result.model_dump(),
            'job_graph_results': {'analyze': previous_result.model_dump()},
            'job_graph_trace': ['analyze'],
        },
        budget={'max_tokens': 400, 'timeout_sec': 5, 'max_steps': 1},
        return_schema={'type': 'reviewer_critique'},
        status='prepared',
    )



def test_reviewer_analyst_approves_complete_video_homework_artifact() -> None:
    result = run_reviewer_analyst(
        handoff=_review_handoff(_analysis_result(recommendations=['增加术语表达模板练习。'])),
        teacher_context={'teacher_id': 'teacher_1'},
        task_goal='校验视频作业反馈结构完整性与证据一致性',
        multimodal_submission_bundle={'scope': {'teacher_id': 'teacher_1', 'student_id': 'student_1'}},
        deps=ReviewerAnalystDeps(diag_log=lambda *_args, **_kwargs: None),
    )

    assert result.status == 'completed'
    assert result.output['approved'] is True
    assert result.output['reason_codes'] == []
    assert result.output['recommended_action'] == 'deliver'
    assert 'completion_overview' in result.output['checked_sections']



def test_reviewer_analyst_rejects_incomplete_video_homework_artifact() -> None:
    result = run_reviewer_analyst(
        handoff=_review_handoff(_analysis_result(recommendations=[], evidence_ref=None)),
        teacher_context={'teacher_id': 'teacher_1'},
        task_goal='校验视频作业反馈结构完整性与证据一致性',
        multimodal_submission_bundle={'scope': {'teacher_id': 'teacher_1', 'student_id': 'student_1'}},
        deps=ReviewerAnalystDeps(diag_log=lambda *_args, **_kwargs: None),
    )

    assert result.status == 'completed'
    assert result.output['approved'] is False
    assert 'missing_evidence_clips' in result.output['reason_codes']
    assert 'missing_teaching_recommendations' in result.output['reason_codes']
    assert result.output['recommended_action'] == 'enqueue_review'


def test_reviewer_analyst_returns_v2_issue_list_and_quality_score() -> None:
    result = run_reviewer_analyst(
        handoff=_review_handoff(_analysis_result(recommendations=[], evidence_ref=None)),
        teacher_context={'teacher_id': 'teacher_1'},
        task_goal='校验视频作业反馈结构完整性与证据一致性',
        multimodal_submission_bundle={'scope': {'teacher_id': 'teacher_1', 'student_id': 'student_1'}},
        deps=ReviewerAnalystDeps(diag_log=lambda *_args, **_kwargs: None),
    )

    assert result.output['quality_score'] < 0.8
    assert result.output['issue_list']
    assert any(item['severity'] == 'high' for item in result.output['issue_list'])
    assert any(item['reason_code'] == 'missing_evidence_clips' for item in result.output['issue_list'])
