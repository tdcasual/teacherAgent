from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .analysis_lineage_service import extract_analysis_lineage
from .analysis_metadata_repository import FileBackedAnalysisMetadataRepository
from .api_models import SurveyReportDetail, SurveyReportSummary, SurveyReviewQueueItemSummary
from .config import DATA_DIR, UPLOADS_DIR
from .job_repository import load_survey_job, write_survey_job
from .review_queue_service import ReviewQueueDeps, has_open_review_item, list_review_items
from .survey_repository import (
    load_survey_bundle,
    load_survey_report,
    read_survey_review_queue,
    write_survey_report,
)


class SurveyReportServiceError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = int(status_code)
        self.detail = str(detail)


@dataclass(frozen=True)
class SurveyReportReadDeps:
    data_dir: Path
    uploads_dir: Path
    load_survey_report: Callable[[str], Dict[str, Any]]
    write_survey_report: Callable[[str, Dict[str, Any]], Any]
    load_survey_bundle: Callable[[str], Dict[str, Any]]
    load_survey_job: Callable[[str], Dict[str, Any]]
    write_survey_job: Callable[[str, Dict[str, Any]], Any]
    read_survey_review_queue: Callable[[], List[Dict[str, Any]]]
    review_queue_deps: ReviewQueueDeps
    now_iso: Callable[[], str]
    metrics_service: Any | None = None



def build_survey_report_deps(core: Any | None = None) -> SurveyReportReadDeps:
    data_dir = Path(getattr(core, "DATA_DIR", DATA_DIR))
    uploads_dir = Path(getattr(core, "UPLOADS_DIR", UPLOADS_DIR))
    metrics_service = getattr(core, 'analysis_metrics_service', None)
    return SurveyReportReadDeps(
        data_dir=data_dir,
        uploads_dir=uploads_dir,
        load_survey_report=lambda report_id: load_survey_report(report_id, core=core),
        write_survey_report=lambda report_id, payload: write_survey_report(report_id, payload, core=core),
        load_survey_bundle=lambda job_id: load_survey_bundle(job_id, core=core),
        load_survey_job=lambda job_id: load_survey_job(job_id, core=core),
        write_survey_job=lambda job_id, payload: write_survey_job(job_id, payload, core=core),
        read_survey_review_queue=lambda: read_survey_review_queue(core=core),
        review_queue_deps=ReviewQueueDeps(
            metadata_repo=FileBackedAnalysisMetadataRepository(base_dir=data_dir),
            queue_log='survey_review_queue.jsonl',
            now_iso=lambda: datetime.now().isoformat(timespec='seconds'),
            review_feedback_log=data_dir / 'analysis' / 'review_feedback.jsonl',
            metrics_service=metrics_service,
        ),
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
        metrics_service=metrics_service,
    )



def _require_teacher_id(teacher_id: str) -> str:
    value = str(teacher_id or "").strip()
    if not value:
        raise SurveyReportServiceError(400, "teacher_id_required")
    return value



def _load_json(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}



def _iter_report_payloads(deps: SurveyReportReadDeps) -> List[Dict[str, Any]]:
    report_dir = deps.data_dir / "survey_reports"
    rows: List[Dict[str, Any]] = []
    if not report_dir.exists():
        return rows
    for path in sorted(report_dir.glob("*.json")):
        payload = _load_json(path)
        if payload:
            payload.setdefault("report_id", path.stem)
            rows.append(payload)
    return rows



def _iter_job_payloads(deps: SurveyReportReadDeps) -> List[Dict[str, Any]]:
    jobs_dir = deps.uploads_dir / "survey_jobs"
    rows: List[Dict[str, Any]] = []
    if not jobs_dir.exists():
        return rows
    for path in sorted(jobs_dir.glob("*/job.json")):
        payload = _load_json(path)
        if payload:
            payload.setdefault("job_id", path.parent.name)
            rows.append(payload)
    return rows



def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None



def _load_bundle_optional(job_id: Optional[str], deps: SurveyReportReadDeps) -> Dict[str, Any]:
    if not job_id:
        return {}
    try:
        bundle = deps.load_survey_bundle(job_id)
    except FileNotFoundError:
        return {}
    return bundle if isinstance(bundle, dict) else {}



def _bundle_meta_for_job(job_id: Optional[str], deps: SurveyReportReadDeps) -> Dict[str, Any]:
    if not job_id:
        return {}
    try:
        bundle = deps.load_survey_bundle(job_id)
    except FileNotFoundError:
        return {}
    if not isinstance(bundle, dict):
        return {}
    return {
        "parse_confidence": _safe_float(bundle.get("parse_confidence")),
        "missing_fields": list(bundle.get("missing_fields") or []),
        "provenance": dict(bundle.get("provenance") or {}),
        "survey_meta": dict(bundle.get("survey_meta") or {}),
    }



def _review_required(report_id: str, teacher_id: str, deps: SurveyReportReadDeps) -> bool:
    return has_open_review_item(
        report_id=report_id,
        teacher_id=teacher_id,
        domain='survey',
        deps=deps.review_queue_deps,
    )



def _summary_from_report(report: Dict[str, Any], deps: SurveyReportReadDeps) -> Dict[str, Any]:
    report_id = str(report.get("report_id") or "").strip()
    job_id = str(report.get("job_id") or report_id or "").strip() or None
    bundle_meta = _bundle_meta_for_job(job_id, deps)
    confidence = _safe_float(report.get("confidence"))
    if confidence is None:
        confidence = _safe_float(bundle_meta.get("parse_confidence"))
    summary = SurveyReportSummary(
        report_id=report_id,
        teacher_id=str(report.get("teacher_id") or "").strip(),
        class_name=str(report.get("class_name") or bundle_meta.get("survey_meta", {}).get("class_name") or "").strip() or None,
        status=str(report.get("status") or "unknown").strip() or "unknown",
        confidence=confidence,
        summary=str(
            report.get("summary")
            or (report.get("analysis_artifact") or {}).get("executive_summary")
            or ""
        ).strip()
        or None,
        created_at=str(report.get("created_at") or "").strip() or None,
        updated_at=str(report.get("updated_at") or "").strip() or None,
    )
    return summary.model_dump()



def _summary_from_job(job: Dict[str, Any], deps: SurveyReportReadDeps) -> Dict[str, Any]:
    report_id = str(job.get("report_id") or job.get("job_id") or "").strip()
    job_id = str(job.get("job_id") or report_id or "").strip() or None
    bundle_meta = _bundle_meta_for_job(job_id, deps)
    confidence = _safe_float(bundle_meta.get("parse_confidence"))
    summary = SurveyReportSummary(
        report_id=report_id,
        teacher_id=str(job.get("teacher_id") or "").strip(),
        class_name=str(job.get("class_name") or "").strip() or None,
        status=str(job.get("status") or job.get("queue_status") or "queued").strip() or "queued",
        confidence=confidence,
        summary=None,
        created_at=str(job.get("created_at") or "").strip() or None,
        updated_at=str(job.get("updated_at") or "").strip() or None,
    )
    return summary.model_dump()



def _status_rank(status: str) -> int:
    order = {
        "teacher_notified": 6,
        "analysis_ready": 5,
        "review": 4,
        "analysis_running": 3,
        "bundle_ready": 2,
        "normalized": 1,
        "queued": 0,
    }
    return order.get(str(status or "").strip(), 0)



def _sort_key(summary: Dict[str, Any]) -> Tuple[int, str, str]:
    updated_at = str(summary.get("updated_at") or "")
    created_at = str(summary.get("created_at") or "")
    return (_status_rank(str(summary.get("status") or "")), updated_at, created_at)



def list_survey_reports(*, teacher_id: str, status: str | None, deps: SurveyReportReadDeps) -> Dict[str, Any]:
    teacher_id_final = _require_teacher_id(teacher_id)
    normalized_status = str(status or "").strip() or None

    report_payloads = _iter_report_payloads(deps)
    summaries: List[Dict[str, Any]] = []
    seen_report_ids: set[str] = set()
    seen_job_ids: set[str] = set()

    for report in report_payloads:
        summary = _summary_from_report(report, deps)
        if summary["teacher_id"] != teacher_id_final:
            continue
        if normalized_status and summary["status"] != normalized_status:
            continue
        summaries.append(summary)
        seen_report_ids.add(summary["report_id"])
        job_id = str(report.get("job_id") or "").strip()
        if job_id:
            seen_job_ids.add(job_id)

    for job in _iter_job_payloads(deps):
        job_id = str(job.get("job_id") or "").strip()
        report_id = str(job.get("report_id") or job_id or "").strip()
        if not report_id or report_id in seen_report_ids or job_id in seen_job_ids:
            continue
        summary = _summary_from_job(job, deps)
        if summary["teacher_id"] != teacher_id_final:
            continue
        if normalized_status and summary["status"] != normalized_status:
            continue
        summaries.append(summary)

    summaries.sort(key=_sort_key, reverse=True)
    return {"items": summaries}



def _load_report_or_job(report_id: str, deps: SurveyReportReadDeps) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    report: Optional[Dict[str, Any]]
    job: Optional[Dict[str, Any]]
    try:
        report = deps.load_survey_report(report_id)
    except FileNotFoundError:
        report = None
    if report is not None:
        job_id = str(report.get("job_id") or report_id or "").strip() or None
        if job_id:
            try:
                job = deps.load_survey_job(job_id)
            except FileNotFoundError:
                job = None
        else:
            job = None
        return report, job
    try:
        job = deps.load_survey_job(report_id)
    except FileNotFoundError:
        job = None
    return None, job



def get_survey_report(report_id: str, *, teacher_id: str, deps: SurveyReportReadDeps) -> Dict[str, Any]:
    teacher_id_final = _require_teacher_id(teacher_id)
    report, job = _load_report_or_job(report_id, deps)
    if report is None and job is None:
        raise SurveyReportServiceError(404, "survey_report_not_found")

    effective_teacher_id = str((report or job or {}).get("teacher_id") or "").strip()
    if effective_teacher_id != teacher_id_final:
        raise SurveyReportServiceError(404, "survey_report_not_found")

    if report is not None:
        summary = _summary_from_report(report, deps)
        effective_report_id = summary["report_id"]
        job_id = str(report.get("job_id") or effective_report_id or "").strip() or None
        bundle_meta = dict(report.get("bundle_meta") or {})
        replay_artifact = _load_bundle_optional(job_id, deps)
        bundle_meta_from_job = _bundle_meta_for_job(job_id, deps)
        bundle_meta.setdefault("parse_confidence", bundle_meta_from_job.get("parse_confidence"))
        bundle_meta.setdefault("missing_fields", bundle_meta_from_job.get("missing_fields") or [])
        if bundle_meta_from_job.get("provenance") is not None:
            bundle_meta.setdefault("provenance", bundle_meta_from_job.get("provenance"))
        if job_id is not None:
            bundle_meta.setdefault("job_id", job_id)
        bundle_meta.setdefault("report_id", effective_report_id)
        if report.get("rerun_requested") is not None:
            bundle_meta["rerun_requested"] = bool(report.get("rerun_requested"))
        if report.get("rerun_reason") is not None:
            bundle_meta["rerun_reason"] = report.get("rerun_reason")
        if report.get("rerun_requested_at") is not None:
            bundle_meta["rerun_requested_at"] = report.get("rerun_requested_at")
        if report.get("rerun_base_lineage") is not None:
            bundle_meta["rerun_base_lineage"] = dict(report.get("rerun_base_lineage") or {})
        detail = SurveyReportDetail(
            report=SurveyReportSummary.model_validate(summary),
            analysis_artifact=dict(report.get("analysis_artifact") or {}),
            bundle_meta=bundle_meta,
            review_required=_review_required(effective_report_id, teacher_id_final, deps),
        )
        payload = detail.model_dump()
        payload['replay_artifact'] = dict(replay_artifact or {})
        return payload

    assert job is not None
    summary = _summary_from_job(job, deps)
    effective_report_id = summary["report_id"]
    job_id = str(job.get("job_id") or effective_report_id or "").strip() or None
    replay_artifact = _load_bundle_optional(job_id, deps)
    bundle_meta = _bundle_meta_for_job(job_id, deps)
    if job_id is not None:
        bundle_meta["job_id"] = job_id
    bundle_meta["report_id"] = effective_report_id
    bundle_meta["job_status"] = summary["status"]
    if job.get("rerun_base_lineage") is not None:
        bundle_meta["rerun_base_lineage"] = dict(job.get("rerun_base_lineage") or {})
    detail = SurveyReportDetail(
        report=SurveyReportSummary.model_validate(summary),
        analysis_artifact={},
        bundle_meta=bundle_meta,
        review_required=_review_required(effective_report_id, teacher_id_final, deps),
    )
    payload = detail.model_dump()
    payload['replay_artifact'] = dict(replay_artifact or {})
    return payload



def rerun_survey_report(
    report_id: str,
    *,
    teacher_id: str,
    reason: str | None,
    deps: SurveyReportReadDeps,
) -> Dict[str, Any]:
    teacher_id_final = _require_teacher_id(teacher_id)
    report, job = _load_report_or_job(report_id, deps)
    payload = report or job
    if payload is None or str(payload.get("teacher_id") or "").strip() != teacher_id_final:
        raise SurveyReportServiceError(404, "survey_report_not_found")

    previous_lineage = extract_analysis_lineage(payload)
    current_lineage = extract_analysis_lineage(payload)
    updates = {
        "rerun_requested": True,
        "rerun_reason": str(reason or "").strip() or None,
        "rerun_requested_at": deps.now_iso(),
        "rerun_requested_by": teacher_id_final,
        "rerun_base_lineage": previous_lineage,
    }
    if report is not None:
        merged_report = dict(report)
        merged_report.update(updates)
        deps.write_survey_report(report_id, merged_report)
    else:
        deps.write_survey_job(report_id, updates)
    metrics_service = getattr(deps, 'metrics_service', None)
    record_rerun = getattr(metrics_service, 'record_rerun', None)
    if callable(record_rerun):
        record_rerun(
            domain='survey',
            strategy_id=str(payload.get('strategy_id') or 'survey.teacher.report').strip() or 'survey.teacher.report',
        )
    return {
        "ok": True,
        "report_id": report_id,
        "status": "rerun_requested",
        "reason": updates["rerun_reason"],
        "previous_lineage": previous_lineage,
        "current_lineage": current_lineage,
    }



def list_survey_review_queue(*, teacher_id: str, deps: SurveyReportReadDeps) -> Dict[str, Any]:
    teacher_id_final = _require_teacher_id(teacher_id)
    payload = list_review_items(teacher_id=teacher_id_final, domain='survey', status=None, deps=deps.review_queue_deps)
    items: List[Dict[str, Any]] = []
    for raw in payload.get('items') or []:
        item = SurveyReviewQueueItemSummary(
            report_id=str(raw.get('report_id') or '').strip(),
            teacher_id=teacher_id_final,
            reason=str(raw.get('reason') or '').strip(),
            confidence=_safe_float(raw.get('confidence')),
            created_at=str(raw.get('created_at') or '').strip() or None,
        )
        items.append(item.model_dump())
    return {'items': items}
