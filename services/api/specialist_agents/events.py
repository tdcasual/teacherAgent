from __future__ import annotations

from typing import Any, Dict

from pydantic import BaseModel, Field


class SpecialistRuntimeEvent(BaseModel):
    phase: str
    handoff_id: str
    agent_id: str
    task_kind: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
