from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


def _default_sanitize_filename(name: str) -> str:
    return Path(str(name or "").strip()).name


@dataclass(frozen=True)
class AssignmentQuestionsOcrDeps:
    uploads_dir: Path
    app_root: Path
    run_script: Callable[[list[str]], str]
    sanitize_filename: Callable[[str], str] = _default_sanitize_filename


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
    batch_dir = deps.uploads_dir / "assignment_ocr" / assignment_id
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
        assignment_id,
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
    return {"ok": True, "output": out, "files": file_paths}
