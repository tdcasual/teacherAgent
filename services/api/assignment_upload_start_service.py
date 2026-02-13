from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional

from .auth_service import get_current_principal


class AssignmentUploadStartError(Exception):
    def __init__(self, status_code: int, detail: Any):
        super().__init__(str(detail))
        self.status_code = int(status_code)
        self.detail = detail


MAX_FILES_PER_UPLOAD_FIELD = 20
MAX_UPLOAD_FILE_SIZE_BYTES = 20 * 1024 * 1024
MAX_UPLOAD_TOTAL_SIZE_BYTES = 80 * 1024 * 1024
_ASSIGNMENT_ALLOWED_SUFFIXES = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".bmp",
    ".webp",
    ".md",
    ".markdown",
    ".txt",
    ".tex",
}


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


def _detect_upload_size(upload: Any) -> Optional[int]:
    file_obj = getattr(upload, "file", None)
    if file_obj is None:
        return None
    try:
        current = file_obj.tell()
        file_obj.seek(0, 2)
        size = int(file_obj.tell())
        file_obj.seek(current)
        if size < 0:
            return None
        return size
    except Exception:
        return None


def _prepare_uploads(
    files: Optional[List[Any]],
    *,
    field_label: str,
    sanitize_filename: Callable[[Any], str],
) -> tuple[List[tuple[Any, str]], int]:
    items = [item for item in (files or []) if item is not None]
    if len(items) > MAX_FILES_PER_UPLOAD_FIELD:
        raise AssignmentUploadStartError(
            400,
            f"{field_label} 最多上传 {MAX_FILES_PER_UPLOAD_FIELD} 个文件",
        )
    prepared: List[tuple[Any, str]] = []
    known_total = 0
    for upload in items:
        filename = sanitize_filename(getattr(upload, "filename", ""))
        if not filename:
            continue
        suffix = Path(filename).suffix.lower()
        if suffix not in _ASSIGNMENT_ALLOWED_SUFFIXES:
            raise AssignmentUploadStartError(400, f"不支持的文件类型: {suffix or filename}")
        known_size = _detect_upload_size(upload)
        if known_size is not None:
            if known_size > MAX_UPLOAD_FILE_SIZE_BYTES:
                raise AssignmentUploadStartError(400, "单个文件大小不能超过 20MB")
            known_total += known_size
        prepared.append((upload, filename))
    return prepared, known_total


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

    source_inputs, source_known_total = _prepare_uploads(
        files,
        field_label="files",
        sanitize_filename=deps.sanitize_filename,
    )
    answer_inputs, answer_known_total = _prepare_uploads(
        answer_files,
        field_label="answer_files",
        sanitize_filename=deps.sanitize_filename,
    )
    if (source_known_total + answer_known_total) > MAX_UPLOAD_TOTAL_SIZE_BYTES:
        raise AssignmentUploadStartError(400, "单次上传总大小不能超过 80MB")

    saved_sources: List[str] = []
    delivery_mode = "image"
    saved_answers: List[str] = []
    total_written = 0
    principal = get_current_principal()
    teacher_id = str(getattr(principal, "actor_id", "") or "").strip()
    try:
        for upload_file, filename in source_inputs:
            dest = source_dir / filename
            written = await deps.save_upload_file(upload_file, dest)
            size_bytes = int(written if written is not None else dest.stat().st_size)
            if size_bytes > MAX_UPLOAD_FILE_SIZE_BYTES:
                dest.unlink(missing_ok=True)
                raise AssignmentUploadStartError(400, "单个文件大小不能超过 20MB")
            total_written += size_bytes
            if total_written > MAX_UPLOAD_TOTAL_SIZE_BYTES:
                dest.unlink(missing_ok=True)
                raise AssignmentUploadStartError(400, "单次上传总大小不能超过 80MB")
            saved_sources.append(filename)
            if dest.suffix.lower() == ".pdf":
                delivery_mode = "pdf"

        for upload_file, filename in answer_inputs:
            dest = answers_dir / filename
            written = await deps.save_upload_file(upload_file, dest)
            size_bytes = int(written if written is not None else dest.stat().st_size)
            if size_bytes > MAX_UPLOAD_FILE_SIZE_BYTES:
                dest.unlink(missing_ok=True)
                raise AssignmentUploadStartError(400, "单个文件大小不能超过 20MB")
            total_written += size_bytes
            if total_written > MAX_UPLOAD_TOTAL_SIZE_BYTES:
                dest.unlink(missing_ok=True)
                raise AssignmentUploadStartError(400, "单次上传总大小不能超过 80MB")
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
            "teacher_id": teacher_id,
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
    except Exception:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise
