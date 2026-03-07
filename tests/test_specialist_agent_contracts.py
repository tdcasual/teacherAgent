from __future__ import annotations

from services.api.specialist_agents.contracts import (
    AgentExecutionBudget,
    ArtifactRef,
    HandoffContract,
    SpecialistAgentResult,
)



def test_handoff_contract_and_result_roundtrip() -> None:
    handoff = HandoffContract(
        handoff_id="handoff_1",
        from_agent="coordinator",
        to_agent="survey_analyst",
        task_kind="survey.analysis",
        artifact_refs=[
            ArtifactRef(
                artifact_id="bundle_1",
                artifact_type="survey_evidence_bundle",
                uri="survey://bundle/1",
                version="v1",
            )
        ],
        goal="输出班级问卷洞察和教学建议",
        constraints={"disallow_student_list": True},
        budget=AgentExecutionBudget(max_tokens=1600, timeout_sec=45, max_steps=2),
        return_schema={"type": "analysis_artifact"},
        status="prepared",
    )
    result = SpecialistAgentResult(
        handoff_id="handoff_1",
        agent_id="survey_analyst",
        status="completed",
        output={"executive_summary": "班级整体在实验设计题上失分较多"},
        confidence=0.83,
        artifacts=[ArtifactRef(artifact_id="analysis_1", artifact_type="analysis_artifact")],
    )

    assert handoff.artifact_refs[0].artifact_type == "survey_evidence_bundle"
    assert handoff.budget.max_steps == 2
    assert result.output["executive_summary"].startswith("班级整体")
    assert result.artifacts[0].artifact_type == "analysis_artifact"
