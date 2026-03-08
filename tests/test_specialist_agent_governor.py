from __future__ import annotations

import pytest

from services.api.specialist_agents.contracts import HandoffContract, SpecialistAgentResult
from services.api.specialist_agents.governor import SpecialistAgentGovernor, SpecialistAgentRuntimeError
from services.api.specialist_agents.registry import SpecialistAgentSpec



def _spec() -> SpecialistAgentSpec:
    return SpecialistAgentSpec(
        agent_id='survey_analyst',
        display_name='Survey Analyst',
        roles=['teacher'],
        accepted_artifacts=['survey_evidence_bundle'],
        task_kinds=['survey.analysis'],
        direct_answer_capable=False,
        takeover_policy='coordinator_only',
        tool_allowlist=['llm.generate'],
        budgets={'default': {'max_tokens': 1600, 'timeout_sec': 5, 'max_steps': 2}},
        memory_policy='no_direct_memory_write',
        output_schema={'type': 'analysis_artifact'},
        evaluation_suite=['survey_v1_golden'],
    )



def _handoff(*, max_tokens: int = 800, timeout_sec: int = 5, max_steps: int = 2) -> HandoffContract:
    return HandoffContract(
        handoff_id='handoff_1',
        from_agent='coordinator',
        to_agent='survey_analyst',
        task_kind='survey.analysis',
        artifact_refs=[],
        goal='提炼班级洞察',
        constraints={},
        budget={'max_tokens': max_tokens, 'timeout_sec': timeout_sec, 'max_steps': max_steps},
        return_schema={'type': 'analysis_artifact'},
        status='prepared',
    )



def test_governor_records_prepared_started_and_completed_events() -> None:
    events = []
    governor = SpecialistAgentGovernor(event_sink=lambda event: events.append(event))

    result = governor.run(
        handoff=_handoff(),
        spec=_spec(),
        runner=lambda handoff: SpecialistAgentResult(
            handoff_id=handoff.handoff_id,
            agent_id=handoff.to_agent,
            status='completed',
            output={'executive_summary': 'ok'},
        ),
    )

    assert result.status == 'completed'
    assert [event.phase for event in events] == ['prepared', 'started', 'completed']
    assert events[-1].metadata['evaluation_suite'] == ['survey_v1_golden']



def test_governor_rejects_budget_over_spec_limit() -> None:
    governor = SpecialistAgentGovernor()

    with pytest.raises(SpecialistAgentRuntimeError) as exc_info:
        governor.run(
            handoff=_handoff(max_tokens=3200),
            spec=_spec(),
            runner=lambda handoff: SpecialistAgentResult(
                handoff_id=handoff.handoff_id,
                agent_id=handoff.to_agent,
                status='completed',
                output={'executive_summary': 'ok'},
            ),
        )

    assert exc_info.value.code == 'budget_exceeded'



def test_governor_times_out_when_elapsed_budget_is_exceeded() -> None:
    ticks = iter([0.0, 7.0])
    governor = SpecialistAgentGovernor(monotonic=lambda: next(ticks))

    with pytest.raises(SpecialistAgentRuntimeError) as exc_info:
        governor.run(
            handoff=_handoff(timeout_sec=5),
            spec=_spec(),
            runner=lambda handoff: SpecialistAgentResult(
                handoff_id=handoff.handoff_id,
                agent_id=handoff.to_agent,
                status='completed',
                output={'executive_summary': 'ok'},
            ),
        )

    assert exc_info.value.code == 'timeout'



def test_governor_sanitizes_runner_exception_without_traceback_leak() -> None:
    governor = SpecialistAgentGovernor()

    with pytest.raises(SpecialistAgentRuntimeError) as exc_info:
        governor.run(
            handoff=_handoff(),
            spec=_spec(),
            runner=lambda _handoff: (_ for _ in ()).throw(RuntimeError('Traceback: private stack detail')),
        )

    assert exc_info.value.code == 'specialist_execution_failed'
    assert 'Traceback' not in str(exc_info.value)



def test_governor_rejects_invalid_output_for_analysis_artifact_schema() -> None:
    governor = SpecialistAgentGovernor()

    with pytest.raises(SpecialistAgentRuntimeError) as exc_info:
        governor.run(
            handoff=_handoff(),
            spec=_spec(),
            runner=lambda handoff: SpecialistAgentResult(
                handoff_id=handoff.handoff_id,
                agent_id=handoff.to_agent,
                status='completed',
                output={},
            ),
        )

    assert exc_info.value.code == 'invalid_output'


def test_governor_emits_domain_and_strategy_context_in_events() -> None:
    events = []
    governor = SpecialistAgentGovernor(event_sink=lambda event: events.append(event))

    governor.run(
        handoff=HandoffContract(
            handoff_id='handoff_1',
            from_agent='coordinator',
            to_agent='survey_analyst',
            task_kind='survey.analysis',
            artifact_refs=[],
            goal='提炼班级洞察',
            constraints={},
            budget={'max_tokens': 800, 'timeout_sec': 5, 'max_steps': 2},
            return_schema={'type': 'analysis_artifact'},
            strategy_id='survey.teacher.report',
            status='prepared',
        ),
        spec=_spec(),
        runner=lambda handoff: SpecialistAgentResult(
            handoff_id=handoff.handoff_id,
            agent_id=handoff.to_agent,
            status='completed',
            output={'executive_summary': 'ok'},
        ),
    )

    assert events[-1].domain == 'survey'
    assert events[-1].strategy_id == 'survey.teacher.report'
