from __future__ import annotations

from services.api.artifacts.contracts import ArtifactEnvelope
from services.api.strategies.planner import build_handoff_plan
from services.api.strategies.selector import build_default_strategy_selector



def test_planner_converts_strategy_decision_to_handoff_contract() -> None:
    selector = build_default_strategy_selector()
    artifact = ArtifactEnvelope(
        artifact_type='survey_evidence_bundle',
        schema_version='v1',
        subject_scope={'teacher_id': 'teacher_1', 'class_name': '高二2403班'},
        evidence_refs=[],
        confidence=0.83,
        missing_fields=[],
        provenance={'source': 'structured'},
        payload={'survey_meta': {'title': '课堂反馈问卷'}},
    )
    decision = selector.select(role='teacher', artifact=artifact, task_kind='survey.chat_followup', target_scope='class')

    plan = build_handoff_plan(
        strategy=decision,
        artifact=artifact,
        artifact_id='job_1',
        handoff_id='handoff_1',
        from_agent='coordinator',
        goal='输出班级问卷洞察和教学建议',
        extra_constraints={
            'teacher_context': {
                'teacher_id': 'teacher_1',
                'class_name': '高二2403班',
                'report_mode': 'chat_followup',
            }
        },
        fallback_policy='ask_user_to_clarify',
    )

    assert plan.strategy_id == 'survey.chat.followup'
    assert plan.delivery_mode == 'chat_reply'
    assert plan.review_required is False
    assert plan.fallback_policy == 'ask_user_to_clarify'
    assert plan.handoff.to_agent == 'survey_analyst'
    assert plan.handoff.artifact_refs[0].artifact_id == 'job_1'
    assert plan.handoff.constraints['survey_evidence_bundle']['survey_meta']['title'] == '课堂反馈问卷'
    assert plan.handoff.constraints['teacher_context']['report_mode'] == 'chat_followup'
