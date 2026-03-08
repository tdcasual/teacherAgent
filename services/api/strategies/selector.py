from __future__ import annotations

from typing import Any, Iterable, List, Optional

from .. import settings
from ..artifacts.contracts import ArtifactEnvelope
from .contracts import StrategyDecision, StrategySpec


class StrategySelectionError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class StrategySelector:
    def __init__(
        self,
        specs: Iterable[StrategySpec],
        *,
        disabled_strategy_ids: Iterable[str] | None = None,
    ):
        self._specs = list(specs)
        self._disabled_strategy_ids = {
            str(strategy_id or '').strip().lower()
            for strategy_id in list(disabled_strategy_ids or [])
            if str(strategy_id or '').strip()
        }

    def select(
        self,
        *,
        role: str,
        artifact: ArtifactEnvelope,
        task_kind: str,
        target_scope: Optional[str] = None,
        force_review_only: bool = False,
    ) -> StrategyDecision:
        role_final = str(role or '').strip()
        task_kind_final = str(task_kind or '').strip()
        target_scope_final = str(target_scope or '').strip() or None
        matches: List[StrategySpec] = []
        for spec in self._specs:
            if spec.roles and role_final not in spec.roles:
                continue
            if artifact.artifact_type not in spec.accepted_artifacts:
                continue
            if task_kind_final not in spec.task_kinds:
                continue
            if spec.target_scopes and target_scope_final not in spec.target_scopes:
                continue
            matches.append(spec)

        if not matches:
            raise StrategySelectionError(
                'unsupported_strategy',
                f'No strategy for {artifact.artifact_type}:{task_kind_final}:{role_final}',
            )

        spec = sorted(
            matches,
            key=lambda item: (
                1 if item.target_scopes else 0,
                len(item.task_kinds),
                1 if item.confidence_floor is not None else 0,
            ),
            reverse=True,
        )[0]
        strategy_id = str(spec.strategy_id or '').strip()
        if strategy_id.lower() in self._disabled_strategy_ids:
            raise StrategySelectionError('strategy_disabled', f'Strategy disabled: {strategy_id}')

        confidence = artifact.confidence
        review_required = spec.review_policy == 'always_review'
        delivery_mode = spec.delivery_mode
        reason = 'selected'
        if force_review_only:
            review_required = True
            delivery_mode = 'review_queue'
            reason = 'domain_review_only'
        elif (
            spec.review_policy == 'auto_on_low_confidence'
            and spec.confidence_floor is not None
            and confidence is not None
            and float(confidence) < float(spec.confidence_floor)
        ):
            review_required = True
            delivery_mode = 'review_queue'
            reason = 'low_confidence_review'

        return StrategyDecision(
            strategy_id=strategy_id,
            strategy_version=str(spec.strategy_version or 'v1').strip() or 'v1',
            specialist_agent=spec.specialist_agent,
            task_kind=task_kind_final,
            review_policy=spec.review_policy,
            delivery_mode=delivery_mode,
            review_required=review_required,
            reason=reason,
            budget=dict(spec.budget or {}),
            return_schema=dict(spec.return_schema or {}),
        )



def build_default_strategy_selector(
    review_confidence_floor: float = 0.7,
    *,
    manifest_registry: Any | None = None,
    disabled_strategy_ids: Iterable[str] | None = None,
) -> StrategySelector:
    if manifest_registry is None:
        from ..domains.manifest_registry import build_default_domain_manifest_registry

        manifest_registry = build_default_domain_manifest_registry(review_confidence_floor)
    if disabled_strategy_ids is None:
        disabled_strategy_ids = settings.analysis_disabled_strategies()
    specs = [spec for manifest in manifest_registry.list() for spec in manifest.strategies]
    return StrategySelector(specs, disabled_strategy_ids=disabled_strategy_ids)
