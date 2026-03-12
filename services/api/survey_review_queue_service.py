from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from .analysis_metadata_repository import FileBackedAnalysisMetadataRepository
from .review_queue_service import ReviewQueueDeps, enqueue_review_item
from .survey_repository import append_survey_review_queue_item


@dataclass(frozen=True)
class SurveyReviewQueueDeps:
    append_item: Callable[[Dict[str, Any]], Any]
    now_iso: Callable[[], str]
    review_queue_deps: ReviewQueueDeps



def build_survey_review_queue_deps(core: Any | None = None) -> SurveyReviewQueueDeps:
    target = Path(getattr(core, 'DATA_DIR', '.')) / 'survey_review_queue.jsonl'
    metrics_service = getattr(core, 'analysis_metrics_service', None)
    return SurveyReviewQueueDeps(
        append_item=lambda item: append_survey_review_queue_item(item, core=core),
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
        review_queue_deps=ReviewQueueDeps(
            metadata_repo=FileBackedAnalysisMetadataRepository(base_dir=target.parent),
            queue_log=target.name,
            now_iso=lambda: datetime.now().isoformat(timespec='seconds'),
            review_feedback_log=target.parent / 'analysis' / 'review_feedback.jsonl',
            metrics_service=metrics_service,
        ),
    )



def enqueue_survey_review_item(
    *,
    job: Dict[str, Any],
    reason: str,
    confidence: Optional[float],
    deps: SurveyReviewQueueDeps,
) -> Dict[str, Any]:
    item = enqueue_review_item(
        domain='survey',
        report_id=str(job.get('report_id') or job.get('job_id') or '').strip(),
        teacher_id=str(job.get('teacher_id') or '').strip(),
        reason=str(reason or '').strip(),
        confidence=confidence,
        target_type='report',
        target_id=str(job.get('report_id') or job.get('job_id') or '').strip(),
        strategy_id=str(job.get('strategy_id') or 'survey.teacher.report').strip() or 'survey.teacher.report',
        deps=deps.review_queue_deps,
    )
    item['job_id'] = str(job.get('job_id') or '').strip() or None
    item['class_name'] = str(job.get('class_name') or '').strip() or None
    return item
