from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from ..api_models import StudentImportRequest, StudentVerifyRequest
from ..assignment_process_archive_service import ProcessArchiveError
from ..auth_service import (
    AuthError,
    get_current_principal,
    require_principal,
    resolve_student_scope,
)
from ..student_submit_service import StudentSubmitError


def _scoped_student_id(student_id: str | None) -> str:
    try:
        scoped = resolve_student_scope(student_id, required_for_admin=False)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    sid = str(scoped or "").strip()
    if not sid:
        raise HTTPException(status_code=400, detail="student_id is required")
    return sid


def _require_teacher_or_admin() -> None:
    try:
        require_principal(roles=("teacher", "admin"))
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


def register_student_ops_routes(router: APIRouter, core: Any) -> None:
    @router.post("/student/import")
    def import_students(req: StudentImportRequest) -> Any:
        _require_teacher_or_admin()
        result = core.student_import(req.model_dump())
        if result.get("error"):
            raise HTTPException(status_code=400, detail=result["error"])
        return result

    @router.post("/student/verify")
    def verify_student(req: StudentVerifyRequest) -> Any:
        _require_teacher_or_admin()
        return core.verify_student(req.name, req.class_name)

    @router.post("/student/submit")
    async def submit(
        student_id: str = Form(...),
        files: list[UploadFile] = File(...),
        assignment_id: Optional[str] = Form(None),
        auto_assignment: bool = Form(False),
    ) -> Any:
        sid = _scoped_student_id(student_id)
        try:
            return await core.student_submit(
                student_id=sid,
                files=files,
                assignment_id=assignment_id,
                auto_assignment=auto_assignment,
            )
        except StudentSubmitError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    @router.post("/student/assignment/{assignment_id}/process-archive")
    def student_process_archive(assignment_id: str, student_id: Optional[str] = None) -> Any:
        principal = get_current_principal()
        if principal is not None and principal.role == "student":
            sid = _scoped_student_id(student_id or principal.actor_id)
        else:
            if principal is not None:
                try:
                    require_principal(roles=("teacher", "admin"))
                except AuthError as exc:
                    raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
            sid = str(student_id or "").strip()
            if not sid:
                raise HTTPException(status_code=400, detail="student_id is required")
        try:
            result = dict(
                core.request_process_archive(
                    assignment_id=assignment_id,
                    student_id=sid,
                    reason="manual",
                )
            )
        except ProcessArchiveError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
        status = int(result.pop("http_status", 200) or 200)
        if status == 202:
            return JSONResponse(status_code=202, content=result)
        return result
