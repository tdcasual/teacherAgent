from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


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
    confirm_exam_upload: Callable[[str, Dict[str, Any], Path], Dict[str, Any]]


def _load_job_or_raise(job_id: str, *, deps: ExamUploadApiDeps) -> Dict[str, Any]:
    try:
        return deps.load_exam_job(job_id)
    except FileNotFoundError as exc:
        raise ExamUploadApiError(status_code=404, detail="job not found") from exc


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
    deps.write_exam_job(job_id, {"draft_version": new_version})
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
    try:
        return deps.confirm_exam_upload(job_id, job, job_dir)
    except Exception as exc:
        status_code = getattr(exc, "status_code", None)
        if status_code is not None:
            raise ExamUploadApiError(status_code=status_code, detail=getattr(exc, "detail", str(exc))) from exc
        raise
