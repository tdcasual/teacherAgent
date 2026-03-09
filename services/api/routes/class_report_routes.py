from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query

from ..analysis_report_service import (
    AnalysisReportServiceError,
    build_analysis_report_deps,
    get_analysis_report,
    list_analysis_reports,
    list_analysis_review_queue,
    rerun_analysis_report,
)
from ..api_models import AnalysisReportRerunRequest
from .teacher_route_helpers import scoped_teacher_id



def _raise_http_exception(exc: Exception) -> None:
    status_code = int(getattr(exc, 'status_code', 500) or 500)
    detail = str(getattr(exc, 'detail', exc) or 'class_report_request_failed')
    raise HTTPException(status_code=status_code, detail=detail)



def _to_class_report_detail(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'report': dict(payload.get('report') or {}),
        'analysis_artifact': dict(payload.get('analysis_artifact') or {}),
        'artifact_meta': dict(payload.get('artifact_meta') or {}),
    }



def build_router(core: Any) -> APIRouter:
    router = APIRouter()
    analysis_deps = build_analysis_report_deps(core)

    @router.get('/teacher/class-reports/reports')
    async def teacher_class_reports(
        teacher_id: str = Query(default=''),
        status: str = Query(default=''),
    ) -> Any:
        teacher_id_scoped = scoped_teacher_id(teacher_id) or ''
        try:
            return list_analysis_reports(
                teacher_id=teacher_id_scoped,
                domain='class_report',
                status=status or None,
                strategy_id=None,
                target_type=None,
                deps=analysis_deps,
            )
        except (AnalysisReportServiceError, Exception) as exc:
            _raise_http_exception(exc)

    @router.get('/teacher/class-reports/reports/{report_id}')
    async def teacher_class_report(report_id: str, teacher_id: str = Query(default='')) -> Any:
        teacher_id_scoped = scoped_teacher_id(teacher_id) or ''
        try:
            return _to_class_report_detail(
                get_analysis_report(
                    report_id=report_id,
                    teacher_id=teacher_id_scoped,
                    domain='class_report',
                    deps=analysis_deps,
                )
            )
        except (AnalysisReportServiceError, Exception) as exc:
            _raise_http_exception(exc)

    @router.post('/teacher/class-reports/reports/{report_id}/rerun')
    async def teacher_class_report_rerun(report_id: str, req: AnalysisReportRerunRequest) -> Any:
        teacher_id_scoped = scoped_teacher_id(req.teacher_id) or ''
        try:
            return rerun_analysis_report(
                report_id=report_id,
                teacher_id=teacher_id_scoped,
                domain='class_report',
                reason=req.reason,
                deps=analysis_deps,
            )
        except (AnalysisReportServiceError, Exception) as exc:
            _raise_http_exception(exc)

    @router.get('/teacher/class-reports/review-queue')
    async def teacher_class_report_review_queue(teacher_id: str = Query(default='')) -> Any:
        teacher_id_scoped = scoped_teacher_id(teacher_id) or ''
        try:
            return list_analysis_review_queue(
                teacher_id=teacher_id_scoped,
                domain='class_report',
                status=None,
                deps=analysis_deps,
            )
        except (AnalysisReportServiceError, Exception) as exc:
            _raise_http_exception(exc)

    return router
