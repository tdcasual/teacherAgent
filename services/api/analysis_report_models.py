from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AnalysisReportSummary(BaseModel):
    report_id: str
    analysis_type: str
    target_type: str
    target_id: str
    strategy_id: str
    teacher_id: str
    status: str
    confidence: Optional[float] = None
    summary: Optional[str] = None
    review_required: bool = False
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class AnalysisReportDetail(BaseModel):
    report: AnalysisReportSummary
    analysis_artifact: Dict[str, Any] = Field(default_factory=dict)
    artifact_meta: Dict[str, Any] = Field(default_factory=dict)


class AnalysisReviewQueueItemSummary(BaseModel):
    item_id: str
    domain: str
    report_id: str
    teacher_id: str
    status: str
    reason: str
    reason_code: Optional[str] = None
    disposition: Optional[str] = None
    reviewer_id: Optional[str] = None
    operator_note: Optional[str] = None
    confidence: Optional[float] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    claimed_at: Optional[str] = None
    resolved_at: Optional[str] = None
    rejected_at: Optional[str] = None
    dismissed_at: Optional[str] = None
    escalated_at: Optional[str] = None
    retried_at: Optional[str] = None


class AnalysisReviewQueueDomainSummary(BaseModel):
    domain: str
    total_items: int = 0
    unresolved_items: int = 0
    status_counts: Dict[str, int] = Field(default_factory=dict)
    reason_counts: Dict[str, int] = Field(default_factory=dict)


class AnalysisReviewQueueSummary(BaseModel):
    total_items: int = 0
    unresolved_items: int = 0
    status_counts: Dict[str, int] = Field(default_factory=dict)
    reason_counts: Dict[str, int] = Field(default_factory=dict)
    domains: List[AnalysisReviewQueueDomainSummary] = Field(default_factory=list)
    generated_at: Optional[str] = None
