from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class OutputSchemaValidationError(ValueError):
    pass


class ConfidenceAndGaps(BaseModel):
    confidence: float
    gaps: list[str] = Field(default_factory=list)


class KeySignal(BaseModel):
    title: str
    detail: str
    evidence_refs: list[str] = Field(default_factory=list)


class GroupDifference(BaseModel):
    group_name: str
    summary: str


class CompletionOverview(BaseModel):
    status: str
    summary: str
    duration_sec: float | None = None


class EvidenceClip(BaseModel):
    label: str
    start_sec: float | None = None
    end_sec: float | None = None
    evidence_ref: str | None = None
    excerpt: str | None = None


class SurveyAnalysisArtifact(BaseModel):
    executive_summary: str
    key_signals: list[KeySignal] = Field(default_factory=list)
    group_differences: list[GroupDifference] = Field(default_factory=list)
    teaching_recommendations: list[str] = Field(default_factory=list)
    confidence_and_gaps: ConfidenceAndGaps


class ClassReportAnalysisArtifact(BaseModel):
    executive_summary: str
    key_signals: list[KeySignal] = Field(default_factory=list)
    teaching_recommendations: list[str] = Field(default_factory=list)
    confidence_and_gaps: ConfidenceAndGaps


class VideoHomeworkAnalysisArtifact(BaseModel):
    executive_summary: str
    completion_overview: CompletionOverview
    key_signals: list[KeySignal] = Field(default_factory=list)
    expression_signals: list[KeySignal] = Field(default_factory=list)
    evidence_clips: list[EvidenceClip] = Field(default_factory=list)
    teaching_recommendations: list[str] = Field(default_factory=list)
    confidence_and_gaps: ConfidenceAndGaps


_SCHEMA_BY_TYPE: dict[str, type[BaseModel]] = {
    'survey.analysis_artifact': SurveyAnalysisArtifact,
    'class_report.analysis_artifact': ClassReportAnalysisArtifact,
    'video_homework.analysis_artifact': VideoHomeworkAnalysisArtifact,
}



def validate_specialist_output(*, schema_type: str, output: dict[str, Any]) -> None:
    schema_type_final = str(schema_type or '').strip()
    if not schema_type_final:
        return
    if schema_type_final == 'analysis_artifact':
        if not dict(output or {}):
            raise OutputSchemaValidationError('output must not be empty')
        return
    schema = _SCHEMA_BY_TYPE.get(schema_type_final)
    if schema is None:
        raise OutputSchemaValidationError(f'unknown schema type: {schema_type_final}')
    validated = schema.model_validate(output)
    recommendations = getattr(validated, 'teaching_recommendations', None)
    if recommendations is not None and not list(recommendations):
        raise OutputSchemaValidationError('teaching_recommendations must not be empty')
