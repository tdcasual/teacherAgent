from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class StrategySpec:
    strategy_id: str
    accepted_artifacts: List[str] = field(default_factory=list)
    task_kinds: List[str] = field(default_factory=list)
    specialist_agent: str = ''
    review_policy: str = 'none'
    delivery_mode: str = 'teacher_report'
    roles: List[str] = field(default_factory=list)
    target_scopes: List[str] = field(default_factory=list)
    confidence_floor: Optional[float] = None
    budget: Dict[str, Any] = field(default_factory=dict)
    return_schema: Dict[str, Any] = field(default_factory=lambda: {'type': 'analysis_artifact'})


@dataclass(frozen=True)
class StrategyDecision:
    strategy_id: str
    specialist_agent: str
    task_kind: str
    review_policy: str
    delivery_mode: str
    review_required: bool
    reason: str
    budget: Dict[str, Any] = field(default_factory=dict)
    return_schema: Dict[str, Any] = field(default_factory=dict)
