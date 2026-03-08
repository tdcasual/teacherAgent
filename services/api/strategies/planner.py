from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from ..artifacts.contracts import ArtifactEnvelope
from ..specialist_agents.contracts import ArtifactRef, HandoffContract
from .contracts import StrategyDecision


@dataclass(frozen=True)
class HandoffPlan:
    strategy_id: str
    strategy_version: str
    prompt_version: str
    adapter_version: str
    runtime_version: str
    handoff: HandoffContract
    delivery_mode: str
    review_required: bool
    fallback_policy: str
    reason: str



def build_handoff_plan(
    *,
    strategy: StrategyDecision,
    artifact: ArtifactEnvelope,
    artifact_id: str,
    handoff_id: str,
    from_agent: str,
    goal: str,
    extra_constraints: Optional[Dict[str, Any]] = None,
    fallback_policy: str = 'none',
) -> HandoffPlan:
    prompt_version = 'v1'
    runtime_version = 'v1'
    constraints: Dict[str, Any] = {artifact.artifact_type: dict(artifact.payload or {})}
    if extra_constraints:
        constraints.update(dict(extra_constraints or {}))
    handoff = HandoffContract(
        handoff_id=handoff_id,
        from_agent=from_agent,
        to_agent=strategy.specialist_agent,
        task_kind=strategy.task_kind,
        strategy_id=strategy.strategy_id,
        artifact_refs=[
            ArtifactRef(
                artifact_id=str(artifact_id or '').strip(),
                artifact_type=artifact.artifact_type,
                version=artifact.schema_version,
            )
        ],
        goal=goal,
        constraints=constraints,
        budget=dict(strategy.budget or {}),
        return_schema=dict(strategy.return_schema or {}),
        prompt_version=prompt_version,
        runtime_version=runtime_version,
        status='prepared',
    )
    return HandoffPlan(
        strategy_id=strategy.strategy_id,
        strategy_version=str(strategy.strategy_version or 'v1').strip() or 'v1',
        prompt_version=prompt_version,
        adapter_version=str(getattr(artifact, 'adapter_version', 'v1') or 'v1').strip() or 'v1',
        runtime_version=runtime_version,
        handoff=handoff,
        delivery_mode=strategy.delivery_mode,
        review_required=bool(strategy.review_required),
        fallback_policy=str(fallback_policy or 'none'),
        reason=str(strategy.reason or 'selected'),
    )


def build_lineage_metadata(*, strategy: StrategyDecision, artifact: ArtifactEnvelope) -> Dict[str, str]:
    return {
        'strategy_version': str(strategy.strategy_version or 'v1').strip() or 'v1',
        'prompt_version': 'v1',
        'adapter_version': str(getattr(artifact, 'adapter_version', 'v1') or 'v1').strip() or 'v1',
        'runtime_version': 'v1',
    }
