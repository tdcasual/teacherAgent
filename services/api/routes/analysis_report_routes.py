from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from ..analysis_metrics_service import AnalysisMetricsService
from ..analysis_report_service import (
    AnalysisReportServiceError,
    build_analysis_report_deps,
    get_analysis_report,
    list_analysis_reports,
    list_analysis_review_queue,
    operate_analysis_review_queue_item,
    rerun_analysis_report,
)
from ..api_models import AnalysisReportRerunRequest, AnalysisReviewQueueActionRequest
from .teacher_route_helpers import scoped_teacher_id


def _raise_http_exception(exc: Exception) -> None:
    status_code = int(getattr(exc, 'status_code', 500) or 500)
    detail = str(getattr(exc, 'detail', exc) or 'analysis_report_request_failed')
    raise HTTPException(status_code=status_code, detail=detail)



def build_router(core: Any) -> APIRouter:
    router = APIRouter()
    deps = build_analysis_report_deps(core)

    @router.get('/teacher/analysis/reports')
    async def teacher_analysis_reports(
        teacher_id: str = Query(default=''),
        domain: str = Query(default=''),
        status: str = Query(default=''),
        strategy_id: str = Query(default=''),
        target_type: str = Query(default=''),
    ) -> Any:
        teacher_id_scoped = scoped_teacher_id(teacher_id) or ''
        try:
            return list_analysis_reports(
                teacher_id=teacher_id_scoped,
                domain=domain or None,
                status=status or None,
                strategy_id=strategy_id or None,
                target_type=target_type or None,
                deps=deps,
            )
        except (AnalysisReportServiceError, Exception) as exc:
            _raise_http_exception(exc)

    @router.get('/teacher/analysis/reports/{report_id}')
    async def teacher_analysis_report(report_id: str, teacher_id: str = Query(default=''), domain: str = Query(default='')) -> Any:
        teacher_id_scoped = scoped_teacher_id(teacher_id) or ''
        try:
            return get_analysis_report(report_id=report_id, teacher_id=teacher_id_scoped, domain=domain or None, deps=deps)
        except (AnalysisReportServiceError, Exception) as exc:
            _raise_http_exception(exc)

    @router.post('/teacher/analysis/reports/{report_id}/rerun')
    async def teacher_analysis_report_rerun(report_id: str, req: AnalysisReportRerunRequest) -> Any:
        teacher_id_scoped = scoped_teacher_id(req.teacher_id) or ''
        try:
            return rerun_analysis_report(
                report_id=report_id,
                teacher_id=teacher_id_scoped,
                domain=req.domain,
                reason=req.reason,
                deps=deps,
            )
        except (AnalysisReportServiceError, Exception) as exc:
            _raise_http_exception(exc)

    @router.get('/teacher/analysis/review-queue')
    async def teacher_analysis_review_queue(
        teacher_id: str = Query(default=''),
        domain: str = Query(default=''),
        status: str = Query(default=''),
    ) -> Any:
        teacher_id_scoped = scoped_teacher_id(teacher_id) or ''
        try:
            return list_analysis_review_queue(
                teacher_id=teacher_id_scoped,
                domain=domain or None,
                status=status or None,
                deps=deps,
            )
        except (AnalysisReportServiceError, Exception) as exc:
            _raise_http_exception(exc)

    @router.post('/teacher/analysis/review-queue/{item_id}/actions')
    async def teacher_analysis_review_queue_action(item_id: str, req: AnalysisReviewQueueActionRequest) -> Any:
        teacher_id_scoped = scoped_teacher_id(req.teacher_id) or ''
        try:
            return operate_analysis_review_queue_item(
                item_id=item_id,
                teacher_id=teacher_id_scoped,
                domain=req.domain,
                action=req.action,
                reviewer_id=req.reviewer_id,
                operator_note=req.operator_note,
                deps=deps,
            )
        except (AnalysisReportServiceError, Exception) as exc:
            _raise_http_exception(exc)

    @router.get('/teacher/analysis/metrics')
    async def teacher_analysis_metrics() -> Any:
        scoped_teacher_id(None)
        metrics_service = getattr(core, 'analysis_metrics_service', None)
        metrics_snapshot = getattr(metrics_service, 'snapshot', None)
        if callable(metrics_snapshot):
            snapshot = metrics_snapshot()
        else:
            snapshot = AnalysisMetricsService().snapshot()
        return {'ok': True, 'metrics': snapshot}

    return router
