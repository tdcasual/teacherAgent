from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Body, Header, HTTPException, Query

from ..analysis_report_service import (
    AnalysisReportServiceError,
    build_analysis_report_deps,
    get_analysis_report,
    list_analysis_reports,
    list_analysis_review_queue,
    rerun_analysis_report,
)
from ..api_models import SurveyReportRerunRequest
from ..survey import application as survey_application
from ..survey import deps as survey_deps
from .teacher_route_helpers import scoped_teacher_id


def _raise_http_exception(exc: Exception) -> None:
    status_code = int(getattr(exc, "status_code", 500) or 500)
    detail = str(getattr(exc, "detail", exc) or "survey_request_failed")
    raise HTTPException(status_code=status_code, detail=detail)


def _to_survey_detail(payload: Dict[str, Any]) -> Dict[str, Any]:
    report = dict(payload.get("report") or {})
    return {
        "report": report,
        "analysis_artifact": dict(payload.get("analysis_artifact") or {}),
        "bundle_meta": dict(payload.get("artifact_meta") or payload.get("bundle_meta") or {}),
        "review_required": bool(report.get("review_required")),
    }


def build_router(core: Any) -> APIRouter:
    router = APIRouter()
    app_deps = survey_deps.build_survey_application_deps(core)
    analysis_deps = build_analysis_report_deps(core)

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
        teacher_id_scoped = scoped_teacher_id(teacher_id) or ""
        try:
            return list_analysis_reports(
                teacher_id=teacher_id_scoped,
                domain="survey",
                status=status or None,
                strategy_id=None,
                target_type=None,
                deps=analysis_deps,
            )
        except (AnalysisReportServiceError, Exception) as exc:
            _raise_http_exception(exc)

    @router.get("/teacher/surveys/reports/{report_id}")
    async def teacher_survey_report(report_id: str, teacher_id: str = Query(default="")) -> Any:
        teacher_id_scoped = scoped_teacher_id(teacher_id) or ""
        try:
            return _to_survey_detail(
                get_analysis_report(
                    report_id=report_id,
                    teacher_id=teacher_id_scoped,
                    domain="survey",
                    deps=analysis_deps,
                )
            )
        except (AnalysisReportServiceError, Exception) as exc:
            _raise_http_exception(exc)

    @router.post("/teacher/surveys/reports/{report_id}/rerun")
    async def teacher_survey_report_rerun(
        report_id: str,
        req: SurveyReportRerunRequest,
    ) -> Any:
        teacher_id_scoped = scoped_teacher_id(req.teacher_id) or ""
        try:
            return rerun_analysis_report(
                report_id=report_id,
                teacher_id=teacher_id_scoped,
                domain="survey",
                reason=req.reason,
                deps=analysis_deps,
            )
        except (AnalysisReportServiceError, Exception) as exc:
            _raise_http_exception(exc)

    @router.get("/teacher/surveys/review-queue")
    async def teacher_survey_review_queue(teacher_id: str = Query(default="")) -> Any:
        teacher_id_scoped = scoped_teacher_id(teacher_id) or ""
        try:
            return list_analysis_review_queue(
                teacher_id=teacher_id_scoped,
                domain="survey",
                status=None,
                deps=analysis_deps,
            )
        except (AnalysisReportServiceError, Exception) as exc:
            _raise_http_exception(exc)

    return router
