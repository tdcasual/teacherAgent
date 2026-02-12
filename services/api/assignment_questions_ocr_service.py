from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


def _default_sanitize_filename(name: str) -> str:
    return Path(str(name or "").strip()).name


def _default_sanitize_assignment_id(value: str) -> str:
    raw = Path(str(value or "").strip()).name
    slug = re.sub(r"[^\w-]+", "_", raw).strip("_")
    return slug or "assignment"


@dataclass(frozen=True)
class AssignmentQuestionsOcrDeps:
    uploads_dir: Path
    app_root: Path
    run_script: Callable[[list[str]], str]
    sanitize_filename: Callable[[str], str] = _default_sanitize_filename
    sanitize_assignment_id: Callable[[str], str] = _default_sanitize_assignment_id


async def assignment_questions_ocr(
    *,
    assignment_id: str,
    files: List[Any],
    kp_id: Optional[str],
    difficulty: Optional[str],
    tags: Optional[str],
    ocr_mode: Optional[str],
    language: Optional[str],
    deps: AssignmentQuestionsOcrDeps,
) -> Dict[str, Any]:
    deps.uploads_dir.mkdir(parents=True, exist_ok=True)
    safe_assignment_id = deps.sanitize_assignment_id(assignment_id)
    if not safe_assignment_id:
        raise ValueError("invalid assignment_id")
    ocr_root = (deps.uploads_dir / "assignment_ocr").resolve()
    batch_dir = (ocr_root / safe_assignment_id).resolve()
    if batch_dir != ocr_root and ocr_root not in batch_dir.parents:
        raise ValueError("invalid assignment_id path")
    batch_dir.mkdir(parents=True, exist_ok=True)

    file_paths: List[str] = []
    for upload_file in files:
        filename = deps.sanitize_filename(getattr(upload_file, "filename", ""))
        if not filename:
            continue
        dest = batch_dir / filename
        dest.write_bytes(await upload_file.read())
        file_paths.append(str(dest))

    script = deps.app_root / "skills" / "physics-student-coach" / "scripts" / "ingest_assignment_questions.py"
    args = [
        "python3",
        str(script),
        "--assignment-id",
        safe_assignment_id,
        "--kp-id",
        kp_id or "uncategorized",
        "--difficulty",
        difficulty or "basic",
        "--tags",
        tags or "ocr",
        "--ocr-mode",
        ocr_mode or "FREE_OCR",
        "--language",
        language or "zh",
        "--files",
        *file_paths,
    ]
    out = deps.run_script(args)
    return {"ok": True, "output": out, "files": file_paths, "assignment_id": safe_assignment_id}
