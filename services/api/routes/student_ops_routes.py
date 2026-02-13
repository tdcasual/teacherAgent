from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..api_models import StudentImportRequest, StudentVerifyRequest
from ..auth_service import AuthError, resolve_student_scope


def _scoped_student_id(student_id: str | None) -> str:
    try:
        scoped = resolve_student_scope(student_id, required_for_admin=False)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    sid = str(scoped or "").strip()
    if not sid:
        raise HTTPException(status_code=400, detail="student_id is required")
    return sid


def register_student_ops_routes(router: APIRouter, core: Any) -> None:
    @router.post("/student/import")
    def import_students(req: StudentImportRequest) -> Any:
        result = core.student_import(req.dict())
        if result.get("error"):
            raise HTTPException(status_code=400, detail=result["error"])
        return result

    @router.post("/student/verify")
    def verify_student(req: StudentVerifyRequest) -> Any:
        return core._verify_student_api_impl(
            req.name, req.class_name, deps=core._student_ops_api_deps()
        )

    @router.post("/student/submit")
    async def submit(
        student_id: str = Form(...),
        files: list[UploadFile] = File(...),
        assignment_id: Optional[str] = Form(None),
        auto_assignment: bool = Form(False),
    ) -> Any:
        sid = _scoped_student_id(student_id)
        return await core._student_submit_impl(
            student_id=sid,
            files=files,
            assignment_id=assignment_id,
            auto_assignment=auto_assignment,
            deps=core._student_submit_deps(),
        )
