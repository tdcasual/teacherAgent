from __future__ import annotations

from typing import Callable

from .contracts import HandoffContract, SpecialistAgentResult
from .governor import SpecialistAgentRuntimeError
from .job_graph_models import JobGraphNode, SpecialistJobGraph, SpecialistJobGraphResult


class SpecialistJobGraphRuntime:
    def __init__(self, *, executor: Callable[[HandoffContract], SpecialistAgentResult]) -> None:
        self._executor = executor

    def run(self, graph: SpecialistJobGraph) -> SpecialistJobGraphResult:
        request = SpecialistJobGraph.model_validate(graph)
        if len(request.nodes) > int(request.max_nodes or 0):
            raise ValueError('job graph exceeds max_nodes')
        if not request.nodes:
            raise ValueError('job graph requires at least one node')
        node_ids = [str(node.node_id or '').strip() for node in request.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError('job graph node_id must be unique')

        trace: list[str] = []
        results: list[SpecialistAgentResult] = []
        for node in request.nodes:
            trace.append(node.node_id)
            self._validate_node_budget(node)
            result = self._executor(node.handoff)
            if str(result.status or '').strip() not in set(node.allow_statuses or ['completed']):
                raise SpecialistAgentRuntimeError('specialist_execution_failed', 'job graph node returned unexpected status.')
            results.append(result)
        return SpecialistJobGraphResult(trace=trace, results=results, final_result=results[-1])

    def _validate_node_budget(self, node: JobGraphNode) -> None:
        for key in ('max_tokens', 'timeout_sec', 'max_steps'):
            allowed = (node.max_budget or {}).get(key)
            requested = getattr(node.handoff.budget, key)
            if allowed is None or requested is None:
                continue
            if float(requested) > float(allowed):
                raise SpecialistAgentRuntimeError('budget_exceeded', f'Job graph node budget exceeded for {key}.')
