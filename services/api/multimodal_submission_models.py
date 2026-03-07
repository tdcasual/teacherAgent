from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .artifacts.contracts import ArtifactEnvelope, ArtifactEvidenceRef
from .media_segment_models import MediaExtractionFailure, MediaFrameEvidence, MediaTextSegment


class MultimodalSourceMeta(BaseModel):
    source_type: str
    title: Optional[str] = None
    submission_id: Optional[str] = None
    assignment_id: Optional[str] = None
    uploaded_at: Optional[str] = None


class MultimodalScope(BaseModel):
    teacher_id: str
    student_id: Optional[str] = None
    class_name: Optional[str] = None
    assignment_id: Optional[str] = None
    submission_kind: str = 'video_homework'


class MultimodalMediaFile(BaseModel):
    file_id: str
    kind: str = 'video'
    storage_path: Optional[str] = None
    original_name: Optional[str] = None
    mime_type: Optional[str] = None
    bytes: int = 0
    duration_sec: Optional[float] = None
    checksum: Optional[str] = None


class MultimodalSubmissionBundle(BaseModel):
    source_meta: MultimodalSourceMeta
    scope: MultimodalScope
    media_files: List[MultimodalMediaFile] = Field(default_factory=list)
    transcript_segments: List[MediaTextSegment] = Field(default_factory=list)
    subtitle_segments: List[MediaTextSegment] = Field(default_factory=list)
    keyframe_evidence: List[MediaFrameEvidence] = Field(default_factory=list)
    extraction_status: str = 'pending'
    extraction_failures: List[MediaExtractionFailure] = Field(default_factory=list)
    narrative_blocks: List[str] = Field(default_factory=list)
    attachments: List[Dict[str, Any]] = Field(default_factory=list)
    parse_confidence: float = 1.0
    missing_fields: List[str] = Field(default_factory=list)
    provenance: Dict[str, Any] = Field(default_factory=dict)

    def to_artifact_envelope(self) -> ArtifactEnvelope:
        evidence_refs = [_media_file_to_evidence_ref(item) for item in self.media_files]
        evidence_refs.extend(_frame_to_evidence_ref(item) for item in self.keyframe_evidence)
        return ArtifactEnvelope(
            artifact_type='multimodal_submission_bundle',
            schema_version='v1',
            subject_scope={
                'teacher_id': self.scope.teacher_id,
                'student_id': self.scope.student_id,
                'class_name': self.scope.class_name,
                'assignment_id': self.scope.assignment_id,
                'submission_kind': self.scope.submission_kind,
                'submission_id': self.source_meta.submission_id,
            },
            evidence_refs=evidence_refs,
            confidence=float(self.parse_confidence),
            missing_fields=list(self.missing_fields or []),
            provenance=dict(self.provenance or {}),
            payload=self.model_dump(),
        )



def _media_file_to_evidence_ref(media_file: MultimodalMediaFile) -> ArtifactEvidenceRef:
    return ArtifactEvidenceRef(
        ref_id=media_file.file_id,
        kind=media_file.kind,
        uri=media_file.storage_path,
        mime_type=media_file.mime_type,
        metadata={
            'original_name': media_file.original_name,
            'bytes': media_file.bytes,
            'duration_sec': media_file.duration_sec,
            'checksum': media_file.checksum,
        },
    )



def _frame_to_evidence_ref(frame: MediaFrameEvidence) -> ArtifactEvidenceRef:
    return ArtifactEvidenceRef(
        ref_id=frame.frame_id,
        kind='keyframe',
        uri=frame.image_uri or frame.image_path,
        mime_type='image/jpeg',
        metadata={
            'timestamp_sec': frame.timestamp_sec,
            'ocr_text': frame.ocr_text,
            'caption': frame.caption,
            'confidence': frame.confidence,
        },
    )
