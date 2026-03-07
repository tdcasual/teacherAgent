from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class MediaTextSegment(BaseModel):
    segment_id: str
    kind: str = 'asr'
    start_sec: float
    end_sec: float
    text: str
    speaker: Optional[str] = None
    confidence: Optional[float] = None
    language: Optional[str] = None
    evidence_refs: list[str] = Field(default_factory=list)


class MediaFrameEvidence(BaseModel):
    frame_id: str
    timestamp_sec: float
    image_path: Optional[str] = None
    image_uri: Optional[str] = None
    ocr_text: Optional[str] = None
    caption: Optional[str] = None
    confidence: Optional[float] = None


class MediaExtractionFailure(BaseModel):
    stage: str
    code: str
    message: Optional[str] = None
    retryable: bool = False
