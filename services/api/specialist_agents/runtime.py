from __future__ import annotations

from .contracts import HandoffContract, SpecialistAgentResult
from .registry import SpecialistAgentRegistry


class SpecialistAgentRuntime:
    def __init__(self, registry: SpecialistAgentRegistry) -> None:
        self.registry = registry

    def run(self, handoff: HandoffContract) -> SpecialistAgentResult:
        request = HandoffContract.model_validate(handoff)
        runner = self.registry.get_runner(request.to_agent)
        result = runner(request)
        return SpecialistAgentResult.model_validate(result)
