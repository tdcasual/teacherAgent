from __future__ import annotations

from typing import Any, Dict, Optional

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
    confidence: Optional[float] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
