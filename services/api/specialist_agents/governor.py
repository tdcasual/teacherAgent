from __future__ import annotations

import time
from typing import Callable, Optional

from .contracts import HandoffContract, SpecialistAgentResult
from .events import SpecialistRuntimeEvent
from .registry import SpecialistAgentSpec


class SpecialistAgentRuntimeError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class SpecialistAgentGovernor:
    def __init__(
        self,
        *,
        event_sink: Optional[Callable[[SpecialistRuntimeEvent], None]] = None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._event_sink = event_sink
        self._monotonic = monotonic

    def run(
        self,
        *,
        handoff: HandoffContract,
        spec: SpecialistAgentSpec,
        runner,
    ) -> SpecialistAgentResult:
        request = HandoffContract.model_validate(handoff)
        self._emit('prepared', request, spec)
        self._validate_budget(request, spec)
        self._emit('started', request, spec)
        started_at = self._monotonic()
        try:
            raw_result = runner(request)
        except Exception:
            self._emit('failed', request, spec, metadata={'code': 'specialist_execution_failed'})
            raise SpecialistAgentRuntimeError('specialist_execution_failed', 'Specialist agent execution failed.') from None
        elapsed_sec = self._monotonic() - started_at
        timeout_sec = request.budget.timeout_sec or ((spec.budgets.get('default') or {}).get('timeout_sec'))
        if timeout_sec is not None and float(elapsed_sec) > float(timeout_sec):
            self._emit('failed', request, spec, metadata={'code': 'timeout', 'elapsed_sec': round(float(elapsed_sec), 4)})
            raise SpecialistAgentRuntimeError('timeout', 'Specialist agent timed out.')
        result = SpecialistAgentResult.model_validate(raw_result)
        self._validate_output(spec, result)
        self._emit(
            'completed',
            request,
            spec,
            metadata={
                'elapsed_sec': round(float(elapsed_sec), 4),
                'evaluation_suite': list(spec.evaluation_suite or []),
                'status': result.status,
            },
        )
        return result

    def _validate_budget(self, handoff: HandoffContract, spec: SpecialistAgentSpec) -> None:
        default_budget = dict(spec.budgets.get('default') or {})
        for key in ('max_tokens', 'timeout_sec', 'max_steps'):
            requested = getattr(handoff.budget, key)
            allowed = default_budget.get(key)
            if requested is None or allowed is None:
                continue
            if float(requested) > float(allowed):
                self._emit('failed', handoff, spec, metadata={'code': 'budget_exceeded', 'budget_field': key})
                raise SpecialistAgentRuntimeError('budget_exceeded', f'Specialist budget exceeded for {key}.')

    def _validate_output(self, spec: SpecialistAgentSpec, result: SpecialistAgentResult) -> None:
        schema_type = str((spec.output_schema or {}).get('type') or '').strip()
        if schema_type and not dict(result.output or {}):
            raise SpecialistAgentRuntimeError('invalid_output', 'Specialist output did not satisfy required schema.')

    def _emit(
        self,
        phase: str,
        handoff: HandoffContract,
        spec: SpecialistAgentSpec,
        *,
        metadata: Optional[dict] = None,
    ) -> None:
        if not callable(self._event_sink):
            return
        self._event_sink(
            SpecialistRuntimeEvent(
                phase=phase,
                handoff_id=handoff.handoff_id,
                agent_id=spec.agent_id,
                task_kind=handoff.task_kind,
                metadata=dict(metadata or {}),
            )
        )
