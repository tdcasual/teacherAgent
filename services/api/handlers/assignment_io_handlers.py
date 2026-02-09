from __future__ import annotations

import inspect
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from fastapi import HTTPException
from fastapi.responses import FileResponse

from ..assignment_generate_service import AssignmentGenerateError


@dataclass
class AssignmentIoHandlerDeps:
    resolve_assignment_dir: Callable[[str], Path]
    sanitize_filename: Callable[[str], str]
    run_script: Callable[[list[str]], str]
    assignment_questions_ocr: Callable[..., Any]
    generate_assignment: Callable[..., Any]
    app_root: Path


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def assignment_download(assignment_id: str, file: str, *, deps: AssignmentIoHandlerDeps):
    try:
        assignment_dir = deps.resolve_assignment_dir(assignment_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    folder = (assignment_dir / "source").resolve()
    if assignment_dir not in folder.parents:
        raise HTTPException(status_code=400, detail="invalid assignment_id path")
    if not folder.exists():
        raise HTTPException(status_code=404, detail="assignment source not found")
    safe_name = deps.sanitize_filename(file)
    if not safe_name:
        raise HTTPException(status_code=400, detail="invalid file")
    path = (folder / safe_name).resolve()
    if path != folder and folder not in path.parents:
        raise HTTPException(status_code=400, detail="invalid file path")
    if not path.exists():
        raise HTTPException(status_code=404, detail="file not found")
    return FileResponse(path)


async def render_assignment(assignment_id: str, *, deps: AssignmentIoHandlerDeps):
    script = deps.app_root / "scripts" / "render_assignment_pdf.py"
    out = deps.run_script(["python3", str(script), "--assignment-id", assignment_id])
    return {"ok": True, "output": out}


async def assignment_questions_ocr(
    *,
    assignment_id: str,
    files,
    kp_id: Optional[str],
    difficulty: Optional[str],
    tags: Optional[str],
    ocr_mode: Optional[str],
    language: Optional[str],
    deps: AssignmentIoHandlerDeps,
):
    return await _maybe_await(
        deps.assignment_questions_ocr(
            assignment_id=assignment_id,
            files=files,
            kp_id=kp_id,
            difficulty=difficulty,
            tags=tags,
            ocr_mode=ocr_mode,
            language=language,
        )
    )


async def generate_assignment(
    *,
    assignment_id: str,
    kp: str,
    question_ids: Optional[str],
    per_kp: int,
    core_examples: Optional[str],
    generate: bool,
    mode: Optional[str],
    date: Optional[str],
    due_at: Optional[str],
    class_name: Optional[str],
    student_ids: Optional[str],
    source: Optional[str],
    requirements_json: Optional[str],
    deps: AssignmentIoHandlerDeps,
):
    try:
        return await _maybe_await(
            deps.generate_assignment(
                assignment_id=assignment_id,
                kp=kp,
                question_ids=question_ids,
                per_kp=per_kp,
                core_examples=core_examples,
                generate=generate,
                mode=mode,
                date=date,
                due_at=due_at,
                class_name=class_name,
                student_ids=student_ids,
                source=source,
                requirements_json=requirements_json,
            )
        )
    except AssignmentGenerateError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
