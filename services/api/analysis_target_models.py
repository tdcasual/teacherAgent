from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AnalysisTargetRef:
    target_type: str
    target_id: str
    artifact_type: str
    teacher_id: str
    source_domain: str
    resolution_reason: str
