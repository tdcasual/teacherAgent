from __future__ import annotations

import pytest

from services.api.specialist_agents.contracts import HandoffContract, SpecialistAgentResult
from services.api.specialist_agents.governor import SpecialistAgentGovernor, SpecialistAgentRuntimeError
from services.api.specialist_agents.registry import SpecialistAgentRegistry, SpecialistAgentSpec
from services.api.specialist_agents.runtime import SpecialistAgentRuntime



def _handoff(max_tokens: int = 800) -> HandoffContract:
    return HandoffContract(
        handoff_id='handoff_1',
        from_agent='coordinator',
        to_agent='survey_analyst',
        task_kind='survey.analysis',
        artifact_refs=[],
        goal='提炼班级洞察',
        constraints={},
        budget={'max_tokens': max_tokens, 'timeout_sec': 5, 'max_steps': 2},
        return_schema={'type': 'analysis_artifact'},
        status='prepared',
    )



def test_runtime_executes_registered_agent_via_governor() -> None:
    registry = SpecialistAgentRegistry()
    events = []
    registry.register(
        SpecialistAgentSpec(
            agent_id='survey_analyst',
            display_name='Survey Analyst',
            roles=['teacher'],
            accepted_artifacts=['survey_evidence_bundle'],
            task_kinds=['survey.analysis'],
            budgets={'default': {'max_tokens': 1600, 'timeout_sec': 5, 'max_steps': 2}},
            output_schema={'type': 'analysis_artifact'},
            evaluation_suite=['survey_v1_golden'],
        ),
        runner=lambda handoff: SpecialistAgentResult(
            handoff_id=handoff.handoff_id,
            agent_id=handoff.to_agent,
            status='completed',
            output={'executive_summary': handoff.goal},
        ),
    )
    runtime = SpecialistAgentRuntime(registry, governor=SpecialistAgentGovernor(event_sink=lambda event: events.append(event)))

    result = runtime.run(_handoff())

    assert result.output['executive_summary'] == '提炼班级洞察'
    assert events[-1].phase == 'completed'



def test_runtime_raises_sanitized_governor_error_on_budget_violation() -> None:
    registry = SpecialistAgentRegistry()
    registry.register(
        SpecialistAgentSpec(
            agent_id='survey_analyst',
            display_name='Survey Analyst',
            roles=['teacher'],
            accepted_artifacts=['survey_evidence_bundle'],
            task_kinds=['survey.analysis'],
            budgets={'default': {'max_tokens': 100, 'timeout_sec': 5, 'max_steps': 2}},
            output_schema={'type': 'analysis_artifact'},
            evaluation_suite=['survey_v1_golden'],
        ),
        runner=lambda handoff: SpecialistAgentResult(
            handoff_id=handoff.handoff_id,
            agent_id=handoff.to_agent,
            status='completed',
            output={'executive_summary': 'ok'},
        ),
    )
    runtime = SpecialistAgentRuntime(registry)

    with pytest.raises(SpecialistAgentRuntimeError) as exc_info:
        runtime.run(_handoff(max_tokens=200))

    assert exc_info.value.code == 'budget_exceeded'
