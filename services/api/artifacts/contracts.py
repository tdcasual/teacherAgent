from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ArtifactEvidenceRef(BaseModel):
    ref_id: str
    kind: Optional[str] = None
    uri: Optional[str] = None
    mime_type: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ArtifactEnvelope(BaseModel):
    artifact_type: str
    schema_version: str = 'v1'
    adapter_version: str = 'v1'
    subject_scope: Dict[str, Any] = Field(default_factory=dict)
    evidence_refs: List[ArtifactEvidenceRef] = Field(default_factory=list)
    confidence: Optional[float] = None
    missing_fields: List[str] = Field(default_factory=list)
    provenance: Dict[str, Any] = Field(default_factory=dict)
    payload: Dict[str, Any] = Field(default_factory=dict)
