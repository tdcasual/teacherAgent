from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from .contracts import HandoffContract, SpecialistAgentResult


class JobGraphNode(BaseModel):
    node_id: str
    handoff: HandoffContract


class SpecialistJobGraph(BaseModel):
    nodes: List[JobGraphNode] = Field(default_factory=list)
    max_nodes: int = 6


class SpecialistJobGraphResult(BaseModel):
    trace: List[str] = Field(default_factory=list)
    results: List[SpecialistAgentResult] = Field(default_factory=list)
    final_result: SpecialistAgentResult
