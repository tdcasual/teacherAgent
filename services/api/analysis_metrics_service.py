from __future__ import annotations

from collections import defaultdict
from typing import DefaultDict, Dict

from .specialist_agents.events import SpecialistRuntimeEvent


class AnalysisMetricsService:
    def __init__(self) -> None:
        self._by_phase: DefaultDict[str, int] = defaultdict(int)
        self._by_reason: DefaultDict[str, int] = defaultdict(int)
        self._by_domain: DefaultDict[str, DefaultDict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._by_strategy: DefaultDict[str, DefaultDict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._by_agent: DefaultDict[str, DefaultDict[str, int]] = defaultdict(lambda: defaultdict(int))

    def record(self, event: SpecialistRuntimeEvent) -> None:
        normalized = SpecialistRuntimeEvent.model_validate(event)
        phase = str(normalized.phase or '').strip() or 'unknown'
        self._by_phase[phase] += 1

        domain = str(normalized.domain or '').strip()
        if domain:
            self._by_domain[domain][phase] += 1

        strategy_id = str(normalized.strategy_id or '').strip()
        if strategy_id:
            self._by_strategy[strategy_id][phase] += 1

        agent_id = str(normalized.agent_id or '').strip()
        if agent_id:
            self._by_agent[agent_id][phase] += 1

        reason = str((normalized.metadata or {}).get('code') or '').strip()
        if reason:
            self._by_reason[reason] += 1

    def snapshot(self) -> Dict[str, Dict]:
        return {
            'by_phase': dict(self._by_phase),
            'by_reason': dict(self._by_reason),
            'by_domain': {key: dict(value) for key, value in self._by_domain.items()},
            'by_strategy': {key: dict(value) for key, value in self._by_strategy.items()},
            'by_agent': {key: dict(value) for key, value in self._by_agent.items()},
        }
