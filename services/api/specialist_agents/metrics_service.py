from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass(frozen=True)
class SpecialistMetricsService:
    max_timeout_rate: float = 0.05
    max_invalid_output_rate: float = 0.05
    max_budget_rejection_rate: float = 0.02
    max_fallback_rate: float = 0.1

    def summarize(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        payload = dict(snapshot or {})
        counters = dict(payload.get('counters') or {})
        by_phase = dict(payload.get('by_phase') or {})

        run_count = int(counters.get('run_count') or 0)
        completed_count = int(by_phase.get('completed') or 0)
        fail_count = int(counters.get('fail_count') or 0)
        timeout_count = int(counters.get('timeout_count') or 0)
        invalid_output_count = int(counters.get('invalid_output_count') or 0)
        budget_rejection_count = int(counters.get('budget_rejection_count') or 0)
        fallback_count = int(counters.get('fallback_count') or 0)

        success_rate = _rate(completed_count, run_count)
        timeout_rate = _rate(timeout_count, run_count)
        invalid_output_rate = _rate(invalid_output_count, run_count)
        budget_rejection_rate = _rate(budget_rejection_count, run_count)
        fallback_rate = _rate(fallback_count, run_count)

        blocking_issues: List[Dict[str, Any]] = []
        if timeout_rate > float(self.max_timeout_rate):
            blocking_issues.append({'code': 'specialist_timeout_rate_exceeded', 'detail': f'timeout_rate={timeout_rate:.4f}'})
        if invalid_output_rate > float(self.max_invalid_output_rate):
            blocking_issues.append({'code': 'specialist_invalid_output_rate_exceeded', 'detail': f'invalid_output_rate={invalid_output_rate:.4f}'})
        if budget_rejection_rate > float(self.max_budget_rejection_rate):
            blocking_issues.append(
                {'code': 'specialist_budget_rejection_rate_exceeded', 'detail': f'budget_rejection_rate={budget_rejection_rate:.4f}'}
            )
        if fallback_rate > float(self.max_fallback_rate):
            blocking_issues.append({'code': 'specialist_fallback_rate_exceeded', 'detail': f'fallback_rate={fallback_rate:.4f}'})

        return {
            'schema_version': 'v1',
            'run_count': run_count,
            'completed_count': completed_count,
            'fail_count': fail_count,
            'timeout_count': timeout_count,
            'invalid_output_count': invalid_output_count,
            'budget_rejection_count': budget_rejection_count,
            'fallback_count': fallback_count,
            'success_rate': success_rate,
            'timeout_rate': timeout_rate,
            'invalid_output_rate': invalid_output_rate,
            'budget_rejection_rate': budget_rejection_rate,
            'fallback_rate': fallback_rate,
            'ready_for_release': len(blocking_issues) == 0,
            'blocking_issues': blocking_issues,
            'thresholds': {
                'max_timeout_rate': float(self.max_timeout_rate),
                'max_invalid_output_rate': float(self.max_invalid_output_rate),
                'max_budget_rejection_rate': float(self.max_budget_rejection_rate),
                'max_fallback_rate': float(self.max_fallback_rate),
            },
        }

    def summarize_grouped(self, grouped_snapshots: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        summaries: Dict[str, Dict[str, Any]] = {}
        for bucket, snapshot in dict(grouped_snapshots or {}).items():
            if not isinstance(snapshot, dict):
                continue
            summaries[str(bucket)] = self.summarize(snapshot)
        return summaries



def _rate(count: int, total: int) -> float:
    if int(total or 0) <= 0:
        return 0.0
    return round(float(count or 0) / float(total), 4)
