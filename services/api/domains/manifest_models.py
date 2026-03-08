from __future__ import annotations

from dataclasses import dataclass, field

from ..artifacts.registry import ArtifactAdapterSpec
from ..specialist_agents.registry import SpecialistAgentSpec
from ..strategies.contracts import StrategySpec


@dataclass(frozen=True)
class DomainRuntimeBinding:
    specialist_deps_factory: str
    payload_constraint_key: str
    teacher_context_constraint_key: str = 'teacher_context'


@dataclass(frozen=True)
class DomainManifest:
    domain_id: str
    display_name: str = ''
    artifact_adapters: list[ArtifactAdapterSpec] = field(default_factory=list)
    strategies: list[StrategySpec] = field(default_factory=list)
    specialists: list[SpecialistAgentSpec] = field(default_factory=list)
    runtime_binding: DomainRuntimeBinding | None = None
    rollout_stage: str = 'controlled'
    feature_flags: list[str] = field(default_factory=list)
