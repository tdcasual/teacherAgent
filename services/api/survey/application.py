from __future__ import annotations

from typing import Any, Dict

from ..api_models import SurveyReportRerunRequest
from .deps import SurveyApplicationDeps


async def survey_webhook_ingest(*, provider: str, payload: Dict[str, Any], signature: str, deps: SurveyApplicationDeps) -> Any:
    return deps.webhook_ingest(provider=provider, payload=payload, signature=signature)


async def list_survey_reports(*, teacher_id: str, status: str | None, deps: SurveyApplicationDeps) -> Any:
    return deps.list_reports(teacher_id=teacher_id, status=status)


async def get_survey_report(report_id: str, *, teacher_id: str, deps: SurveyApplicationDeps) -> Any:
    return deps.get_report(report_id=report_id, teacher_id=teacher_id)


async def rerun_survey_report(
    report_id: str,
    req: SurveyReportRerunRequest,
    *,
    deps: SurveyApplicationDeps,
) -> Any:
    return deps.rerun_report(report_id=report_id, teacher_id=req.teacher_id, reason=req.reason)


async def list_survey_review_queue(*, teacher_id: str, deps: SurveyApplicationDeps) -> Any:
    return deps.list_review_queue(teacher_id=teacher_id)
