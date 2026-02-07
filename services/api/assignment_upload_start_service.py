from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional


class AssignmentUploadStartError(Exception):
    def __init__(self, status_code: int, detail: Any):
        super().__init__(str(detail))
        self.status_code = int(status_code)
        self.detail = detail


@dataclass(frozen=True)
class AssignmentUploadStartDeps:
    new_job_id: Callable[[], str]
    parse_date_str: Callable[[Any], str]
    upload_job_path: Callable[[str], Path]
    sanitize_filename: Callable[[Any], str]
    save_upload_file: Callable[[Any, Path], Awaitable[int]]
    parse_ids_value: Callable[[Any], List[str]]
    resolve_scope: Callable[[str, List[str], str], str]
    normalize_due_at: Callable[[Any], str]
    now_iso: Callable[[], str]
    write_upload_job: Callable[[str, Dict[str, Any], bool], Dict[str, Any]]
    enqueue_upload_job: Callable[[str], None]
    diag_log: Callable[[str, Optional[Dict[str, Any]]], None]


async def start_assignment_upload(
    *,
    assignment_id: str,
    date: Any,
    due_at: Any,
    scope: Any,
    class_name: Any,
    student_ids: Any,
    files: List[Any],
    answer_files: Optional[List[Any]],
    ocr_mode: Any,
    language: Any,
    deps: AssignmentUploadStartDeps,
) -> Dict[str, Any]:
    date_str = deps.parse_date_str(date)
    job_id = deps.new_job_id()
    job_dir = deps.upload_job_path(job_id)
    source_dir = job_dir / "source"
    answers_dir = job_dir / "answer_source"
    source_dir.mkdir(parents=True, exist_ok=True)
    answers_dir.mkdir(parents=True, exist_ok=True)

    saved_sources: List[str] = []
    delivery_mode = "image"
    for upload_file in files:
        filename = deps.sanitize_filename(getattr(upload_file, "filename", ""))
        if not filename:
            continue
        dest = source_dir / filename
        await deps.save_upload_file(upload_file, dest)
        saved_sources.append(filename)
        if dest.suffix.lower() == ".pdf":
            delivery_mode = "pdf"

    saved_answers: List[str] = []
    if answer_files:
        for upload_file in answer_files:
            filename = deps.sanitize_filename(getattr(upload_file, "filename", ""))
            if not filename:
                continue
            dest = answers_dir / filename
            await deps.save_upload_file(upload_file, dest)
            saved_answers.append(filename)

    if not saved_sources:
        raise AssignmentUploadStartError(400, "No source files uploaded")

    student_ids_list = deps.parse_ids_value(student_ids)
    scope_val = deps.resolve_scope(str(scope or ""), student_ids_list, str(class_name or ""))
    if scope_val == "student" and not student_ids_list:
        raise AssignmentUploadStartError(400, "student scope requires student_ids")
    if scope_val == "class" and not class_name:
        raise AssignmentUploadStartError(400, "class scope requires class_name")

    record = {
        "job_id": job_id,
        "assignment_id": assignment_id,
        "date": date_str,
        "due_at": deps.normalize_due_at(due_at),
        "scope": scope_val,
        "class_name": class_name or "",
        "student_ids": student_ids_list,
        "source_files": saved_sources,
        "answer_files": saved_answers,
        "delivery_mode": delivery_mode,
        "language": language or "zh",
        "ocr_mode": ocr_mode or "FREE_OCR",
        "status": "queued",
        "progress": 0,
        "step": "queued",
        "created_at": deps.now_iso(),
    }
    deps.write_upload_job(job_id, record, True)
    deps.enqueue_upload_job(job_id)
    deps.diag_log("upload.job.created", {"job_id": job_id, "assignment_id": assignment_id})

    return {
        "ok": True,
        "job_id": job_id,
        "assignment_id": assignment_id,
        "status": "queued",
        "message": "解析任务已创建，后台处理中。",
    }
