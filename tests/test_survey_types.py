from __future__ import annotations

from services.api import settings
from services.api.api_models import (
    SurveyReportDetail,
    SurveyReportRerunRequest,
    SurveyReportSummary,
    SurveyReviewQueueItemSummary,
    SurveyWebhookAckResponse,
)


def test_survey_api_models_minimal_roundtrip() -> None:
    ack = SurveyWebhookAckResponse(ok=True, job_id='survey_job_1', status='queued')
    assert ack.job_id == 'survey_job_1'
    assert ack.status == 'queued'

    summary = SurveyReportSummary(
        report_id='report_1',
        teacher_id='teacher_1',
        class_name='高二2403班',
        status='analysis_ready',
        confidence=0.86,
        summary='班级整体对实验设计理解偏弱',
        created_at='2026-03-06T10:00:00',
    )
    detail = SurveyReportDetail(
        report=summary,
        analysis_artifact={'executive_summary': 'ok'},
        bundle_meta={'parse_confidence': 0.86},
        review_required=False,
    )
    rerun = SurveyReportRerunRequest(teacher_id='teacher_1', reason='refresh')
    review_item = SurveyReviewQueueItemSummary(
        report_id='report_1',
        teacher_id='teacher_1',
        reason='low_confidence',
        confidence=0.41,
    )

    assert detail.report.report_id == 'report_1'
    assert detail.bundle_meta['parse_confidence'] == 0.86
    assert rerun.reason == 'refresh'
    assert review_item.reason == 'low_confidence'



def test_survey_settings_accessors_defaults(monkeypatch) -> None:
    monkeypatch.delenv('SURVEY_ANALYSIS_ENABLED', raising=False)
    monkeypatch.delenv('SURVEY_WEBHOOK_SECRET', raising=False)
    monkeypatch.delenv('SURVEY_SHADOW_MODE', raising=False)
    monkeypatch.delenv('SURVEY_MAX_ATTACHMENT_BYTES', raising=False)
    monkeypatch.delenv('SURVEY_REVIEW_CONFIDENCE_FLOOR', raising=False)
    monkeypatch.delenv('SURVEY_BETA_TEACHER_ALLOWLIST', raising=False)

    assert settings.survey_analysis_enabled() is False
    assert settings.survey_webhook_secret() == ''
    assert settings.survey_shadow_mode() is True
    assert settings.survey_max_attachment_bytes() >= 1024
    assert 0.0 <= settings.survey_review_confidence_floor() <= 1.0
    assert settings.survey_beta_teacher_allowlist_raw() == ''
    assert settings.survey_beta_teacher_allowlist() == []



def test_survey_settings_accessors_from_env(monkeypatch) -> None:
    monkeypatch.setenv('SURVEY_ANALYSIS_ENABLED', '1')
    monkeypatch.setenv('SURVEY_WEBHOOK_SECRET', 'secret-123')
    monkeypatch.setenv('SURVEY_SHADOW_MODE', '0')
    monkeypatch.setenv('SURVEY_MAX_ATTACHMENT_BYTES', '8192')
    monkeypatch.setenv('SURVEY_REVIEW_CONFIDENCE_FLOOR', '0.72')
    monkeypatch.setenv('SURVEY_BETA_TEACHER_ALLOWLIST', 'teacher_a, teacher_b\nteacher_c  teacher_b')

    assert settings.survey_analysis_enabled() is True
    assert settings.survey_webhook_secret() == 'secret-123'
    assert settings.survey_shadow_mode() is False
    assert settings.survey_max_attachment_bytes() == 8192
    assert settings.survey_review_confidence_floor() == 0.72
    assert settings.survey_beta_teacher_allowlist_raw() == 'teacher_a, teacher_b\nteacher_c  teacher_b'
    assert settings.survey_beta_teacher_allowlist() == ['teacher_a', 'teacher_b', 'teacher_c']
