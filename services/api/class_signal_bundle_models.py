from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .artifacts.contracts import ArtifactEnvelope, ArtifactEvidenceRef


class ClassSignalSourceMeta(BaseModel):
    title: Optional[str] = None
    provider: str
    source_type: str
    report_id: Optional[str] = None
    generated_at: Optional[str] = None


class ClassSignalScope(BaseModel):
    teacher_id: Optional[str] = None
    class_name: Optional[str] = None
    sample_size: Optional[int] = None
    grade_level: Optional[str] = None


class ClassSignalQuestionLike(BaseModel):
    signal_id: str
    title: str
    summary: Optional[str] = None
    stats: Dict[str, Any] = Field(default_factory=dict)
    evidence_refs: List[str] = Field(default_factory=list)


class ClassSignalThemeLike(BaseModel):
    theme: str
    summary: Optional[str] = None
    evidence_count: int = 0
    excerpts: List[str] = Field(default_factory=list)
    evidence_refs: List[str] = Field(default_factory=list)


class ClassSignalRiskLike(BaseModel):
    risk: str
    severity: Optional[str] = None
    summary: Optional[str] = None
    evidence_refs: List[str] = Field(default_factory=list)


class ClassSignalBundle(BaseModel):
    source_meta: ClassSignalSourceMeta
    class_scope: ClassSignalScope
    question_like_signals: List[ClassSignalQuestionLike] = Field(default_factory=list)
    theme_like_signals: List[ClassSignalThemeLike] = Field(default_factory=list)
    risk_like_signals: List[ClassSignalRiskLike] = Field(default_factory=list)
    narrative_blocks: List[str] = Field(default_factory=list)
    attachments: List[Dict[str, Any]] = Field(default_factory=list)
    parse_confidence: float = 1.0
    missing_fields: List[str] = Field(default_factory=list)
    provenance: Dict[str, Any] = Field(default_factory=dict)

    def to_artifact_envelope(self) -> ArtifactEnvelope:
        return ArtifactEnvelope(
            artifact_type='class_signal_bundle',
            schema_version='v1',
            subject_scope={
                'teacher_id': self.class_scope.teacher_id,
                'class_name': self.class_scope.class_name,
                'sample_size': self.class_scope.sample_size,
                'grade_level': self.class_scope.grade_level,
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
