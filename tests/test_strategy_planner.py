from __future__ import annotations

from services.api.artifacts.contracts import ArtifactEnvelope
from services.api.strategies.planner import build_handoff_plan
from services.api.strategies.selector import build_default_strategy_selector


def test_planner_converts_strategy_decision_to_handoff_contract() -> None:
    selector = build_default_strategy_selector()
    artifact = ArtifactEnvelope(
        artifact_type='multimodal_submission_bundle',
        schema_version='v1',
        subject_scope={'teacher_id': 'teacher_1', 'student_id': 'student_1'},
        evidence_refs=[],
        confidence=0.83,
        missing_fields=[],
        provenance={'source': 'upload'},
        payload={'source_meta': {'title': '实验讲解视频', 'submission_id': 'submission_1'}},
    )
    decision = selector.select(
        role='teacher',
        artifact=artifact,
        task_kind='video_homework.analysis',
        target_scope='student',
    )

    plan = build_handoff_plan(
        strategy=decision,
        artifact=artifact,
        artifact_id='submission_1',
        handoff_id='handoff_1',
        from_agent='coordinator',
        goal='输出视频作业洞察和教学建议',
        extra_constraints={
            'teacher_context': {
                'teacher_id': 'teacher_1',
                'student_id': 'student_1',
                'report_mode': 'teacher_report',
            }
        },
        fallback_policy='ask_user_to_clarify',
    )

    assert plan.strategy_id == 'video_homework.teacher.report'
    assert plan.delivery_mode == 'teacher_report'
    assert plan.review_required is False
    assert plan.fallback_policy == 'ask_user_to_clarify'
    assert plan.handoff.to_agent == 'video_homework_analyst'
    assert plan.handoff.artifact_refs[0].artifact_id == 'submission_1'
    assert plan.handoff.constraints['multimodal_submission_bundle']['source_meta']['title'] == '实验讲解视频'
    assert plan.handoff.constraints['teacher_context']['report_mode'] == 'teacher_report'
