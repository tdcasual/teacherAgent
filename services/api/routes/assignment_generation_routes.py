from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..auth_service import AuthError, require_principal


def _require_teacher_or_admin() -> None:
    try:
        require_principal(roles=("teacher", "admin"))
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


def register_assignment_generation_routes(
    router: APIRouter, *, app_deps: Any, assignment_app: Any
) -> None:
    @router.post("/assignment/generate")
    async def generate_assignment(
        assignment_id: str = Form(...),
        kp: str = Form(""),
        question_ids: Optional[str] = Form(""),
        per_kp: int = Form(5),
        core_examples: Optional[str] = Form(""),
        generate: bool = Form(False),
        mode: Optional[str] = Form(""),
        date: Optional[str] = Form(""),
        due_at: Optional[str] = Form(""),
        class_name: Optional[str] = Form(""),
        student_ids: Optional[str] = Form(""),
        source: Optional[str] = Form(""),
        requirements_json: Optional[str] = Form(""),
    ) -> Any:
        _require_teacher_or_admin()
        return await assignment_app.post_generate_assignment(
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
            deps=app_deps,
        )

    @router.post("/assignment/render")
    async def render_assignment(assignment_id: str = Form(...)) -> Any:
        _require_teacher_or_admin()
        return await assignment_app.post_render_assignment(assignment_id, deps=app_deps)

    @router.post("/assignment/questions/ocr")
    async def assignment_questions_ocr(
        assignment_id: str = Form(...),
        files: list[UploadFile] = File(...),
        kp_id: Optional[str] = Form("uncategorized"),
        difficulty: Optional[str] = Form("basic"),
        tags: Optional[str] = Form("ocr"),
        ocr_mode: Optional[str] = Form("FREE_OCR"),
        language: Optional[str] = Form("zh"),
    ) -> Any:
        _require_teacher_or_admin()
        return await assignment_app.post_assignment_questions_ocr(
            assignment_id=assignment_id,
            files=files,
            kp_id=kp_id,
            difficulty=difficulty,
            tags=tags,
            ocr_mode=ocr_mode,
            language=language,
            deps=app_deps,
        )
