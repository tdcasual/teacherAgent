from __future__ import annotations

import pytest

from services.api.specialist_agents.contracts import HandoffContract, SpecialistAgentResult
from services.api.specialist_agents.registry import (
    SpecialistAgentNotFoundError,
    SpecialistAgentRegistry,
    SpecialistAgentSpec,
)
from services.api.specialist_agents.runtime import SpecialistAgentRuntime



def test_registry_registers_and_queries_specialist_agents() -> None:
    registry = SpecialistAgentRegistry()
    registry.register(
        SpecialistAgentSpec(
            agent_id="survey_analyst",
            display_name="Survey Analyst",
            roles=["teacher"],
            accepted_artifacts=["survey_evidence_bundle"],
            task_kinds=["survey.analysis"],
            direct_answer_capable=False,
            takeover_policy="coordinator_only",
            tool_allowlist=["llm.generate"],
            budgets={"default": {"max_tokens": 1600}},
            memory_policy="no_direct_memory_write",
            output_schema={"type": "analysis_artifact"},
            evaluation_suite=["survey_v1_golden"],
        ),
        runner=lambda handoff: SpecialistAgentResult(
            handoff_id=handoff.handoff_id,
            agent_id="survey_analyst",
            status="completed",
            output={"ok": True},
        ),
    )

    spec = registry.get("survey_analyst")
    matches = registry.find(artifact_type="survey_evidence_bundle", task_kind="survey.analysis")

    assert spec.agent_id == "survey_analyst"
    assert spec.takeover_policy == "coordinator_only"
    assert spec.budgets["default"]["max_tokens"] == 1600
    assert [item.agent_id for item in matches] == ["survey_analyst"]



def test_registry_raises_for_unknown_agent() -> None:
    registry = SpecialistAgentRegistry()

    with pytest.raises(SpecialistAgentNotFoundError):
        registry.get("missing")



def test_runtime_executes_registered_agent_through_uniform_interface() -> None:
    registry = SpecialistAgentRegistry()
    registry.register(
        SpecialistAgentSpec(
            agent_id="survey_analyst",
            display_name="Survey Analyst",
            roles=["teacher"],
            accepted_artifacts=["survey_evidence_bundle"],
            task_kinds=["survey.analysis"],
            direct_answer_capable=False,
            takeover_policy="coordinator_only",
            tool_allowlist=["llm.generate"],
            budgets={"default": {"max_tokens": 1600}},
            memory_policy="no_direct_memory_write",
            output_schema={"type": "analysis_artifact"},
            evaluation_suite=["survey_v1_golden"],
        ),
        runner=lambda handoff: SpecialistAgentResult(
            handoff_id=handoff.handoff_id,
            agent_id=handoff.to_agent,
            status="completed",
            output={"received_goal": handoff.goal},
        ),
    )
    runtime = SpecialistAgentRuntime(registry)
    handoff = HandoffContract(
        handoff_id="handoff_1",
        from_agent="coordinator",
        to_agent="survey_analyst",
        task_kind="survey.analysis",
        artifact_refs=[],
        goal="提炼班级洞察",
        constraints={},
        budget={"max_tokens": 800},
        return_schema={"type": "analysis_artifact"},
        status="prepared",
    )

    result = runtime.run(handoff)

    assert result.agent_id == "survey_analyst"
    assert result.output["received_goal"] == "提炼班级洞察"
