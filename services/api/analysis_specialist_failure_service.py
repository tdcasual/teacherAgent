from __future__ import annotations

from dataclasses import dataclass

from .specialist_agents.governor import SpecialistAgentRuntimeError

_REVIEWABLE_FAILURE_CODES = {'invalid_output', 'timeout', 'specialist_execution_failed'}


@dataclass(frozen=True)
class SpecialistFailureDecision:
    action: str
    reason: str
    error: str


def classify_specialist_failure(exc: SpecialistAgentRuntimeError) -> SpecialistFailureDecision:
    code = str(getattr(exc, 'code', '') or 'specialist_execution_failed').strip() or 'specialist_execution_failed'
    error = str(exc or code).strip() or code
    if code in _REVIEWABLE_FAILURE_CODES:
        return SpecialistFailureDecision(action='review', reason=code, error=error[:200])
    return SpecialistFailureDecision(action='fail', reason=code, error=error[:200])
