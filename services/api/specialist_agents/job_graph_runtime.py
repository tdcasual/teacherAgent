from __future__ import annotations

from typing import Any, Callable, Dict

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
        results_by_node: Dict[str, Dict[str, Any]] = {}
        final_result: SpecialistAgentResult | None = None
        review_metadata: Dict[str, Any] = {}

        for node in request.nodes:
            prepared_handoff = self._prepare_handoff(node=node, trace=trace, results_by_node=results_by_node, results=results)
            trace.append(node.node_id)
            self._validate_node_budget(node=node, handoff=prepared_handoff)
            result = self._executor(prepared_handoff)
            if str(result.status or '').strip() not in set(node.allow_statuses or ['completed']):
                raise SpecialistAgentRuntimeError('specialist_execution_failed', 'job graph node returned unexpected status.')
            results.append(result)
            results_by_node[node.node_id] = result.model_dump()
            if node.node_type == 'verify' and _is_reviewer_result(result.output):
                review_metadata = dict(result.output or {})
                continue
            final_result = result

        resolved_final_result = final_result or results[-1]
        return SpecialistJobGraphResult(
            trace=trace,
            results=results,
            final_result=resolved_final_result,
            review_metadata=review_metadata,
        )

    def _prepare_handoff(
        self,
        *,
        node: JobGraphNode,
        trace: list[str],
        results_by_node: Dict[str, Dict[str, Any]],
        results: list[SpecialistAgentResult],
    ) -> HandoffContract:
        constraints = dict(node.handoff.constraints or {})
        if results:
            constraints['job_graph_previous_result'] = results[-1].model_dump()
            constraints['job_graph_results'] = dict(results_by_node)
            constraints['job_graph_trace'] = list(trace)
        return node.handoff.model_copy(update={'constraints': constraints})

    def _validate_node_budget(self, *, node: JobGraphNode, handoff: HandoffContract) -> None:
        for key in ('max_tokens', 'timeout_sec', 'max_steps'):
            allowed = (node.max_budget or {}).get(key)
            requested = getattr(handoff.budget, key)
            if allowed is None or requested is None:
                continue
            if float(requested) > float(allowed):
                raise SpecialistAgentRuntimeError('budget_exceeded', f'Job graph node budget exceeded for {key}.')



def _is_reviewer_result(output: Dict[str, Any]) -> bool:
    if not isinstance(output, dict):
        return False
    required_keys = {'approved', 'reason_codes', 'recommended_action', 'checked_sections'}
    return required_keys.issubset(output)
