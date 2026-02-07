from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional


class AssignmentUploadLegacyError(Exception):
    def __init__(self, *, status_code: int, detail: Any):
        super().__init__(str(detail))
        self.status_code = status_code
        self.detail = detail


@dataclass(frozen=True)
class AssignmentUploadLegacyDeps:
    data_dir: Path
    parse_date_str: Callable[[Optional[str]], str]
    sanitize_filename: Callable[[Optional[str]], str]
    save_upload_file: Callable[[Any, Path], Awaitable[None]]
    extract_text_from_pdf: Callable[[Path, str, str], str]
    extract_text_from_image: Callable[[Path, str, str], str]
    llm_parse_assignment_payload: Callable[[str, str], Dict[str, Any]]
    write_uploaded_questions: Callable[[Path, str, List[Dict[str, Any]]], List[Dict[str, Any]]]
    compute_requirements_missing: Callable[[Dict[str, Any]], List[str]]
    llm_autofill_requirements: Callable[[str, str, List[Dict[str, Any]], Dict[str, Any], List[str]], Any]
    save_assignment_requirements: Callable[..., Dict[str, Any]]
    parse_ids_value: Callable[[Any], List[str]]
    resolve_scope: Callable[[str, List[str], str], str]
    load_assignment_meta: Callable[[Path], Dict[str, Any]]
    now_iso: Callable[[], str]


async def assignment_upload(
    *,
    deps: AssignmentUploadLegacyDeps,
    assignment_id: str,
    date: Optional[str],
    scope: Optional[str],
    class_name: Optional[str],
    student_ids: Optional[str],
    files: List[Any],
    answer_files: Optional[List[Any]],
    ocr_mode: Optional[str],
    language: Optional[str],
) -> Dict[str, Any]:
    date_str = deps.parse_date_str(date)
    out_dir = deps.data_dir / "assignments" / assignment_id
    source_dir = out_dir / "source"
    answers_dir = out_dir / "answer_source"
    source_dir.mkdir(parents=True, exist_ok=True)
    answers_dir.mkdir(parents=True, exist_ok=True)

    saved_sources = []
    delivery_mode = "image"
    for f in files:
        fname = deps.sanitize_filename(getattr(f, "filename", ""))
        if not fname:
            continue
        dest = source_dir / fname
        await deps.save_upload_file(f, dest)
        saved_sources.append(fname)
        suffix = dest.suffix.lower()
        if suffix == ".pdf":
            delivery_mode = "pdf"
        elif suffix in {".md", ".markdown", ".tex", ".txt"} and delivery_mode != "pdf":
            delivery_mode = "text"

    saved_answers = []
    if answer_files:
        for f in answer_files:
            fname = deps.sanitize_filename(getattr(f, "filename", ""))
            if not fname:
                continue
            dest = answers_dir / fname
            await deps.save_upload_file(f, dest)
            saved_answers.append(fname)

    if not saved_sources:
        raise AssignmentUploadLegacyError(status_code=400, detail="No source files uploaded")

    source_text_parts = []
    extraction_warnings: List[str] = []
    for fname in saved_sources:
        path = source_dir / fname
        if path.suffix.lower() == ".pdf":
            source_text_parts.append(deps.extract_text_from_pdf(path, language or "zh", ocr_mode or "FREE_OCR"))
        else:
            source_text_parts.append(deps.extract_text_from_image(path, language or "zh", ocr_mode or "FREE_OCR"))
    source_text = "\n\n".join([t for t in source_text_parts if t])
    (out_dir / "source_text.txt").write_text(source_text or "", encoding="utf-8")

    if not source_text.strip():
        raise AssignmentUploadLegacyError(
            status_code=400,
            detail={
                "error": "source_text_empty",
                "message": "未能从上传文件中解析出文本。",
                "hints": [
                    "如果是扫描件，请确保 OCR 可用，或上传更清晰的图片。",
                    "如果是 PDF，请确认包含可复制文字。",
                    "也可以上传答案文件帮助解析。",
                ],
            },
        )
    if len(source_text.strip()) < 200:
        extraction_warnings.append("解析文本较少，作业要求可能不完整。")

    answer_text_parts = []
    for fname in saved_answers:
        path = answers_dir / fname
        if path.suffix.lower() == ".pdf":
            answer_text_parts.append(deps.extract_text_from_pdf(path, language or "zh", ocr_mode or "FREE_OCR"))
        else:
            answer_text_parts.append(deps.extract_text_from_image(path, language or "zh", ocr_mode or "FREE_OCR"))
    answer_text = "\n\n".join([t for t in answer_text_parts if t])
    if answer_text:
        (out_dir / "answer_text.txt").write_text(answer_text, encoding="utf-8")

    parsed = deps.llm_parse_assignment_payload(source_text, answer_text)
    if parsed.get("error"):
        raise AssignmentUploadLegacyError(status_code=400, detail=parsed)

    questions = parsed.get("questions") or []
    if not isinstance(questions, list) or not questions:
        raise AssignmentUploadLegacyError(status_code=400, detail="No questions parsed from source")

    rows = deps.write_uploaded_questions(out_dir, assignment_id, questions)

    requirements = parsed.get("requirements") or {}
    missing = deps.compute_requirements_missing(requirements)
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
            extraction_warnings.append("作业要求已自动补全部分字段，请核对并补充缺失项。")
    deps.save_assignment_requirements(
        assignment_id,
        requirements,
        date_str,
        created_by="teacher_upload",
        validate=False,
    )

    student_ids_list = deps.parse_ids_value(student_ids)
    scope_val = deps.resolve_scope(scope or "", student_ids_list, class_name or "")
    if scope_val == "student" and not student_ids_list:
        raise AssignmentUploadLegacyError(status_code=400, detail="student scope requires student_ids")

    meta_path = out_dir / "meta.json"
    meta = deps.load_assignment_meta(out_dir) if meta_path.exists() else {}
    meta.update(
        {
            "assignment_id": assignment_id,
            "date": date_str,
            "mode": "upload",
            "target_kp": requirements.get("core_concepts") or [],
            "question_ids": [row.get("question_id") for row in rows if row.get("question_id")],
            "class_name": class_name or "",
            "student_ids": student_ids_list,
            "scope": scope_val,
            "source": "teacher",
            "delivery_mode": delivery_mode,
            "source_files": saved_sources,
            "answer_files": saved_answers,
            "requirements_missing": missing,
            "requirements_autofilled": autofilled,
            "generated_at": deps.now_iso(),
        }
    )
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "ok": True,
        "status": "partial" if missing else "ok",
        "message": "作业创建成功" + ("，已自动补全部分要求，请补充缺失项。" if missing else "。"),
        "assignment_id": assignment_id,
        "date": date_str,
        "delivery_mode": delivery_mode,
        "question_count": len(rows),
        "requirements_missing": missing,
        "requirements_autofilled": autofilled,
        "requirements": requirements,
        "warnings": extraction_warnings,
    }
