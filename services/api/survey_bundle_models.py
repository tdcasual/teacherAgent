from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SurveyMeta(BaseModel):
    title: Optional[str] = None
    provider: str
    submission_id: Optional[str] = None


class SurveyAudienceScope(BaseModel):
    teacher_id: Optional[str] = None
    class_name: Optional[str] = None
    sample_size: Optional[int] = None


class SurveyQuestionSummary(BaseModel):
    question_id: str
    prompt: Optional[str] = None
    response_type: Optional[str] = None
    stats: Dict[str, Any] = Field(default_factory=dict)


class SurveyGroupBreakdown(BaseModel):
    group_name: str
    sample_size: Optional[int] = None
    stats: Dict[str, Any] = Field(default_factory=dict)


class SurveyFreeTextSignal(BaseModel):
    theme: str
    evidence_count: int = 0
    excerpts: List[str] = Field(default_factory=list)


class SurveyEvidenceBundle(BaseModel):
    survey_meta: SurveyMeta
    audience_scope: SurveyAudienceScope
    question_summaries: List[SurveyQuestionSummary] = Field(default_factory=list)
    group_breakdowns: List[SurveyGroupBreakdown] = Field(default_factory=list)
    free_text_signals: List[SurveyFreeTextSignal] = Field(default_factory=list)
    attachments: List[Dict[str, Any]] = Field(default_factory=list)
    parse_confidence: float = 1.0
    missing_fields: List[str] = Field(default_factory=list)
    provenance: Dict[str, Any] = Field(default_factory=dict)
