from __future__ import annotations

import pytest

from services.api.analysis_target_resolution_service import (
    AnalysisTargetResolutionError,
    build_recent_target_from_messages,
    extract_report_id_from_text,
    resolve_analysis_target,
)


def test_resolve_analysis_target_prefers_explicit_target_contract() -> None:
    target = resolve_analysis_target(
        explicit_target={
            'target_type': 'submission',
            'target_id': 'submission_7',
            'source_domain': 'video_homework',
            'artifact_type': 'video_submission_bundle',
            'strategy_id': 'video_homework.teacher.submission_review',
        },
        explicit_target_id='report_2',
        target_type='report',
        artifact_type='survey_evidence_bundle',
        teacher_id='teacher_1',
        source_domain='survey',
        candidates=[
            {'report_id': 'report_1', 'teacher_id': 'teacher_1'},
            {'report_id': 'report_2', 'teacher_id': 'teacher_1'},
        ],
        session_recent_target={
            'target_id': 'report_1',
            'target_type': 'report',
            'artifact_type': 'survey_evidence_bundle',
            'teacher_id': 'teacher_1',
            'source_domain': 'survey',
        },
    )

    assert target.target_type == 'submission'
    assert target.target_id == 'submission_7'
    assert target.source_domain == 'video_homework'
    assert target.artifact_type == 'video_submission_bundle'
    assert target.strategy_id == 'video_homework.teacher.submission_review'
    assert target.resolution_reason == 'explicit_target'



def test_resolve_analysis_target_prefers_explicit_report_id() -> None:
    target = resolve_analysis_target(
        explicit_target=None,
        explicit_target_id='report_2',
        target_type='report',
        artifact_type='survey_evidence_bundle',
        teacher_id='teacher_1',
        source_domain='survey',
        candidates=[
            {'report_id': 'report_1', 'teacher_id': 'teacher_1'},
            {'report_id': 'report_2', 'teacher_id': 'teacher_1'},
        ],
        session_recent_target={
            'target_id': 'report_1',
            'target_type': 'report',
            'artifact_type': 'survey_evidence_bundle',
            'teacher_id': 'teacher_1',
            'source_domain': 'survey',
        },
    )

    assert target.target_id == 'report_2'
    assert target.resolution_reason == 'explicit_target_id'



def test_resolve_analysis_target_falls_back_to_recent_session_target() -> None:
    target = resolve_analysis_target(
        explicit_target=None,
        explicit_target_id=None,
        target_type='report',
        artifact_type='survey_evidence_bundle',
        teacher_id='teacher_1',
        source_domain='survey',
        candidates=[
            {'report_id': 'report_1', 'teacher_id': 'teacher_1'},
            {'report_id': 'report_2', 'teacher_id': 'teacher_1'},
        ],
        session_recent_target={
            'target_id': 'report_2',
            'target_type': 'report',
            'artifact_type': 'survey_evidence_bundle',
            'teacher_id': 'teacher_1',
            'source_domain': 'survey',
        },
    )

    assert target.target_id == 'report_2'
    assert target.resolution_reason == 'session_recent_target'



def test_resolve_analysis_target_supports_class_candidates() -> None:
    target = resolve_analysis_target(
        explicit_target=None,
        explicit_target_id=None,
        target_type='class',
        artifact_type='class_report_bundle',
        teacher_id='teacher_1',
        source_domain='class_report',
        candidates=[
            {'class_id': 'class_2403', 'teacher_id': 'teacher_1'},
        ],
        session_recent_target=None,
    )

    assert target.target_type == 'class'
    assert target.target_id == 'class_2403'
    assert target.resolution_reason == 'single_candidate'



def test_resolve_analysis_target_rejects_ambiguous_candidates_without_explicit_target() -> None:
    with pytest.raises(AnalysisTargetResolutionError) as exc_info:
        resolve_analysis_target(
            explicit_target=None,
            explicit_target_id=None,
            target_type='report',
            artifact_type='survey_evidence_bundle',
            teacher_id='teacher_1',
            source_domain='survey',
            candidates=[
                {'report_id': 'report_1', 'teacher_id': 'teacher_1'},
                {'report_id': 'report_2', 'teacher_id': 'teacher_1'},
            ],
            session_recent_target=None,
        )

    assert exc_info.value.code == 'ambiguous_target'



def test_extract_report_id_from_text_and_build_recent_target_from_messages() -> None:
    assert extract_report_id_from_text('请基于 report_7 做深入复盘') == 'report_7'

    recent = build_recent_target_from_messages(
        [
            {'role': 'assistant', 'content': '你刚查看的是 report_3。'},
            {'role': 'user', 'content': '继续深入分析'},
        ],
        teacher_id='teacher_1',
        source_domain='survey',
        artifact_type='survey_evidence_bundle',
    )

    assert recent is not None
    assert recent['target_id'] == 'report_3'



def test_build_recent_target_from_messages_accepts_structured_ui_target_marker() -> None:
    recent = build_recent_target_from_messages(
        [
            {
                'role': 'assistant',
                'content': '[analysis_target] domain=survey target_type=report target_id=class-report-42 strategy_id=class_signal.teacher.report',
            },
            {'role': 'user', 'content': '继续深入分析'},
        ],
        teacher_id='teacher_1',
        source_domain='survey',
        artifact_type='survey_evidence_bundle',
    )

    assert recent is not None
    assert recent['target_id'] == 'class-report-42'
