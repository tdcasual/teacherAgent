from __future__ import annotations

import pytest

from services.api.survey_job_state_machine import (
    SurveyJobStateMachine,
    is_terminal_survey_job_status,
    normalize_survey_job_status,
    transition_survey_job_status,
)


def test_survey_job_state_machine_allows_happy_path() -> None:
    sm = SurveyJobStateMachine("webhook_received")
    assert sm.transition("intake_validated") == "intake_validated"
    assert sm.transition("normalized") == "normalized"
    assert sm.transition("bundle_ready") == "bundle_ready"
    assert sm.transition("analysis_running") == "analysis_running"
    assert sm.transition("analysis_ready") == "analysis_ready"
    assert sm.transition("teacher_notified") == "teacher_notified"
    assert is_terminal_survey_job_status(sm.status) is True


def test_survey_job_state_machine_rejects_invalid_transition() -> None:
    with pytest.raises(ValueError, match="invalid_survey_job_transition"):
        transition_survey_job_status("webhook_received", "analysis_running")


def test_survey_job_state_machine_allows_review_and_failed_terminal_paths() -> None:
    assert transition_survey_job_status("bundle_ready", "review") == "review"
    assert transition_survey_job_status("analysis_running", "failed") == "failed"
    assert normalize_survey_job_status("  ANALYSIS_READY ") == "analysis_ready"
