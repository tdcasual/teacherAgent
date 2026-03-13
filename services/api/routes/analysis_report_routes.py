from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from ..analysis_metrics_service import AnalysisMetricsService
from ..analysis_ops_service import AnalysisOpsService
from ..analysis_report_service import (
    AnalysisReportServiceError,
    build_analysis_report_deps,
    get_analysis_report,
    list_analysis_reports,
    list_analysis_review_queue,
    operate_analysis_review_queue_item,
    rerun_analysis_report,
    rerun_analysis_reports_bulk,
)
from ..api_models import (
    AnalysisOpsSnapshotResponse,
    AnalysisReportBulkRerunRequest,
    AnalysisReportRerunRequest,
    AnalysisReviewQueueActionRequest,
)
from ..specialist_agents.metrics_service import SpecialistMetricsService
from .teacher_route_helpers import scoped_teacher_id



def _raise_http_exception(exc: Exception) -> None:
    status_code = int(getattr(exc, 'status_code', 500) or 500)
    detail = str(getattr(exc, 'detail', exc) or 'analysis_report_request_failed')
    raise HTTPException(status_code=status_code, detail=detail)



def _teacher_analysis_reports_response(
    *,
    teacher_id: str,
    domain: str,
    status: str,
    strategy_id: str,
    target_type: str,
    deps: Any,
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


def _teacher_analysis_report_response(report_id: str, *, teacher_id: str, domain: str, deps: Any) -> Any:
    teacher_id_scoped = scoped_teacher_id(teacher_id) or ''
    try:
        return get_analysis_report(
            report_id=report_id,
            teacher_id=teacher_id_scoped,
            domain=domain or None,
            deps=deps,
        )
    except (AnalysisReportServiceError, Exception) as exc:
        _raise_http_exception(exc)


def _teacher_analysis_report_rerun_response(report_id: str, req: AnalysisReportRerunRequest, *, deps: Any) -> Any:
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


def _teacher_analysis_reports_bulk_rerun_response(req: AnalysisReportBulkRerunRequest, *, deps: Any) -> Any:
    teacher_id_scoped = scoped_teacher_id(req.teacher_id) or ''
    try:
        return rerun_analysis_reports_bulk(
            teacher_id=teacher_id_scoped,
            report_ids=req.report_ids,
            domain=req.domain,
            reason=req.reason,
            deps=deps,
        )
    except (AnalysisReportServiceError, Exception) as exc:
        _raise_http_exception(exc)


def _teacher_analysis_review_queue_response(*, teacher_id: str, domain: str, status: str, deps: Any) -> Any:
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


def _teacher_analysis_review_queue_action_response(
    item_id: str,
    req: AnalysisReviewQueueActionRequest,
    *,
    deps: Any,
) -> Any:
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


def _teacher_analysis_ops_response(*, window_sec: int, core: Any) -> Any:
    scoped_teacher_id(None)
    ops_service = getattr(core, 'analysis_ops_service', None)
    ops_snapshot = getattr(ops_service, 'snapshot', None)
    if callable(ops_snapshot):
        return ops_snapshot(window_sec=window_sec)
    fallback_service = AnalysisOpsService(
        metrics_service=getattr(core, 'analysis_metrics_service', None),
        review_feedback_path=Path(getattr(core, 'DATA_DIR', '.')) / 'analysis' / 'review_feedback.jsonl',
        data_dir=Path(getattr(core, 'DATA_DIR', '.')),
    )
    return fallback_service.snapshot(window_sec=window_sec)


def _teacher_analysis_metrics_response(*, window_sec: int, group_by: str, core: Any) -> Any:
    scoped_teacher_id(None)
    metrics_service = getattr(core, 'analysis_metrics_service', None)
    metrics_snapshot = getattr(metrics_service, 'snapshot', None)
    grouped_runtime_snapshot = getattr(metrics_service, 'grouped_runtime_snapshot', None)
    if callable(metrics_snapshot):
        snapshot = metrics_snapshot(window_sec=window_sec)
    else:
        snapshot = AnalysisMetricsService().snapshot(window_sec=window_sec)
    payload = dict(snapshot or {})
    summary_service = SpecialistMetricsService()
    payload['specialist_quality'] = summary_service.summarize(payload)
    group_by_final = str(group_by or '').strip()
    if group_by_final in {'strategy', 'agent'} and callable(grouped_runtime_snapshot):
        grouped_payload = grouped_runtime_snapshot(group_by=group_by_final, window_sec=window_sec)
        payload[f'specialist_quality_by_{group_by_final}'] = summary_service.summarize_grouped(grouped_payload)
    return {'ok': True, 'metrics': payload}


def _register_analysis_reports_list_route(router: APIRouter, *, deps: Any) -> None:
    @router.get('/teacher/analysis/reports')
    async def teacher_analysis_reports(
        teacher_id: str = Query(default=''),
        domain: str = Query(default=''),
        status: str = Query(default=''),
        strategy_id: str = Query(default=''),
        target_type: str = Query(default=''),
    ) -> Any:
        return _teacher_analysis_reports_response(
            teacher_id=teacher_id,
            domain=domain,
            status=status,
            strategy_id=strategy_id,
            target_type=target_type,
            deps=deps,
        )


def _register_analysis_report_detail_route(router: APIRouter, *, deps: Any) -> None:
    @router.get('/teacher/analysis/reports/{report_id}')
    async def teacher_analysis_report(
        report_id: str,
        teacher_id: str = Query(default=''),
        domain: str = Query(default=''),
    ) -> Any:
        return _teacher_analysis_report_response(report_id, teacher_id=teacher_id, domain=domain, deps=deps)


def _register_analysis_report_rerun_route(router: APIRouter, *, deps: Any) -> None:
    @router.post('/teacher/analysis/reports/{report_id}/rerun')
    async def teacher_analysis_report_rerun(report_id: str, req: AnalysisReportRerunRequest) -> Any:
        return _teacher_analysis_report_rerun_response(report_id, req, deps=deps)


def _register_analysis_reports_bulk_rerun_route(router: APIRouter, *, deps: Any) -> None:
    @router.post('/teacher/analysis/reports/bulk-rerun')
    async def teacher_analysis_reports_bulk_rerun(req: AnalysisReportBulkRerunRequest) -> Any:
        return _teacher_analysis_reports_bulk_rerun_response(req, deps=deps)


def _register_analysis_review_queue_route(router: APIRouter, *, deps: Any) -> None:
    @router.get('/teacher/analysis/review-queue')
    async def teacher_analysis_review_queue(
        teacher_id: str = Query(default=''),
        domain: str = Query(default=''),
        status: str = Query(default=''),
    ) -> Any:
        return _teacher_analysis_review_queue_response(
            teacher_id=teacher_id,
            domain=domain,
            status=status,
            deps=deps,
        )


def _register_analysis_review_queue_action_route(router: APIRouter, *, deps: Any) -> None:
    @router.post('/teacher/analysis/review-queue/{item_id}/actions')
    async def teacher_analysis_review_queue_action(item_id: str, req: AnalysisReviewQueueActionRequest) -> Any:
        return _teacher_analysis_review_queue_action_response(item_id, req, deps=deps)


def _register_analysis_ops_route(router: APIRouter, *, core: Any) -> None:
    @router.get('/teacher/analysis/ops', response_model=AnalysisOpsSnapshotResponse)
    async def teacher_analysis_ops(window_sec: int = Query(default=86400, ge=1)) -> Any:
        return _teacher_analysis_ops_response(window_sec=window_sec, core=core)


def _register_analysis_metrics_route(router: APIRouter, *, core: Any) -> None:
    @router.get('/teacher/analysis/metrics')
    async def teacher_analysis_metrics(
        window_sec: int = Query(default=3600, ge=1),
        group_by: str = Query(default=''),
    ) -> Any:
        return _teacher_analysis_metrics_response(window_sec=window_sec, group_by=group_by, core=core)


def build_router(core: Any) -> APIRouter:
    router = APIRouter()
    deps = build_analysis_report_deps(core)
    _register_analysis_reports_list_route(router, deps=deps)
    _register_analysis_report_detail_route(router, deps=deps)
    _register_analysis_report_rerun_route(router, deps=deps)
    _register_analysis_reports_bulk_rerun_route(router, deps=deps)
    _register_analysis_review_queue_route(router, deps=deps)
    _register_analysis_review_queue_action_route(router, deps=deps)
    _register_analysis_ops_route(router, core=core)
    _register_analysis_metrics_route(router, core=core)
    return router
