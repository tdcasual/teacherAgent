from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ArtifactRef(BaseModel):
    artifact_id: str
    artifact_type: str
    uri: Optional[str] = None
    version: Optional[str] = None


class AgentExecutionBudget(BaseModel):
    max_tokens: Optional[int] = None
    timeout_sec: Optional[int] = None
    max_steps: Optional[int] = None


class HandoffContract(BaseModel):
    handoff_id: str
    from_agent: str
    to_agent: str
    task_kind: str
    artifact_refs: List[ArtifactRef] = Field(default_factory=list)
    goal: str
    constraints: Dict[str, Any] = Field(default_factory=dict)
    budget: AgentExecutionBudget = Field(default_factory=AgentExecutionBudget)
    return_schema: Dict[str, Any] = Field(default_factory=dict)
    status: str = "prepared"


class SpecialistAgentResult(BaseModel):
    handoff_id: str
    agent_id: str
    status: str
    output: Dict[str, Any] = Field(default_factory=dict)
    confidence: Optional[float] = None
    artifacts: List[ArtifactRef] = Field(default_factory=list)
