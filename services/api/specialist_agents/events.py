from __future__ import annotations

from typing import Any, Dict

from pydantic import BaseModel, Field, model_validator


class SpecialistRuntimeEvent(BaseModel):
    phase: str
    handoff_id: str
    agent_id: str
    task_kind: str
    domain: str | None = None
    strategy_id: str | None = None
    reason_code: str | None = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode='after')
    def sync_reason_code(self) -> 'SpecialistRuntimeEvent':
        reason_code = str(self.reason_code or '').strip() or str((self.metadata or {}).get('code') or '').strip() or None
        metadata = dict(self.metadata or {})
        if reason_code and not metadata.get('code'):
            metadata['code'] = reason_code
        self.reason_code = reason_code
        self.metadata = metadata
        return self
