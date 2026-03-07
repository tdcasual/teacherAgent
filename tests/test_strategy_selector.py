from __future__ import annotations

import pytest

from services.api.artifacts.contracts import ArtifactEnvelope
from services.api.strategies.selector import StrategySelectionError, build_default_strategy_selector



def _survey_artifact(confidence: float = 0.81) -> ArtifactEnvelope:
    return ArtifactEnvelope(
        artifact_type='survey_evidence_bundle',
        schema_version='v1',
        subject_scope={'teacher_id': 'teacher_1', 'class_name': '高二2403班'},
        evidence_refs=[],
        confidence=confidence,
        missing_fields=[],
        provenance={'source': 'structured'},
        payload={'survey_meta': {'title': '课堂反馈问卷'}},
    )



def test_selector_chooses_different_strategy_for_same_artifact_under_different_task_kinds() -> None:
    selector = build_default_strategy_selector()

    report = selector.select(role='teacher', artifact=_survey_artifact(), task_kind='survey.analysis', target_scope='class')
    chat = selector.select(role='teacher', artifact=_survey_artifact(), task_kind='survey.chat_followup', target_scope='class')

    assert report.strategy_id == 'survey.teacher.report'
    assert report.delivery_mode == 'teacher_report'
    assert chat.strategy_id == 'survey.chat.followup'
    assert chat.delivery_mode == 'chat_reply'



def test_selector_forces_low_confidence_artifact_to_review_delivery() -> None:
    selector = build_default_strategy_selector()

    decision = selector.select(role='teacher', artifact=_survey_artifact(0.41), task_kind='survey.analysis', target_scope='class')

    assert decision.strategy_id == 'survey.teacher.report'
    assert decision.review_required is True
    assert decision.delivery_mode == 'review_queue'
    assert decision.reason == 'low_confidence_review'



def test_selector_rejects_unsupported_artifact_task_combination() -> None:
    selector = build_default_strategy_selector()
    artifact = ArtifactEnvelope(
        artifact_type='video_homework_bundle',
        schema_version='v1',
        subject_scope={'teacher_id': 'teacher_1'},
        evidence_refs=[],
        confidence=0.9,
        missing_fields=[],
        provenance={'source': 'video'},
        payload={},
    )

    with pytest.raises(StrategySelectionError) as exc_info:
        selector.select(role='teacher', artifact=artifact, task_kind='video.analysis', target_scope='student')

    assert exc_info.value.code == 'unsupported_strategy'


def _multimodal_artifact(confidence: float = 0.84) -> ArtifactEnvelope:
    return ArtifactEnvelope(
        artifact_type='multimodal_submission_bundle',
        schema_version='v1',
        subject_scope={'teacher_id': 'teacher_1', 'student_id': 'student_1'},
        evidence_refs=[],
        confidence=confidence,
        missing_fields=['teacher_rubric'],
        provenance={'source': 'upload'},
        payload={'source_meta': {'submission_id': 'submission_1'}},
    )



def test_selector_supports_video_homework_teacher_report() -> None:
    selector = build_default_strategy_selector()

    decision = selector.select(
        role='teacher',
        artifact=_multimodal_artifact(),
        task_kind='video_homework.analysis',
        target_scope='student',
    )

    assert decision.strategy_id == 'video_homework.teacher.report'
    assert decision.specialist_agent == 'video_homework_analyst'
    assert decision.delivery_mode == 'teacher_report'
