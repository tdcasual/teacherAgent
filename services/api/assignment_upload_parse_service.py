from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

_log = logging.getLogger(__name__)



@dataclass(frozen=True)
class AssignmentUploadParseDeps:
    now_iso: Callable[[], str]
    now_monotonic: Callable[[], float]
    load_upload_job: Callable[[str], Dict[str, Any]]
    upload_job_path: Callable[[str], Path]
    write_upload_job: Callable[[str, Dict[str, Any]], Dict[str, Any]]
    extract_text_from_file: Callable[..., str]
    llm_parse_assignment_payload: Callable[[str, str], Dict[str, Any]]
    compute_requirements_missing: Callable[[Dict[str, Any]], List[str]]
    llm_autofill_requirements: Callable[
        [str, str, List[Dict[str, Any]], Dict[str, Any], List[str]],
        Tuple[Dict[str, Any], List[str], bool],
    ]
    diag_log: Callable[[str, Dict[str, Any]], None]


_OCR_HINTS = [
    "图片上传需要 OCR 支持。请确保已配置 OCR API Key（OPENAI_API_KEY/SILICONFLOW_API_KEY）并可访问对应服务。",
    "建议优先上传包含可复制文字的 PDF；若为扫描件/照片，请使用清晰的 JPG/PNG（避免 HEIC）。",
]


def _mark_job_processing(job_id: str, deps: AssignmentUploadParseDeps) -> None:
    deps.write_upload_job(
        job_id,
        {"status": "processing", "step": "extract", "progress": 10, "error": ""},
    )


def _extract_source_text(
    job_id: str,
    job_dir: Path,
    source_dir: Path,
    source_files: List[str],
    *,
    language: str,
    ocr_mode: str,
    deps: AssignmentUploadParseDeps,
) -> Optional[str]:
    source_text_parts: List[str] = []
    t_extract = deps.now_monotonic()
    for fname in source_files:
        path = source_dir / fname
        try:
            source_text_parts.append(
                deps.extract_text_from_file(path, language=language, ocr_mode=ocr_mode)
            )
        except Exception as exc:
            _log.debug("operation failed", exc_info=True)
            msg = str(exc)[:200]
            err_code = "extract_failed"
            if "OCR unavailable" in msg:
                err_code = "ocr_unavailable"
            elif "OCR request failed" in msg or "OCR" in msg:
                err_code = "ocr_failed"
            deps.write_upload_job(
                job_id,
                {
                    "status": "failed",
                    "step": "extract",
                    "progress": 100,
                    "error": err_code,
                    "error_detail": msg,
                    "hints": _OCR_HINTS,
                },
            )
            return None

    source_text = "\n\n".join([text for text in source_text_parts if text])
    (job_dir / "source_text.txt").write_text(source_text or "", encoding="utf-8")
    deps.diag_log(
        "upload.extract.done",
        {
            "job_id": job_id,
            "duration_ms": int((deps.now_monotonic() - t_extract) * 1000),
            "chars": len(source_text),
        },
    )
    if not source_text.strip():
        deps.write_upload_job(
            job_id,
            {
                "status": "failed",
                "error": "source_text_empty",
                "hints": _OCR_HINTS,
                "progress": 100,
            },
        )
        return None
    return source_text


def _extract_answer_text(
    job_dir: Path,
    answers_dir: Path,
    answer_files: List[str],
    *,
    language: str,
    ocr_mode: str,
    deps: AssignmentUploadParseDeps,
) -> str:
    answer_text_parts: List[str] = []
    for fname in answer_files:
        path = answers_dir / fname
        try:
            answer_text_parts.append(
                deps.extract_text_from_file(path, language=language, ocr_mode=ocr_mode)
            )
        except Exception:
            _log.debug("operation failed", exc_info=True)
            continue
    answer_text = "\n\n".join([text for text in answer_text_parts if text])
    if answer_text:
        (job_dir / "answer_text.txt").write_text(answer_text, encoding="utf-8")
    return answer_text


def _parse_assignment_payload(
    job_id: str, source_text: str, answer_text: str, deps: AssignmentUploadParseDeps
) -> Optional[Dict[str, Any]]:
    deps.write_upload_job(job_id, {"step": "parse", "progress": 55})
    t_parse = deps.now_monotonic()
    parsed = deps.llm_parse_assignment_payload(source_text, answer_text)
    deps.diag_log(
        "upload.parse.done",
        {
            "job_id": job_id,
            "duration_ms": int((deps.now_monotonic() - t_parse) * 1000),
        },
    )
    if parsed.get("error"):
        deps.write_upload_job(
            job_id,
            {
                "status": "failed",
                "error": parsed.get("error"),
                "progress": 100,
            },
        )
        return None
    return parsed


def _validate_questions(
    job_id: str, parsed: Dict[str, Any], deps: AssignmentUploadParseDeps
) -> Optional[List[Dict[str, Any]]]:
    questions = parsed.get("questions") or []
    if not isinstance(questions, list) or not questions:
        deps.write_upload_job(
            job_id,
            {
                "status": "failed",
                "error": "no questions parsed",
                "progress": 100,
            },
        )
        return None
    return questions


def _enrich_requirements(
    source_text: str,
    answer_text: str,
    questions: List[Dict[str, Any]],
    parsed: Dict[str, Any],
    deps: AssignmentUploadParseDeps,
) -> Tuple[Dict[str, Any], List[str], List[str], bool]:
    requirements = parsed.get("requirements") or {}
    missing = deps.compute_requirements_missing(requirements)
    warnings: List[str] = []
    if len(source_text.strip()) < 200:
        warnings.append("解析文本较少，作业要求可能不完整。")

    autofilled = False
    if missing:
        requirements, missing, autofilled = deps.llm_autofill_requirements(
            source_text,
            answer_text,
            questions,
            requirements,
            missing,
        )
        if autofilled and missing:
            warnings.append("已自动补全部分要求，请核对并补充缺失项。")
    return requirements, missing, warnings, autofilled


def _write_parsed_payload(
    job_dir: Path,
    *,
    questions: List[Dict[str, Any]],
    requirements: Dict[str, Any],
    missing: List[str],
    warnings: List[str],
    delivery_mode: str,
    autofilled: bool,
    deps: AssignmentUploadParseDeps,
) -> None:
    parsed_payload = {
        "questions": questions,
        "requirements": requirements,
        "missing": missing,
        "warnings": warnings,
        "delivery_mode": delivery_mode,
        "question_count": len(questions),
        "autofilled": autofilled,
        "generated_at": deps.now_iso(),
    }
    (job_dir / "parsed.json").write_text(
        json.dumps(parsed_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _build_questions_preview(questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    preview_items: List[Dict[str, Any]] = []
    for idx, question in enumerate(questions[:3], start=1):
        preview_items.append({"id": idx, "stem": str(question.get("stem") or "")[:160]})
    return preview_items


def _write_done_status(
    job_id: str,
    *,
    questions: List[Dict[str, Any]],
    requirements: Dict[str, Any],
    missing: List[str],
    warnings: List[str],
    delivery_mode: str,
    autofilled: bool,
    deps: AssignmentUploadParseDeps,
) -> None:
    deps.write_upload_job(
        job_id,
        {
            "status": "done",
            "step": "done",
            "progress": 100,
            "question_count": len(questions),
            "requirements_missing": missing,
            "requirements": requirements,
            "warnings": warnings,
            "delivery_mode": delivery_mode,
            "questions_preview": _build_questions_preview(questions),
            "autofilled": autofilled,
            "draft_version": 1,
        },
    )


def process_upload_job(job_id: str, deps: AssignmentUploadParseDeps) -> None:
    job = deps.load_upload_job(job_id)
    job_dir = deps.upload_job_path(job_id)
    source_dir = job_dir / "source"
    answers_dir = job_dir / "answer_source"
    source_files = job.get("source_files") or []
    answer_files = job.get("answer_files") or []
    language = job.get("language") or "zh"
    ocr_mode = job.get("ocr_mode") or "FREE_OCR"
    delivery_mode = job.get("delivery_mode") or "image"

    _mark_job_processing(job_id, deps)
    if not source_files:
        deps.write_upload_job(
            job_id,
            {"status": "failed", "error": "no source files", "progress": 100},
        )
        return

    source_text = _extract_source_text(
        job_id,
        job_dir,
        source_dir,
        source_files,
        language=language,
        ocr_mode=ocr_mode,
        deps=deps,
    )
    if source_text is None:
        return

    answer_text = _extract_answer_text(
        job_dir,
        answers_dir,
        answer_files,
        language=language,
        ocr_mode=ocr_mode,
        deps=deps,
    )
    parsed = _parse_assignment_payload(job_id, source_text, answer_text, deps)
    if parsed is None:
        return

    questions = _validate_questions(job_id, parsed, deps)
    if questions is None:
        return

    requirements, missing, warnings, autofilled = _enrich_requirements(
        source_text, answer_text, questions, parsed, deps
    )
    _write_parsed_payload(
        job_dir,
        questions=questions,
        requirements=requirements,
        missing=missing,
        warnings=warnings,
        delivery_mode=delivery_mode,
        autofilled=autofilled,
        deps=deps,
    )
    _write_done_status(
        job_id,
        questions=questions,
        requirements=requirements,
        missing=missing,
        warnings=warnings,
        delivery_mode=delivery_mode,
        autofilled=autofilled,
        deps=deps,
    )
