from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from .config import DATA_DIR, UPLOADS_DIR
from .survey_report_render_service import render_survey_report
from .survey_repository import write_survey_report


@dataclass(frozen=True)
class SurveyDeliveryDeps:
    write_survey_report: Callable[[str, Dict[str, Any]], Any]
    render_survey_report: Callable[..., Dict[str, Any]]
    now_iso: Callable[[], str]



def build_survey_delivery_deps(core: Any | None = None) -> SurveyDeliveryDeps:
    _ = DATA_DIR, UPLOADS_DIR
    return SurveyDeliveryDeps(
        write_survey_report=lambda report_id, payload: write_survey_report(report_id, payload, core=core),
        render_survey_report=render_survey_report,
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
    )



def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None



def deliver_survey_report(
    *,
    job: Dict[str, Any],
    bundle: Dict[str, Any],
    analysis_artifact: Dict[str, Any],
    deps: SurveyDeliveryDeps,
) -> Dict[str, Any]:
    job_id = str(job.get("job_id") or "").strip()
    report_id = str(job.get("report_id") or job_id or "").strip() or job_id
    report_summary = {
        "report_id": report_id,
        "job_id": job_id,
        "teacher_id": str(job.get("teacher_id") or "").strip(),
        "class_name": str(job.get("class_name") or "").strip() or None,
        "analysis_type": str(job.get("analysis_type") or "survey").strip() or "survey",
        "target_type": str(job.get("target_type") or "report").strip() or "report",
        "target_id": str(job.get("target_id") or report_id).strip() or report_id,
        "strategy_id": str(job.get("strategy_id") or "survey.teacher.report").strip() or "survey.teacher.report",
        "status": "analysis_ready",
        "confidence": _safe_float((analysis_artifact.get("confidence_and_gaps") or {}).get("confidence"))
        or _safe_float(bundle.get("parse_confidence")),
        "summary": str(analysis_artifact.get("executive_summary") or "").strip() or None,
        "created_at": str(job.get("created_at") or "").strip() or deps.now_iso(),
        "updated_at": deps.now_iso(),
    }
    bundle_meta = {
        "parse_confidence": _safe_float(bundle.get("parse_confidence")),
        "missing_fields": list(bundle.get("missing_fields") or []),
        "provenance": dict(bundle.get("provenance") or {}),
    }
    rendered = deps.render_survey_report(
        report=report_summary,
        analysis_artifact=analysis_artifact,
        bundle_meta=bundle_meta,
    )
    payload = {
        **report_summary,
        "analysis_artifact": dict(analysis_artifact),
        "bundle_meta": bundle_meta,
        "rendered_markdown": rendered["markdown"],
        "rendered_json": rendered["json"],
    }
    deps.write_survey_report(report_id, payload)
    return payload
