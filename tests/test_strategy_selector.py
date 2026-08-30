from __future__ import annotations

import pytest

from services.api.artifacts.contracts import ArtifactEnvelope
from services.api.strategies.selector import StrategySelectionError, build_default_strategy_selector


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


def test_selector_chooses_different_strategy_for_same_artifact_under_different_task_kinds() -> None:
    selector = build_default_strategy_selector()
    artifact = _multimodal_artifact()

    report = selector.select(
        role='teacher',
        artifact=artifact,
        task_kind='video_homework.analysis',
        target_scope='student',
    )

    assert report.strategy_id == 'video_homework.teacher.report'
    assert report.delivery_mode == 'teacher_report'

    with pytest.raises(StrategySelectionError) as exc_info:
        selector.select(
            role='teacher',
            artifact=artifact,
            task_kind='survey.analysis',
            target_scope='student',
        )

    assert exc_info.value.code == 'unsupported_strategy'


def test_selector_forces_low_confidence_artifact_to_review_delivery() -> None:
    selector = build_default_strategy_selector()

    decision = selector.select(
        role='teacher',
        artifact=_multimodal_artifact(0.41),
        task_kind='video_homework.analysis',
        target_scope='student',
    )

    assert decision.strategy_id == 'video_homework.teacher.report'
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


def test_selector_rejects_disabled_strategy_ids(monkeypatch) -> None:
    monkeypatch.setenv('ANALYSIS_DISABLED_STRATEGIES', 'video_homework.teacher.report')
    selector = build_default_strategy_selector()

    with pytest.raises(StrategySelectionError) as exc_info:
        selector.select(
            role='teacher',
            artifact=_multimodal_artifact(),
            task_kind='video_homework.analysis',
            target_scope='student',
        )

    assert exc_info.value.code == 'strategy_disabled'


def test_selector_marks_video_homework_strategy_with_internal_reviewer() -> None:
    selector = build_default_strategy_selector()

    decision = selector.select(
        role='teacher',
        artifact=_multimodal_artifact(),
        task_kind='video_homework.analysis',
        target_scope='student',
    )

    assert decision.reviewer_agent == 'reviewer_analyst'
