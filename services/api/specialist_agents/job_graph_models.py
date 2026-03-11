from __future__ import annotations

from typing import Any, Dict, List, Literal

from pydantic import BaseModel, Field

from .contracts import HandoffContract, SpecialistAgentResult


class JobGraphNode(BaseModel):
    node_id: str
    node_type: Literal['extract', 'analyze', 'verify', 'merge'] = 'analyze'
    handoff: HandoffContract
    max_budget: Dict[str, float] = Field(default_factory=dict)
    allow_statuses: List[str] = Field(default_factory=lambda: ['completed'])


class SpecialistJobGraph(BaseModel):
    graph_id: str | None = None
    domain: str | None = None
    nodes: List[JobGraphNode] = Field(default_factory=list)
    max_nodes: int = 6


class SpecialistJobGraphResult(BaseModel):
    trace: List[str] = Field(default_factory=list)
    results: List[SpecialistAgentResult] = Field(default_factory=list)
    final_result: SpecialistAgentResult
    review_metadata: Dict[str, Any] = Field(default_factory=dict)
