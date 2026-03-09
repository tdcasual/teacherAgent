from __future__ import annotations

from collections import defaultdict
from typing import Any, DefaultDict, Dict, Optional

from .analysis_metrics_store import AnalysisMetricsStore
from .specialist_agents.events import SpecialistRuntimeEvent

_COUNTER_DEFAULTS = {
    'run_count': 0,
    'fail_count': 0,
    'timeout_count': 0,
    'invalid_output_count': 0,
    'review_downgrade_count': 0,
    'rerun_count': 0,
}
_RUNTIME_REASON_COUNTERS = {
    'timeout': 'timeout_count',
    'invalid_output': 'invalid_output_count',
}
_WORKFLOW_COUNTER_DEFAULTS = {
    'resolution_count': 0,
    'auto_selected_count': 0,
    'requested_rewritten_count': 0,
    'outcome_count': 0,
}


class AnalysisMetricsService:
    def __init__(self, *, store: Optional[AnalysisMetricsStore] = None) -> None:
        self._store = store
        self._counters: DefaultDict[str, int] = defaultdict(int)
        self._by_phase: DefaultDict[str, int] = defaultdict(int)
        self._by_reason: DefaultDict[str, int] = defaultdict(int)
        self._by_domain: DefaultDict[str, DefaultDict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._by_strategy: DefaultDict[str, DefaultDict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._by_agent: DefaultDict[str, DefaultDict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._workflow_counters: DefaultDict[str, int] = defaultdict(int)
        self._workflow_by_effective_skill: DefaultDict[str, DefaultDict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._workflow_by_role: DefaultDict[str, DefaultDict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._workflow_by_reason: DefaultDict[str, int] = defaultdict(int)
        self._workflow_by_resolution_mode: DefaultDict[str, int] = defaultdict(int)
        self._workflow_by_outcome: DefaultDict[str, int] = defaultdict(int)
        self._workflow_by_outcome_reason: DefaultDict[str, int] = defaultdict(int)
        self._restore_snapshot(self._load_persisted_snapshot())

    def record(self, event: SpecialistRuntimeEvent) -> None:
        normalized = SpecialistRuntimeEvent.model_validate(event)
        phase = self._bucket(normalized.phase)
        domain = self._bucket(normalized.domain)
        strategy_id = self._bucket(normalized.strategy_id)
        agent_id = self._bucket(normalized.agent_id)
        reason_code = self._reason_bucket(normalized.reason_code)

        self._increment_dimensions(
            phase=phase,
            domain=domain,
            strategy_id=strategy_id,
            agent_id=agent_id,
        )
        if phase == 'started':
            self._counters['run_count'] += 1
        if phase == 'failed':
            self._counters['fail_count'] += 1
        if reason_code:
            self._by_reason[reason_code] += 1
            counter_key = _RUNTIME_REASON_COUNTERS.get(reason_code)
            if counter_key:
                self._counters[counter_key] += 1
        self._persist()

    def record_review_downgrade(
        self,
        *,
        domain: str | None,
        strategy_id: str | None,
        agent_id: str | None = None,
        reason_code: str | None = None,
    ) -> None:
        self._record_auxiliary_phase(
            phase='review_downgraded',
            domain=domain,
            strategy_id=strategy_id,
            agent_id=agent_id,
            reason_code=reason_code,
            counter_key='review_downgrade_count',
        )
        self._persist()

    def record_rerun(
        self,
        *,
        domain: str | None,
        strategy_id: str | None,
        agent_id: str | None = None,
    ) -> None:
        self._record_auxiliary_phase(
            phase='rerun_requested',
            domain=domain,
            strategy_id=strategy_id,
            agent_id=agent_id,
            reason_code=None,
            counter_key='rerun_count',
        )
        self._persist()

    def record_workflow_resolution(
        self,
        *,
        role: str | None,
        requested_skill_id: str | None,
        effective_skill_id: str | None,
        reason: str | None,
        confidence: float | None = None,
        resolution_mode: str | None = None,
        auto_selected: bool = False,
        requested_rewritten: bool = False,
    ) -> None:
        del requested_skill_id, confidence
        effective = self._bucket(effective_skill_id)
        role_bucket = self._bucket(role)
        reason_bucket = self._bucket(reason)
        resolution_bucket = self._bucket(resolution_mode)
        self._workflow_counters['resolution_count'] += 1
        if auto_selected:
            self._workflow_counters['auto_selected_count'] += 1
        if requested_rewritten:
            self._workflow_counters['requested_rewritten_count'] += 1
        self._workflow_by_effective_skill[effective]['resolved'] += 1
        self._workflow_by_role[role_bucket]['resolved'] += 1
        self._workflow_by_reason[reason_bucket] += 1
        self._workflow_by_resolution_mode[resolution_bucket] += 1
        self._persist()

    def record_workflow_outcome(
        self,
        *,
        role: str | None,
        requested_skill_id: str | None,
        effective_skill_id: str | None,
        reason: str | None,
        resolution_mode: str | None = None,
        outcome: str | None,
        outcome_reason: str | None = None,
    ) -> None:
        del requested_skill_id, reason, resolution_mode
        effective = self._bucket(effective_skill_id)
        role_bucket = self._bucket(role)
        outcome_bucket = self._bucket(outcome)
        outcome_reason_bucket = self._bucket(outcome_reason)
        self._workflow_counters['outcome_count'] += 1
        self._workflow_by_effective_skill[effective][outcome_bucket] += 1
        self._workflow_by_role[role_bucket][outcome_bucket] += 1
        self._workflow_by_outcome[outcome_bucket] += 1
        self._workflow_by_outcome_reason[outcome_reason_bucket] += 1
        self._persist()

    def snapshot(self) -> Dict[str, Any]:
        counters = dict(_COUNTER_DEFAULTS)
        counters.update({key: int(value) for key, value in self._counters.items()})
        workflow_counters = dict(_WORKFLOW_COUNTER_DEFAULTS)
        workflow_counters.update({key: int(value) for key, value in self._workflow_counters.items()})
        return {
            'schema_version': 'v1',
            'counters': counters,
            'by_phase': dict(self._by_phase),
            'by_reason': dict(self._by_reason),
            'by_domain': {key: dict(value) for key, value in self._by_domain.items()},
            'by_strategy': {key: dict(value) for key, value in self._by_strategy.items()},
            'by_agent': {key: dict(value) for key, value in self._by_agent.items()},
            'workflow_routing': {
                'counters': workflow_counters,
                'by_effective_skill': {key: dict(value) for key, value in self._workflow_by_effective_skill.items()},
                'by_role': {key: dict(value) for key, value in self._workflow_by_role.items()},
                'by_reason': dict(self._workflow_by_reason),
                'by_resolution_mode': dict(self._workflow_by_resolution_mode),
                'by_outcome': dict(self._workflow_by_outcome),
                'by_outcome_reason': dict(self._workflow_by_outcome_reason),
            },
        }

    def _load_persisted_snapshot(self) -> Dict[str, Any]:
        if self._store is None:
            return {}
        loaded = self._store.load_snapshot()
        return loaded if isinstance(loaded, dict) else {}

    def _persist(self) -> None:
        if self._store is None:
            return
        self._store.save_snapshot(self.snapshot())

    def _restore_snapshot(self, snapshot: Dict[str, Any]) -> None:
        if not isinstance(snapshot, dict):
            return
        self._update_counter_map(self._counters, snapshot.get('counters'))
        self._update_counter_map(self._by_phase, snapshot.get('by_phase'))
        self._update_counter_map(self._by_reason, snapshot.get('by_reason'))
        self._update_nested_counter_map(self._by_domain, snapshot.get('by_domain'))
        self._update_nested_counter_map(self._by_strategy, snapshot.get('by_strategy'))
        self._update_nested_counter_map(self._by_agent, snapshot.get('by_agent'))
        workflow = snapshot.get('workflow_routing') if isinstance(snapshot.get('workflow_routing'), dict) else {}
        self._update_counter_map(self._workflow_counters, workflow.get('counters'))
        self._update_nested_counter_map(self._workflow_by_effective_skill, workflow.get('by_effective_skill'))
        self._update_nested_counter_map(self._workflow_by_role, workflow.get('by_role'))
        self._update_counter_map(self._workflow_by_reason, workflow.get('by_reason'))
        self._update_counter_map(self._workflow_by_resolution_mode, workflow.get('by_resolution_mode'))
        self._update_counter_map(self._workflow_by_outcome, workflow.get('by_outcome'))
        self._update_counter_map(self._workflow_by_outcome_reason, workflow.get('by_outcome_reason'))

    def _record_auxiliary_phase(
        self,
        *,
        phase: str,
        domain: str | None,
        strategy_id: str | None,
        agent_id: str | None,
        reason_code: str | None,
        counter_key: str,
    ) -> None:
        self._increment_dimensions(
            phase=phase,
            domain=self._bucket(domain),
            strategy_id=self._bucket(strategy_id),
            agent_id=self._bucket(agent_id),
        )
        self._counters[counter_key] += 1
        normalized_reason = self._reason_bucket(reason_code)
        if normalized_reason:
            self._by_reason[normalized_reason] += 1

    def _increment_dimensions(self, *, phase: str, domain: str, strategy_id: str, agent_id: str) -> None:
        self._by_phase[phase] += 1
        self._by_domain[domain][phase] += 1
        self._by_strategy[strategy_id][phase] += 1
        self._by_agent[agent_id][phase] += 1

    @staticmethod
    def _update_counter_map(target: DefaultDict[str, int], raw: Any) -> None:
        if not isinstance(raw, dict):
            return
        for key, value in raw.items():
            try:
                target[str(key)] = int(value)
            except Exception:
                continue

    @staticmethod
    def _update_nested_counter_map(
        target: DefaultDict[str, DefaultDict[str, int]],
        raw: Any,
    ) -> None:
        if not isinstance(raw, dict):
            return
        for outer_key, inner in raw.items():
            if not isinstance(inner, dict):
                continue
            bucket = target[str(outer_key)]
            for inner_key, value in inner.items():
                try:
                    bucket[str(inner_key)] = int(value)
                except Exception:
                    continue

    @staticmethod
    def _bucket(value: str | None) -> str:
        return str(value or '').strip() or 'unknown'

    @staticmethod
    def _reason_bucket(value: str | None) -> str | None:
        normalized = str(value or '').strip()
        return normalized or None
