from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from .survey_repository import append_survey_review_queue_item


@dataclass(frozen=True)
class SurveyReviewQueueDeps:
    append_item: Callable[[Dict[str, Any]], Any]
    now_iso: Callable[[], str]



def build_survey_review_queue_deps(core: Any | None = None) -> SurveyReviewQueueDeps:
    return SurveyReviewQueueDeps(
        append_item=lambda item: append_survey_review_queue_item(item, core=core),
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
    )



def enqueue_survey_review_item(
    *,
    job: Dict[str, Any],
    reason: str,
    confidence: Optional[float],
    deps: SurveyReviewQueueDeps,
) -> Dict[str, Any]:
    item = {
        "report_id": str(job.get("report_id") or job.get("job_id") or "").strip(),
        "job_id": str(job.get("job_id") or "").strip() or None,
        "teacher_id": str(job.get("teacher_id") or "").strip(),
        "class_name": str(job.get("class_name") or "").strip() or None,
        "reason": str(reason or "").strip(),
        "confidence": confidence,
        "created_at": deps.now_iso(),
    }
    deps.append_item(item)
    return item
