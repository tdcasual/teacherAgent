from __future__ import annotations

import pytest

from services.api.specialist_agents.contracts import HandoffContract, SpecialistAgentResult
from services.api.specialist_agents.governor import SpecialistAgentRuntimeError
from services.api.specialist_agents.job_graph_models import JobGraphNode, SpecialistJobGraph
from services.api.specialist_agents.job_graph_runtime import SpecialistJobGraphRuntime


def _handoff(node_id: str) -> HandoffContract:
    return HandoffContract(
        handoff_id=node_id,
        from_agent='coordinator',
        to_agent='video_homework_analyst',
        task_kind='video_homework.analysis',
        strategy_id='video_homework.teacher.report',
        artifact_refs=[],
        goal='生成视频作业分析',
        constraints={},
        budget={'max_tokens': 800, 'timeout_sec': 5, 'max_steps': 2},
        return_schema={'type': 'analysis_artifact'},
        status='prepared',
    )



def test_job_graph_runtime_executes_nodes_in_order() -> None:
    runtime = SpecialistJobGraphRuntime(
        executor=lambda handoff: SpecialistAgentResult(
            handoff_id=handoff.handoff_id,
            agent_id=handoff.to_agent,
            status='completed',
            output={'executive_summary': handoff.handoff_id},
        )
    )
    graph = SpecialistJobGraph(
        nodes=[
            JobGraphNode(node_id='extract', handoff=_handoff('extract')),
            JobGraphNode(node_id='analyze', handoff=_handoff('analyze')),
            JobGraphNode(node_id='verify', handoff=_handoff('verify')),
        ]
    )

    result = runtime.run(graph)

    assert result.trace == ['extract', 'analyze', 'verify']
    assert result.final_result.output['executive_summary'] == 'verify'



def test_job_graph_runtime_stops_on_invalid_verify_step() -> None:
    def _executor(handoff: HandoffContract) -> SpecialistAgentResult:
        if handoff.handoff_id == 'verify':
            raise SpecialistAgentRuntimeError('invalid_output', 'Specialist output did not satisfy required schema.')
        return SpecialistAgentResult(
            handoff_id=handoff.handoff_id,
            agent_id=handoff.to_agent,
            status='completed',
            output={'executive_summary': handoff.handoff_id},
        )

    runtime = SpecialistJobGraphRuntime(executor=_executor)
    graph = SpecialistJobGraph(
        nodes=[
            JobGraphNode(node_id='extract', handoff=_handoff('extract')),
            JobGraphNode(node_id='verify', handoff=_handoff('verify')),
        ]
    )

    with pytest.raises(SpecialistAgentRuntimeError) as exc_info:
        runtime.run(graph)

    assert exc_info.value.code == 'invalid_output'


def test_job_graph_runtime_rejects_node_budget_over_cap() -> None:
    runtime = SpecialistJobGraphRuntime(
        executor=lambda handoff: SpecialistAgentResult(
            handoff_id=handoff.handoff_id,
            agent_id=handoff.to_agent,
            status='completed',
            output={'executive_summary': handoff.handoff_id},
        )
    )
    graph = SpecialistJobGraph(
        graph_id='video_homework.teacher.report',
        domain='video_homework',
        nodes=[
            JobGraphNode(
                node_id='analyze',
                node_type='analyze',
                max_budget={'max_tokens': 400},
                handoff=_handoff('analyze'),
            )
        ],
    )

    with pytest.raises(SpecialistAgentRuntimeError) as exc_info:
        runtime.run(graph)

    assert exc_info.value.code == 'budget_exceeded'
