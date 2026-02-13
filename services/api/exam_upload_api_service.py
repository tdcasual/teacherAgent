from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .auth_service import AuthError, enforce_upload_job_access

_log = logging.getLogger(__name__)



class ExamUploadApiError(Exception):
    def __init__(self, status_code: int, detail: Any):
        super().__init__(str(detail))
        self.status_code = int(status_code)
        self.detail = detail


@dataclass(frozen=True)
class ExamUploadApiDeps:
    load_exam_job: Callable[[str], Dict[str, Any]]
    exam_job_path: Callable[[str], Path]
    load_exam_draft_override: Callable[[Path], Dict[str, Any]]
    save_exam_draft_override: Callable[..., Dict[str, Any]]
    build_exam_upload_draft: Callable[..., Dict[str, Any]]
    exam_upload_not_ready_detail: Callable[[Dict[str, Any], str], Dict[str, Any]]
    parse_exam_answer_key_text: Callable[[str], Tuple[List[Dict[str, Any]], List[str]]]
    read_text_safe: Callable[[Path, int], str]
    write_exam_job: Callable[[str, Dict[str, Any]], None]
    enqueue_exam_job: Callable[[str], None]
    confirm_exam_upload: Callable[[str, Dict[str, Any], Path], Dict[str, Any]]


def _as_dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _selected_candidate_id_from_schema(schema: Dict[str, Any]) -> str:
    subject = _as_dict(schema.get("subject"))
    return str(subject.get("selected_candidate_id") or schema.get("selected_candidate_id") or "").strip()


def _load_job_or_raise(job_id: str, *, deps: ExamUploadApiDeps) -> Dict[str, Any]:
    try:
        job = deps.load_exam_job(job_id)
    except FileNotFoundError as exc:
        raise ExamUploadApiError(status_code=404, detail="job not found") from exc
    try:
        enforce_upload_job_access(job)
    except AuthError as exc:
        raise ExamUploadApiError(status_code=exc.status_code, detail=exc.detail) from exc
    return job


def exam_upload_status(job_id: str, *, deps: ExamUploadApiDeps) -> Dict[str, Any]:
    return _load_job_or_raise(job_id, deps=deps)


def exam_upload_draft(job_id: str, *, deps: ExamUploadApiDeps) -> Dict[str, Any]:
    job = _load_job_or_raise(job_id, deps=deps)
    status = job.get("status")
    if status not in {"done", "confirmed"}:
        raise ExamUploadApiError(
            status_code=400,
            detail=deps.exam_upload_not_ready_detail(job, "解析尚未完成，暂无法打开草稿。"),
        )

    job_dir = deps.exam_job_path(job_id)
    parsed_path = job_dir / "parsed.json"
    if not parsed_path.exists():
        raise ExamUploadApiError(status_code=400, detail="parsed result missing")

    parsed = json.loads(parsed_path.read_text(encoding="utf-8"))
    override = deps.load_exam_draft_override(job_dir)
    try:
        answer_text_excerpt = deps.read_text_safe(job_dir / "answer_text.txt", 6000)
    except Exception:
        _log.debug("JSON parse failed", exc_info=True)
        answer_text_excerpt = ""
    draft = deps.build_exam_upload_draft(
        job_id,
        job,
        parsed,
        override,
        parse_exam_answer_key_text=deps.parse_exam_answer_key_text,
        answer_text_excerpt=answer_text_excerpt,
    )
    return {"ok": True, "draft": draft}


def exam_upload_draft_save(
    *,
    job_id: str,
    meta: Optional[Dict[str, Any]] = None,
    questions: Optional[List[Dict[str, Any]]] = None,
    score_schema: Optional[Dict[str, Any]] = None,
    answer_key_text: Optional[str] = None,
    reparse: bool = False,
    deps: ExamUploadApiDeps,
) -> Dict[str, Any]:
    job = _load_job_or_raise(job_id, deps=deps)
    if job.get("status") not in {"done", "confirmed"}:
        raise ExamUploadApiError(
            status_code=400,
            detail=deps.exam_upload_not_ready_detail(job, "解析尚未完成，暂无法保存草稿。"),
        )

    job_dir = deps.exam_job_path(job_id)
    override = deps.load_exam_draft_override(job_dir)
    deps.save_exam_draft_override(
        job_dir,
        override,
        meta=meta,
        questions=questions,
        score_schema=score_schema,
        answer_key_text=answer_key_text,
    )
    new_version = int(job.get("draft_version") or 1) + 1

    previous_score_schema = _as_dict(job.get("score_schema"))
    previous_selected_candidate_id = _selected_candidate_id_from_schema(previous_score_schema)
    selected_candidate_id = _selected_candidate_id_from_schema(score_schema or {})

    reparse_needed = bool(reparse and selected_candidate_id and selected_candidate_id != previous_selected_candidate_id)
    updates: Dict[str, Any] = {"draft_version": new_version}
    if reparse_needed:
        updates.update(
            {
                "status": "queued",
                "step": "reparse_scores",
                "progress": 0,
                "error": "",
                "error_detail": "",
                "score_schema": score_schema,
            }
        )
    deps.write_exam_job(job_id, updates)
    if reparse_needed:
        deps.enqueue_exam_job(job_id)
    return {"ok": True, "job_id": job_id, "message": "考试草稿已保存。", "draft_version": new_version}


def exam_upload_confirm(job_id: str, *, deps: ExamUploadApiDeps) -> Dict[str, Any]:
    job = _load_job_or_raise(job_id, deps=deps)
    status = job.get("status")
    if status == "confirmed":
        return {"ok": True, "exam_id": job.get("exam_id"), "status": "confirmed", "message": "考试已创建（已确认）。"}
    if status != "done":
        raise ExamUploadApiError(
            status_code=400,
            detail=deps.exam_upload_not_ready_detail(job, "解析尚未完成，请稍后再确认创建考试。"),
        )

    job_dir = deps.exam_job_path(job_id)
    override = deps.load_exam_draft_override(job_dir)
    override_score_schema = _as_dict(override.get("score_schema"))
    job_score_schema = _as_dict(job.get("score_schema"))
    effective_score_schema = {**job_score_schema, **override_score_schema}
    selected_candidate_id = _selected_candidate_id_from_schema(effective_score_schema)
    subject_info = _as_dict(effective_score_schema.get("subject"))
    selected_candidate_available = bool(subject_info.get("selected_candidate_available", True))
    selection_error = str(subject_info.get("selection_error") or "").strip()
    candidate_selection_valid = bool((not selected_candidate_id) or (selected_candidate_available and not selection_error))
    confirmed_mapping = bool((selected_candidate_id and candidate_selection_valid) or effective_score_schema.get("confirm"))

    if bool(job.get("needs_confirm")) and not confirmed_mapping:
        raise ExamUploadApiError(
            status_code=400,
            detail={
                "error": "score_schema_confirm_required",
                "message": "成绩映射置信度不足，请先在草稿中确认物理分映射后再创建考试。",
                "needs_confirm": True,
            },
        )

    try:
        return deps.confirm_exam_upload(job_id, job, job_dir)
    except Exception as exc:
        _log.debug("operation failed", exc_info=True)
        status_code = getattr(exc, "status_code", None)
        if status_code is not None:
            raise ExamUploadApiError(status_code=status_code, detail=getattr(exc, "detail", str(exc))) from exc
        raise
