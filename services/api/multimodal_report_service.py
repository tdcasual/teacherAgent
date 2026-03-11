from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .analysis_lineage_service import extract_analysis_lineage
from .analysis_metadata_repository import FileBackedAnalysisMetadataRepository
from .multimodal_repository import load_multimodal_submission_view
from .review_queue_service import ReviewQueueDeps, enqueue_review_item, list_review_items


class MultimodalReportServiceError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = int(status_code)
        self.detail = str(detail)


@dataclass(frozen=True)
class MultimodalReportDeps:
    metadata_repo: FileBackedAnalysisMetadataRepository
    review_queue_deps: ReviewQueueDeps
    now_iso: Callable[[], str]
    load_submission_view: Callable[[str], Dict[str, Any]]
    metrics_service: Any | None = None



def build_multimodal_report_deps(core: Any | None = None) -> MultimodalReportDeps:
    base_dir = Path(getattr(core, 'DATA_DIR', '.')) / 'video_homework_reports'
    metadata_repo = FileBackedAnalysisMetadataRepository(base_dir=base_dir)
    metrics_service = getattr(core, 'analysis_metrics_service', None)
    return MultimodalReportDeps(
        metadata_repo=metadata_repo,
        review_queue_deps=ReviewQueueDeps(
            metadata_repo=metadata_repo,
            queue_log='review_queue.jsonl',
            now_iso=lambda: datetime.now().isoformat(timespec='seconds'),
            metrics_service=metrics_service,
        ),
        now_iso=lambda: datetime.now().isoformat(timespec='seconds'),
        load_submission_view=lambda submission_id: load_multimodal_submission_view(submission_id, core=core),
        metrics_service=metrics_service,
    )



def write_multimodal_report_job(submission_id: str, payload: Dict[str, Any], *, deps: MultimodalReportDeps) -> Dict[str, Any]:
    target = _job_relative_path(submission_id)
    existing = _read_optional_json(target, deps)
    merged = dict(existing or {})
    merged.update(dict(payload or {}))
    merged.setdefault('submission_id', submission_id)
    merged['updated_at'] = deps.now_iso()
    deps.metadata_repo.write_json(target, merged)
    return merged



def load_multimodal_report_job(submission_id: str, *, deps: MultimodalReportDeps) -> Dict[str, Any]:
    return deps.metadata_repo.read_json(_job_relative_path(submission_id))



def write_multimodal_report(report_id: str, payload: Dict[str, Any], *, deps: MultimodalReportDeps) -> Dict[str, Any]:
    deps.metadata_repo.write_json(_report_relative_path(report_id), dict(payload or {}))
    return dict(payload or {})



def load_multimodal_report(report_id: str, *, deps: MultimodalReportDeps) -> Dict[str, Any]:
    return deps.metadata_repo.read_json(_report_relative_path(report_id))



def deliver_multimodal_report(
    *,
    job: Dict[str, Any],
    bundle: Dict[str, Any],
    analysis_artifact: Dict[str, Any],
    review_metadata: Dict[str, Any] | None = None,
    deps: MultimodalReportDeps,
) -> Dict[str, Any]:
    submission_id = str(job.get('submission_id') or '').strip()
    report_id = str(job.get('report_id') or submission_id or '').strip() or submission_id
    scope = dict(bundle.get('scope') or {})
    report_summary = {
        'report_id': report_id,
        'submission_id': submission_id,
        'teacher_id': str(job.get('teacher_id') or scope.get('teacher_id') or '').strip(),
        'analysis_type': 'video_homework',
        'target_type': str(job.get('target_type') or 'submission').strip() or 'submission',
        'target_id': str(job.get('target_id') or submission_id).strip() or submission_id,
        'strategy_id': str(job.get('strategy_id') or 'video_homework.teacher.report').strip() or 'video_homework.teacher.report',
        'strategy_version': str(job.get('strategy_version') or 'v1').strip() or 'v1',
        'prompt_version': str(job.get('prompt_version') or 'v1').strip() or 'v1',
        'adapter_version': str(job.get('adapter_version') or 'v1').strip() or 'v1',
        'runtime_version': str(job.get('runtime_version') or 'v1').strip() or 'v1',
        'status': 'analysis_ready',
        'confidence': _safe_float((analysis_artifact.get('confidence_and_gaps') or {}).get('confidence'))
        or _safe_float(bundle.get('parse_confidence')),
        'summary': str(analysis_artifact.get('executive_summary') or '').strip() or None,
        'created_at': str(job.get('created_at') or '').strip() or deps.now_iso(),
        'updated_at': deps.now_iso(),
    }
    artifact_meta = {
        'submission_id': submission_id,
        'report_id': report_id,
        'student_id': scope.get('student_id'),
        'class_name': scope.get('class_name'),
        'assignment_id': scope.get('assignment_id'),
        'submission_kind': scope.get('submission_kind'),
        'extraction_status': bundle.get('extraction_status'),
        'parse_confidence': _safe_float(bundle.get('parse_confidence')),
        'missing_fields': list(bundle.get('missing_fields') or []),
        'provenance': dict(bundle.get('provenance') or {}),
    }
    if isinstance(review_metadata, dict) and review_metadata:
        artifact_meta['review_metadata'] = dict(review_metadata)
    payload = {
        **report_summary,
        'analysis_artifact': dict(analysis_artifact or {}),
        'artifact_meta': artifact_meta,
    }
    return write_multimodal_report(report_id, payload, deps=deps)



def enqueue_multimodal_review_item(
    *,
    report_id: str,
    teacher_id: str,
    reason: str,
    confidence: Optional[float],
    target_id: str,
    strategy_id: str | None = None,
    deps: MultimodalReportDeps,
) -> Dict[str, Any]:
    return enqueue_review_item(
        domain='video_homework',
        report_id=report_id,
        teacher_id=teacher_id,
        reason=reason,
        confidence=confidence,
        target_type='submission',
        target_id=target_id,
        strategy_id=str(strategy_id or 'video_homework.teacher.report').strip() or 'video_homework.teacher.report',
        deps=deps.review_queue_deps,
    )



def list_multimodal_review_queue(*, teacher_id: str, deps: MultimodalReportDeps) -> Dict[str, Any]:
    teacher_id_final = _require_teacher_id(teacher_id)
    return list_review_items(teacher_id=teacher_id_final, domain='video_homework', status=None, deps=deps.review_queue_deps)



def list_multimodal_reports(*, teacher_id: str, status: str | None, deps: MultimodalReportDeps) -> Dict[str, Any]:
    teacher_id_final = _require_teacher_id(teacher_id)
    normalized_status = str(status or '').strip() or None
    items: List[Dict[str, Any]] = []
    reports_dir = deps.metadata_repo.base_dir / 'reports'
    for path in sorted(reports_dir.glob('*.json')) if reports_dir.exists() else []:
        raw = deps.metadata_repo.read_json(f'reports/{path.name}')
        summary = _summary_from_report(raw)
        if summary['teacher_id'] != teacher_id_final:
            continue
        if normalized_status and summary['status'] != normalized_status:
            continue
        items.append(summary)
    items.sort(key=lambda item: (str(item.get('updated_at') or ''), str(item.get('created_at') or ''), str(item.get('report_id') or '')), reverse=True)
    return {'items': items}



def get_multimodal_report(report_id: str, *, teacher_id: str, deps: MultimodalReportDeps) -> Dict[str, Any]:
    teacher_id_final = _require_teacher_id(teacher_id)
    report, job = _load_report_or_job(report_id, deps)
    if report is None and job is None:
        raise MultimodalReportServiceError(404, 'video_homework_report_not_found')

    payload = report or job or {}
    if str(payload.get('teacher_id') or '').strip() != teacher_id_final:
        raise MultimodalReportServiceError(404, 'video_homework_report_not_found')

    if report is not None:
        summary = _summary_from_report(report)
        submission_id = str(report.get('submission_id') or summary['target_id'] or '').strip()
        replay_artifact = deps.load_submission_view(submission_id) if submission_id else {}
        artifact_meta = dict(report.get('artifact_meta') or {})
        if report.get('rerun_requested') is not None:
            artifact_meta['rerun_requested'] = bool(report.get('rerun_requested'))
        if report.get('rerun_reason') is not None:
            artifact_meta['rerun_reason'] = report.get('rerun_reason')
        if report.get('rerun_requested_at') is not None:
            artifact_meta['rerun_requested_at'] = report.get('rerun_requested_at')
        if report.get('rerun_base_lineage') is not None:
            artifact_meta['rerun_base_lineage'] = dict(report.get('rerun_base_lineage') or {})
        return {
            'report': summary,
            'analysis_artifact': dict(report.get('analysis_artifact') or {}),
            'artifact_meta': artifact_meta,
            'replay_artifact': dict(replay_artifact or {}),
        }

    assert job is not None
    summary = _summary_from_job(job)
    replay_artifact = deps.load_submission_view(summary['target_id']) if summary.get('target_id') else {}
    return {
        'report': summary,
        'analysis_artifact': {},
        'artifact_meta': {
            'submission_id': summary['target_id'],
            'job_status': summary['status'],
            **({'rerun_base_lineage': dict(job.get('rerun_base_lineage') or {})} if job.get('rerun_base_lineage') is not None else {}),
        },
        'replay_artifact': dict(replay_artifact or {}),
    }



def rerun_multimodal_report(report_id: str, *, teacher_id: str, reason: str | None, deps: MultimodalReportDeps) -> Dict[str, Any]:
    teacher_id_final = _require_teacher_id(teacher_id)
    report, job = _load_report_or_job(report_id, deps)
    payload = report or job
    if payload is None or str(payload.get('teacher_id') or '').strip() != teacher_id_final:
        raise MultimodalReportServiceError(404, 'video_homework_report_not_found')

    previous_lineage = extract_analysis_lineage(payload)
    current_lineage = extract_analysis_lineage(payload)
    updates = {
        'rerun_requested': True,
        'rerun_reason': str(reason or '').strip() or None,
        'rerun_requested_at': deps.now_iso(),
        'rerun_requested_by': teacher_id_final,
        'rerun_base_lineage': previous_lineage,
    }
    if report is not None:
        merged = dict(report)
        merged.update(updates)
        write_multimodal_report(report_id, merged, deps=deps)
    else:
        write_multimodal_report_job(report_id, updates, deps=deps)
    metrics_service = getattr(deps, 'metrics_service', None)
    record_rerun = getattr(metrics_service, 'record_rerun', None)
    if callable(record_rerun):
        record_rerun(
            domain='video_homework',
            strategy_id=str(payload.get('strategy_id') or 'video_homework.teacher.report').strip() or 'video_homework.teacher.report',
        )
    return {
        'ok': True,
        'report_id': report_id,
        'status': 'rerun_requested',
        'reason': updates['rerun_reason'],
        'previous_lineage': previous_lineage,
        'current_lineage': current_lineage,
    }



def _load_report_or_job(report_id: str, deps: MultimodalReportDeps) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    report = _read_optional_json(_report_relative_path(report_id), deps)
    if report is not None:
        submission_id = str(report.get('submission_id') or report_id or '').strip() or None
        job = _read_optional_json(_job_relative_path(submission_id), deps) if submission_id else None
        return report, job
    return None, _read_optional_json(_job_relative_path(report_id), deps)



def _summary_from_report(report: Dict[str, Any]) -> Dict[str, Any]:
    report_id = str(report.get('report_id') or report.get('submission_id') or '').strip()
    return {
        'report_id': report_id,
        'teacher_id': str(report.get('teacher_id') or '').strip(),
        'analysis_type': 'video_homework',
        'target_type': str(report.get('target_type') or 'submission').strip() or 'submission',
        'target_id': str(report.get('target_id') or report_id).strip() or report_id,
        'strategy_id': str(report.get('strategy_id') or 'video_homework.teacher.report').strip() or 'video_homework.teacher.report',
        'status': str(report.get('status') or 'analysis_ready').strip() or 'analysis_ready',
        'confidence': _safe_float(report.get('confidence')),
        'summary': str(report.get('summary') or '').strip() or None,
        'created_at': str(report.get('created_at') or '').strip() or None,
        'updated_at': str(report.get('updated_at') or '').strip() or None,
    }



def _summary_from_job(job: Dict[str, Any]) -> Dict[str, Any]:
    submission_id = str(job.get('submission_id') or job.get('report_id') or '').strip()
    return {
        'report_id': str(job.get('report_id') or submission_id).strip() or submission_id,
        'teacher_id': str(job.get('teacher_id') or '').strip(),
        'analysis_type': 'video_homework',
        'target_type': str(job.get('target_type') or 'submission').strip() or 'submission',
        'target_id': str(job.get('target_id') or submission_id).strip() or submission_id,
        'strategy_id': str(job.get('strategy_id') or 'video_homework.teacher.report').strip() or 'video_homework.teacher.report',
        'status': str(job.get('status') or 'queued').strip() or 'queued',
        'confidence': _safe_float(job.get('analysis_confidence')),
        'summary': str(job.get('summary') or '').strip() or None,
        'created_at': str(job.get('created_at') or '').strip() or None,
        'updated_at': str(job.get('updated_at') or '').strip() or None,
    }



def _read_optional_json(relative_path: str, deps: MultimodalReportDeps) -> Optional[Dict[str, Any]]:
    try:
        payload = deps.metadata_repo.read_json(relative_path)
    except FileNotFoundError:
        return None
    return payload if isinstance(payload, dict) else None



def _job_relative_path(submission_id: str | None) -> str:
    return f'jobs/{str(submission_id or "").strip()}.json'



def _report_relative_path(report_id: str | None) -> str:
    return f'reports/{str(report_id or "").strip()}.json'



def _require_teacher_id(teacher_id: str) -> str:
    teacher_id_final = str(teacher_id or '').strip()
    if not teacher_id_final:
        raise MultimodalReportServiceError(400, 'teacher_id_required')
    return teacher_id_final



def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None
