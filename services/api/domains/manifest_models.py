from __future__ import annotations

from dataclasses import dataclass, field

from ..artifacts.registry import ArtifactAdapterSpec
from ..specialist_agents.registry import SpecialistAgentSpec
from ..strategies.contracts import StrategySpec


@dataclass(frozen=True)
class DomainManifest:
    domain_id: str
    display_name: str = ''
    artifact_adapters: list[ArtifactAdapterSpec] = field(default_factory=list)
    strategies: list[StrategySpec] = field(default_factory=list)
    specialists: list[SpecialistAgentSpec] = field(default_factory=list)
    rollout_stage: str = 'controlled'
    feature_flags: list[str] = field(default_factory=list)
