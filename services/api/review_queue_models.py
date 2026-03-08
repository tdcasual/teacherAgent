from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ReviewQueueItem(BaseModel):
    item_id: str
    domain: str
    report_id: str
    teacher_id: str
    target_type: str
    target_id: str
    status: str
    reason: str
    reason_code: Optional[str] = None
    confidence: Optional[float] = None
    operation: str = 'enqueue'
    reviewer_id: Optional[str] = None
    resolution_note: Optional[str] = None
    operator_note: Optional[str] = None
    disposition: str = 'open'
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    claimed_at: Optional[str] = None
    resolved_at: Optional[str] = None
    rejected_at: Optional[str] = None
    dismissed_at: Optional[str] = None
    escalated_at: Optional[str] = None
    retried_at: Optional[str] = None


class ReviewQueueDomainSummary(BaseModel):
    domain: str
    total_items: int = 0
    unresolved_items: int = 0
    status_counts: Dict[str, int] = Field(default_factory=dict)
    reason_counts: Dict[str, int] = Field(default_factory=dict)


class ReviewQueueSummary(BaseModel):
    total_items: int = 0
    unresolved_items: int = 0
    status_counts: Dict[str, int] = Field(default_factory=dict)
    reason_counts: Dict[str, int] = Field(default_factory=dict)
    domains: List[ReviewQueueDomainSummary] = Field(default_factory=list)
    generated_at: Optional[str] = None
