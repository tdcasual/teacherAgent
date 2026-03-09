from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from ..analysis_lineage_service import extract_analysis_lineage
from ..artifacts.contracts import ArtifactEnvelope
from ..specialist_agents.contracts import ArtifactRef, HandoffContract
from .contracts import StrategyDecision

_ARTIFACT_TYPE_BY_DOMAIN = {
    'survey': 'survey_evidence_bundle',
    'class_report': 'class_signal_bundle',
    'video_homework': 'multimodal_submission_bundle',
}


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
    prompt_version = str(getattr(strategy, 'prompt_version', 'v1') or 'v1').strip() or 'v1'
    runtime_version = str(getattr(strategy, 'runtime_version', 'v1') or 'v1').strip() or 'v1'
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
        'prompt_version': str(getattr(strategy, 'prompt_version', 'v1') or 'v1').strip() or 'v1',
        'adapter_version': str(getattr(artifact, 'adapter_version', 'v1') or 'v1').strip() or 'v1',
        'runtime_version': str(getattr(strategy, 'runtime_version', 'v1') or 'v1').strip() or 'v1',
    }



def build_replay_request(
    *,
    domain: str,
    report: Dict[str, Any],
    artifact_payload: Dict[str, Any],
    artifact_meta: Dict[str, Any] | None = None,
    analysis_artifact: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    report_payload = dict(report or {})
    lineage = {
        'report_id': str(report_payload.get('report_id') or '').strip(),
        'strategy_id': str(report_payload.get('strategy_id') or '').strip() or None,
        **extract_analysis_lineage(report_payload, strict=True),
    }
    domain_id = str(domain or report_payload.get('analysis_type') or '').strip() or 'unknown'
    return {
        'domain': domain_id,
        'report_id': str(report_payload.get('report_id') or '').strip(),
        'target': {
            'analysis_type': str(report_payload.get('analysis_type') or domain_id).strip() or domain_id,
            'target_type': str(report_payload.get('target_type') or 'report').strip() or 'report',
            'target_id': str(report_payload.get('target_id') or report_payload.get('report_id') or '').strip(),
        },
        'strategy_target': {
            'strategy_id': str(report_payload.get('strategy_id') or '').strip(),
            'strategy_version': str(report_payload.get('strategy_version') or '').strip() or 'v1',
            'prompt_version': str(report_payload.get('prompt_version') or '').strip() or 'v1',
            'adapter_version': str(report_payload.get('adapter_version') or '').strip() or 'v1',
            'runtime_version': str(report_payload.get('runtime_version') or '').strip() or 'v1',
        },
        'lineage': lineage,
        'artifact_type': _ARTIFACT_TYPE_BY_DOMAIN.get(domain_id, 'analysis_artifact'),
        'artifact_payload': dict(artifact_payload or {}),
        'artifact_meta': dict(artifact_meta or {}),
        'analysis_artifact': dict(analysis_artifact or {}),
    }
