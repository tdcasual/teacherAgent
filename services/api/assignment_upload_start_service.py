from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional

from .auth_service import get_current_principal
from .paths import InvalidAssignmentDate
from .upload_limits import MAX_FILE_BYTES, MAX_FILES, MAX_TOTAL_BYTES


class AssignmentUploadStartError(Exception):
    def __init__(self, status_code: int, detail: Any):
        super().__init__(str(detail))
        self.status_code = int(status_code)
        self.detail = detail


MAX_FILES_PER_UPLOAD_FIELD = MAX_FILES
MAX_UPLOAD_FILE_SIZE_BYTES = MAX_FILE_BYTES
MAX_UPLOAD_TOTAL_SIZE_BYTES = MAX_TOTAL_BYTES
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
    optional_assignment_date: Callable[[Any], Optional[str]]
    upload_job_path: Callable[[str], Path]
    sanitize_filename: Callable[[Any], str]
    save_upload_file: Callable[[Any, Path], Awaitable[int]]
    parse_ids_value: Callable[[Any], List[str]]
    resolve_scope: Callable[[str, List[str], str], str]
    normalize_due_at: Callable[[Any], Optional[str]]
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


def _ensure_total_upload_size(known_total: int) -> None:
    if known_total > MAX_UPLOAD_TOTAL_SIZE_BYTES:
        raise AssignmentUploadStartError(400, "单次上传总大小不能超过 80MB")


async def _save_upload(
    upload_file: Any,
    dest: Path,
    *,
    deps: AssignmentUploadStartDeps,
    total_written: int,
) -> int:
    written = await deps.save_upload_file(upload_file, dest)
    size_bytes = int(written if written is not None else dest.stat().st_size)
    if size_bytes > MAX_UPLOAD_FILE_SIZE_BYTES:
        dest.unlink(missing_ok=True)
        raise AssignmentUploadStartError(400, "单个文件大小不能超过 20MB")
    next_total = total_written + size_bytes
    if next_total > MAX_UPLOAD_TOTAL_SIZE_BYTES:
        dest.unlink(missing_ok=True)
        raise AssignmentUploadStartError(400, "单次上传总大小不能超过 80MB")
    return next_total


async def _save_upload_batch(
    prepared_inputs: List[tuple[Any, str]],
    target_dir: Path,
    *,
    deps: AssignmentUploadStartDeps,
    total_written: int,
    track_pdf: bool = False,
    delivery_mode: str = "image",
) -> tuple[List[str], int, str]:
    saved_files: List[str] = []
    for upload_file, filename in prepared_inputs:
        dest = target_dir / filename
        total_written = await _save_upload(
            upload_file,
            dest,
            deps=deps,
            total_written=total_written,
        )
        saved_files.append(filename)
        if track_pdf and dest.suffix.lower() == ".pdf":
            delivery_mode = "pdf"
    return saved_files, total_written, delivery_mode


def _validate_upload_scope(scope_val: str, student_ids_list: List[str], class_name: Any) -> None:
    if scope_val == "student" and not student_ids_list:
        raise AssignmentUploadStartError(400, "student scope requires student_ids")
    if scope_val == "class" and not class_name:
        raise AssignmentUploadStartError(400, "class scope requires class_name")


def _require_subject_id(subject_id: Any) -> str:
    raw = str(subject_id or "").strip()
    if not raw:
        raise AssignmentUploadStartError(400, "subject_id_required")
    return raw


def _job_assignment_date(date: Any, deps: AssignmentUploadStartDeps) -> str:
    try:
        parsed = deps.optional_assignment_date(date)
    except InvalidAssignmentDate as exc:
        raise AssignmentUploadStartError(400, "invalid_assignment_date") from exc
    return str(parsed or "")


def _principal_teacher_id() -> str:
    principal = get_current_principal()
    return str(getattr(principal, "actor_id", "") or "").strip()


def _require_teacher_id() -> str:
    teacher_id = _principal_teacher_id()
    if not teacher_id:
        raise AssignmentUploadStartError(400, "teacher_id_required")
    return teacher_id


def _build_upload_record(
    *,
    job_id: str,
    assignment_id: str,
    teacher_id: str,
    date_str: str,
    due_at: Any,
    subject_id: str,
    scope_val: str,
    class_name: Any,
    student_ids_list: List[str],
    saved_sources: List[str],
    saved_answers: List[str],
    delivery_mode: str,
    language: Any,
    ocr_mode: Any,
    deps: AssignmentUploadStartDeps,
) -> Dict[str, Any]:
    return {
        "job_id": job_id,
        "assignment_id": assignment_id,
        "teacher_id": teacher_id,
        "subject_id": subject_id,
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


def _queue_upload_job(
    job_id: str,
    assignment_id: str,
    record: Dict[str, Any],
    *,
    deps: AssignmentUploadStartDeps,
) -> None:
    deps.write_upload_job(job_id, record, True)
    deps.enqueue_upload_job(job_id)
    deps.diag_log("upload.job.created", {"job_id": job_id, "assignment_id": assignment_id})


async def start_assignment_upload(
    *,
    assignment_id: str,
    date: Any,
    due_at: Any,
    subject_id: Any,
    scope: Any,
    class_name: Any,
    student_ids: Any,
    files: List[Any],
    answer_files: Optional[List[Any]],
    ocr_mode: Any,
    language: Any,
    deps: AssignmentUploadStartDeps,
) -> Dict[str, Any]:
    date_str = _job_assignment_date(date, deps)
    subject_id_val = _require_subject_id(subject_id)
    teacher_id = _require_teacher_id()
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
    _ensure_total_upload_size(source_known_total + answer_known_total)

    try:
        saved_sources, total_written, delivery_mode = await _save_upload_batch(
            source_inputs,
            source_dir,
            deps=deps,
            total_written=0,
            track_pdf=True,
        )
        saved_answers, total_written, delivery_mode = await _save_upload_batch(
            answer_inputs,
            answers_dir,
            deps=deps,
            total_written=total_written,
            delivery_mode=delivery_mode,
        )
        if not saved_sources:
            raise AssignmentUploadStartError(400, "No source files uploaded")

        student_ids_list = deps.parse_ids_value(student_ids)
        scope_val = deps.resolve_scope(str(scope or ""), student_ids_list, str(class_name or ""))
        _validate_upload_scope(scope_val, student_ids_list, class_name)
        record = _build_upload_record(
            job_id=job_id,
            assignment_id=assignment_id,
            teacher_id=teacher_id,
            date_str=date_str,
            due_at=due_at,
            subject_id=subject_id_val,
            scope_val=scope_val,
            class_name=class_name,
            student_ids_list=student_ids_list,
            saved_sources=saved_sources,
            saved_answers=saved_answers,
            delivery_mode=delivery_mode,
            language=language,
            ocr_mode=ocr_mode,
            deps=deps,
        )
        _queue_upload_job(job_id, assignment_id, record, deps=deps)

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
