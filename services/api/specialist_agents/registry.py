from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List

from .contracts import HandoffContract, SpecialistAgentResult


class SpecialistAgentNotFoundError(KeyError):
    pass


@dataclass(frozen=True)
class SpecialistAgentSpec:
    agent_id: str
    display_name: str
    roles: List[str] = field(default_factory=list)
    accepted_artifacts: List[str] = field(default_factory=list)
    task_kinds: List[str] = field(default_factory=list)
    direct_answer_capable: bool = False
    takeover_policy: str = "coordinator_only"
    tool_allowlist: List[str] = field(default_factory=list)
    budgets: Dict[str, Any] = field(default_factory=dict)
    memory_policy: str = "no_direct_memory_write"
    output_schema: Dict[str, Any] = field(default_factory=dict)
    evaluation_suite: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class RegisteredSpecialistAgent:
    spec: SpecialistAgentSpec
    runner: Callable[[HandoffContract], SpecialistAgentResult]


class SpecialistAgentRegistry:
    def __init__(self) -> None:
        self._entries: Dict[str, RegisteredSpecialistAgent] = {}

    def register(
        self,
        spec: SpecialistAgentSpec,
        *,
        runner: Callable[[HandoffContract], SpecialistAgentResult],
    ) -> None:
        self._entries[spec.agent_id] = RegisteredSpecialistAgent(spec=spec, runner=runner)

    def get(self, agent_id: str) -> SpecialistAgentSpec:
        entry = self._entries.get(str(agent_id or "").strip())
        if entry is None:
            raise SpecialistAgentNotFoundError(str(agent_id or ""))
        return entry.spec

    def get_entry(self, agent_id: str) -> RegisteredSpecialistAgent:
        entry = self._entries.get(str(agent_id or "").strip())
        if entry is None:
            raise SpecialistAgentNotFoundError(str(agent_id or ""))
        return entry

    def get_runner(self, agent_id: str) -> Callable[[HandoffContract], SpecialistAgentResult]:
        entry = self._entries.get(str(agent_id or "").strip())
        if entry is None:
            raise SpecialistAgentNotFoundError(str(agent_id or ""))
        return entry.runner

    def find(self, *, artifact_type: str, task_kind: str) -> List[SpecialistAgentSpec]:
        artifact_type_final = str(artifact_type or "").strip()
        task_kind_final = str(task_kind or "").strip()
        matches: List[SpecialistAgentSpec] = []
        for entry in self._entries.values():
            spec = entry.spec
            if artifact_type_final not in spec.accepted_artifacts:
                continue
            if task_kind_final not in spec.task_kinds:
                continue
            matches.append(spec)
        matches.sort(key=lambda item: item.agent_id)
        return matches
