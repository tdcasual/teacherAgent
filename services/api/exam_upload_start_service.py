from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional


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


async def _save_uploads(files: Optional[List[Any]], target_dir: Path, deps: ExamUploadStartDeps) -> List[str]:
    saved: List[str] = []
    for upload in files or []:
        filename = deps.sanitize_filename(getattr(upload, "filename", ""))
        if not filename:
            continue
        dest = target_dir / filename
        await deps.save_upload_file(upload, dest)
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

    saved_paper = await _save_uploads(paper_files, paper_dir, deps)
    saved_scores = await _save_uploads(score_files, scores_dir, deps)
    saved_answers = await _save_uploads(answer_files, answers_dir, deps)

    if not saved_paper:
        raise ValueError("No exam paper files uploaded")
    if not saved_scores:
        raise ValueError("No score files uploaded")

    record = {
        "job_id": job_id,
        "exam_id": str(exam_id or "").strip(),
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
