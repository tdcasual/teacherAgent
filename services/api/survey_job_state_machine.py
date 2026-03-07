from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Set

_TRANSITIONS: Dict[str, Set[str]] = {
    "webhook_received": {"webhook_received", "intake_validated", "failed"},
    "intake_validated": {"intake_validated", "normalized", "failed"},
    "normalized": {"normalized", "bundle_ready", "review", "failed"},
    "bundle_ready": {"bundle_ready", "analysis_running", "review", "failed"},
    "analysis_running": {"analysis_running", "analysis_ready", "review", "failed"},
    "analysis_ready": {"analysis_ready", "teacher_notified", "review", "failed"},
    "teacher_notified": {"teacher_notified"},
    "review": {"review"},
    "failed": {"failed"},
}

_TERMINAL_STATUSES = {"teacher_notified", "review", "failed"}



def normalize_survey_job_status(status: object) -> str:
    text = str(status or "").strip().lower()
    return text or "webhook_received"



def is_terminal_survey_job_status(status: object) -> bool:
    return normalize_survey_job_status(status) in _TERMINAL_STATUSES


@dataclass
class SurveyJobStateMachine:
    status: str

    def __post_init__(self) -> None:
        self.status = normalize_survey_job_status(self.status)

    def transition(self, next_status: object) -> str:
        target = normalize_survey_job_status(next_status)
        allowed = _TRANSITIONS.get(self.status)
        if not allowed or target not in allowed:
            raise ValueError(f"invalid_survey_job_transition:{self.status}->{target}")
        self.status = target
        return self.status



def transition_survey_job_status(current_status: object, target_status: object) -> str:
    sm = SurveyJobStateMachine(normalize_survey_job_status(current_status))
    return sm.transition(target_status)
