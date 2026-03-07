from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .artifacts.contracts import ArtifactEnvelope, ArtifactEvidenceRef


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

    def to_artifact_envelope(self) -> ArtifactEnvelope:
        return ArtifactEnvelope(
            artifact_type='survey_evidence_bundle',
            schema_version='v1',
            subject_scope={
                'teacher_id': self.audience_scope.teacher_id,
                'class_name': self.audience_scope.class_name,
                'sample_size': self.audience_scope.sample_size,
            },
            evidence_refs=[_attachment_to_artifact_ref(item, index) for index, item in enumerate(self.attachments)],
            confidence=float(self.parse_confidence),
            missing_fields=list(self.missing_fields or []),
            provenance=dict(self.provenance or {}),
            payload=self.model_dump(),
        )


def _attachment_to_artifact_ref(attachment: Dict[str, Any], index: int) -> ArtifactEvidenceRef:
    return ArtifactEvidenceRef(
        ref_id=str(attachment.get('name') or attachment.get('id') or f'attachment_{index + 1}').strip() or f'attachment_{index + 1}',
        kind=str(attachment.get('kind') or 'attachment').strip() or 'attachment',
        uri=str(attachment.get('uri') or '').strip() or None,
        mime_type=str(attachment.get('mime_type') or attachment.get('content_type') or '').strip() or None,
        metadata={
            key: value
            for key, value in dict(attachment or {}).items()
            if key not in {'name', 'id', 'kind', 'uri', 'mime_type', 'content_type'}
        },
    )
