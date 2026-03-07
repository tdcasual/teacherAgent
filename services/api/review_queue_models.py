from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class ReviewQueueItem(BaseModel):
    item_id: str
    domain: str
    report_id: str
    teacher_id: str
    target_type: str
    target_id: str
    status: str
    reason: str
    confidence: Optional[float] = None
    operation: str = 'enqueue'
    reviewer_id: Optional[str] = None
    resolution_note: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
