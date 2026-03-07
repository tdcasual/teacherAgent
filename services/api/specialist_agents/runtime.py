from __future__ import annotations

from .contracts import HandoffContract, SpecialistAgentResult
from .governor import SpecialistAgentGovernor
from .registry import SpecialistAgentRegistry


class SpecialistAgentRuntime:
    def __init__(self, registry: SpecialistAgentRegistry, governor: SpecialistAgentGovernor | None = None) -> None:
        self.registry = registry
        self.governor = governor or SpecialistAgentGovernor()

    def run(self, handoff: HandoffContract) -> SpecialistAgentResult:
        request = HandoffContract.model_validate(handoff)
        entry = self.registry.get_entry(request.to_agent)
        return self.governor.run(handoff=request, spec=entry.spec, runner=entry.runner)
