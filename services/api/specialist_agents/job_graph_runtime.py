from __future__ import annotations

from typing import Callable

from .contracts import HandoffContract, SpecialistAgentResult
from .job_graph_models import SpecialistJobGraph, SpecialistJobGraphResult


class SpecialistJobGraphRuntime:
    def __init__(self, *, executor: Callable[[HandoffContract], SpecialistAgentResult]) -> None:
        self._executor = executor

    def run(self, graph: SpecialistJobGraph) -> SpecialistJobGraphResult:
        request = SpecialistJobGraph.model_validate(graph)
        if len(request.nodes) > int(request.max_nodes or 0):
            raise ValueError('job graph exceeds max_nodes')
        if not request.nodes:
            raise ValueError('job graph requires at least one node')

        trace: list[str] = []
        results: list[SpecialistAgentResult] = []
        for node in request.nodes:
            trace.append(node.node_id)
            results.append(self._executor(node.handoff))
        return SpecialistJobGraphResult(trace=trace, results=results, final_result=results[-1])
