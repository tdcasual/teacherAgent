from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Body, Header, HTTPException, Query

from ..api_models import SurveyReportRerunRequest
from ..survey import application as survey_application
from ..survey import deps as survey_deps



def _raise_http_exception(exc: Exception) -> None:
    status_code = int(getattr(exc, "status_code", 500) or 500)
    detail = str(getattr(exc, "detail", exc) or "survey_request_failed")
    raise HTTPException(status_code=status_code, detail=detail)



def build_router(core: Any) -> APIRouter:
    router = APIRouter()
    app_deps = survey_deps.build_survey_application_deps(core)

    @router.post("/webhooks/surveys/provider")
    async def survey_webhook_provider(
        payload: Dict[str, Any] = Body(default={}),
        signature: str = Header(default="", alias="X-Survey-Signature"),
    ) -> Any:
        try:
            return await survey_application.survey_webhook_ingest(
                provider="provider",
                payload=payload,
                signature=signature,
                deps=app_deps,
            )
        except Exception as exc:
            _raise_http_exception(exc)

    @router.get("/teacher/surveys/reports")
    async def teacher_survey_reports(
        teacher_id: str = Query(default=""),
        status: str = Query(default=""),
    ) -> Any:
        try:
            return await survey_application.list_survey_reports(
                teacher_id=teacher_id,
                status=status or None,
                deps=app_deps,
            )
        except Exception as exc:
            _raise_http_exception(exc)

    @router.get("/teacher/surveys/reports/{report_id}")
    async def teacher_survey_report(report_id: str, teacher_id: str = Query(default="")) -> Any:
        try:
            return await survey_application.get_survey_report(
                report_id,
                teacher_id=teacher_id,
                deps=app_deps,
            )
        except Exception as exc:
            _raise_http_exception(exc)

    @router.post("/teacher/surveys/reports/{report_id}/rerun")
    async def teacher_survey_report_rerun(
        report_id: str,
        req: SurveyReportRerunRequest,
    ) -> Any:
        try:
            return await survey_application.rerun_survey_report(report_id, req, deps=app_deps)
        except Exception as exc:
            _raise_http_exception(exc)

    @router.get("/teacher/surveys/review-queue")
    async def teacher_survey_review_queue(teacher_id: str = Query(default="")) -> Any:
        try:
            return await survey_application.list_survey_review_queue(
                teacher_id=teacher_id,
                deps=app_deps,
            )
        except Exception as exc:
            _raise_http_exception(exc)

    return router
