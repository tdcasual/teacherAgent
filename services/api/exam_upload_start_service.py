from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional

from .auth_service import get_current_principal

MAX_FILES_PER_UPLOAD_FIELD = 20
MAX_UPLOAD_FILE_SIZE_BYTES = 20 * 1024 * 1024
MAX_UPLOAD_TOTAL_SIZE_BYTES = 80 * 1024 * 1024
_ALLOWED_PAPER_SUFFIXES = {
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
_ALLOWED_SCORE_SUFFIXES = {
    ".csv",
    ".xlsx",
    ".xls",
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".bmp",
    ".webp",
}
_ALLOWED_ANSWER_SUFFIXES = _ALLOWED_PAPER_SUFFIXES | {".csv", ".xlsx", ".xls"}


@dataclass(frozen=True)
class ExamUploadStartDeps:
    parse_date_str: Callable[[Any], str]
    exam_job_path: Callable[[str], Path]
    sanitize_filename: Callable[[Optional[str]], str]
    save_upload_file: Callable[[Any, Path], Awaitable[None]]
    write_exam_job: Callable[[str, Dict[str, Any], bool], Dict[str, Any]]
    enqueue_exam_job: Callable[[str], None]
    now_iso: Callable[[], str]
    diag_log: Callable[[str, Dict[str, Any]], None]
    uuid_hex: Callable[[], str]


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
    sanitize_filename: Callable[[Optional[str]], str],
    allowed_suffixes: set[str],
) -> tuple[List[tuple[Any, str]], int]:
    items = [item for item in (files or []) if item is not None]
    if len(items) > MAX_FILES_PER_UPLOAD_FIELD:
        raise ValueError(f"{field_label} 最多上传 {MAX_FILES_PER_UPLOAD_FIELD} 个文件")
    prepared: List[tuple[Any, str]] = []
    known_total = 0
    for upload in items:
        filename = sanitize_filename(getattr(upload, "filename", ""))
        if not filename:
            continue
        suffix = Path(filename).suffix.lower()
        if suffix not in allowed_suffixes:
            raise ValueError(f"不支持的文件类型: {suffix or filename}")
        known_size = _detect_upload_size(upload)
        if known_size is not None:
            if known_size > MAX_UPLOAD_FILE_SIZE_BYTES:
                raise ValueError("单个文件大小不能超过 20MB")
            known_total += known_size
        prepared.append((upload, filename))
    return prepared, known_total


async def _save_uploads(
    files: List[tuple[Any, str]],
    target_dir: Path,
    deps: ExamUploadStartDeps,
    *,
    total_written: List[int],
) -> List[str]:
    saved: List[str] = []
    for upload, filename in files:
        dest = target_dir / filename
        await deps.save_upload_file(upload, dest)
        size_bytes = int(dest.stat().st_size)
        if size_bytes > MAX_UPLOAD_FILE_SIZE_BYTES:
            dest.unlink(missing_ok=True)
            raise ValueError("单个文件大小不能超过 20MB")
        total_written[0] += size_bytes
        if total_written[0] > MAX_UPLOAD_TOTAL_SIZE_BYTES:
            dest.unlink(missing_ok=True)
            raise ValueError("单次上传总大小不能超过 80MB")
        saved.append(filename)
    return saved


async def start_exam_upload(
    exam_id: Optional[str],
    date: Optional[str],
    class_name: Optional[str],
    paper_files: List[Any],
    score_files: List[Any],
    answer_files: Optional[List[Any]],
    ocr_mode: Optional[str],
    language: Optional[str],
    deps: ExamUploadStartDeps,
) -> Dict[str, Any]:
    date_str = deps.parse_date_str(date)
    job_id = f"job_{deps.uuid_hex()[:12]}"
    job_dir = deps.exam_job_path(job_id)
    paper_dir = job_dir / "paper"
    scores_dir = job_dir / "scores"
    answers_dir = job_dir / "answers"
    paper_dir.mkdir(parents=True, exist_ok=True)
    scores_dir.mkdir(parents=True, exist_ok=True)
    answers_dir.mkdir(parents=True, exist_ok=True)

    paper_inputs, paper_known_total = _prepare_uploads(
        paper_files,
        field_label="paper_files",
        sanitize_filename=deps.sanitize_filename,
        allowed_suffixes=_ALLOWED_PAPER_SUFFIXES,
    )
    score_inputs, score_known_total = _prepare_uploads(
        score_files,
        field_label="score_files",
        sanitize_filename=deps.sanitize_filename,
        allowed_suffixes=_ALLOWED_SCORE_SUFFIXES,
    )
    answer_inputs, answer_known_total = _prepare_uploads(
        answer_files,
        field_label="answer_files",
        sanitize_filename=deps.sanitize_filename,
        allowed_suffixes=_ALLOWED_ANSWER_SUFFIXES,
    )
    if (paper_known_total + score_known_total + answer_known_total) > MAX_UPLOAD_TOTAL_SIZE_BYTES:
        raise ValueError("单次上传总大小不能超过 80MB")

    total_written = [0]
    principal = get_current_principal()
    teacher_id = str(getattr(principal, "actor_id", "") or "").strip()
    try:
        saved_paper = await _save_uploads(paper_inputs, paper_dir, deps, total_written=total_written)
        saved_scores = await _save_uploads(score_inputs, scores_dir, deps, total_written=total_written)
        saved_answers = await _save_uploads(answer_inputs, answers_dir, deps, total_written=total_written)

        if not saved_paper:
            raise ValueError("No exam paper files uploaded")
        if not saved_scores:
            raise ValueError("No score files uploaded")

        record = {
            "job_id": job_id,
            "exam_id": str(exam_id or "").strip(),
            "teacher_id": teacher_id,
            "date": date_str,
            "class_name": class_name or "",
            "paper_files": saved_paper,
            "score_files": saved_scores,
            "answer_files": saved_answers,
            "language": language or "zh",
            "ocr_mode": ocr_mode or "FREE_OCR",
            "status": "queued",
            "progress": 0,
            "step": "queued",
            "created_at": deps.now_iso(),
        }
        deps.write_exam_job(job_id, record, True)
        deps.enqueue_exam_job(job_id)
        deps.diag_log("exam_upload.job.created", {"job_id": job_id, "exam_id": record.get("exam_id")})
        return {
            "ok": True,
            "job_id": job_id,
            "exam_id": record.get("exam_id") or None,
            "status": "queued",
            "message": "考试解析任务已创建，后台处理中。",
        }
    except Exception:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise
