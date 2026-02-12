from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..api_models import StudentImportRequest, StudentVerifyRequest


def register_student_ops_routes(router: APIRouter, core: Any) -> None:
    @router.post("/student/import")
    def import_students(req: StudentImportRequest):
        result = core.student_import(req.dict())
        if result.get("error"):
            raise HTTPException(status_code=400, detail=result["error"])
        return result

    @router.post("/student/verify")
    def verify_student(req: StudentVerifyRequest):
        return core._verify_student_api_impl(
            req.name, req.class_name, deps=core._student_ops_api_deps()
        )

    @router.post("/student/submit")
    async def submit(
        student_id: str = Form(...),
        files: list[UploadFile] = File(...),
        assignment_id: Optional[str] = Form(None),
        auto_assignment: bool = Form(False),
    ):
        return await core._student_submit_impl(
            student_id=student_id,
            files=files,
            assignment_id=assignment_id,
            auto_assignment=auto_assignment,
            deps=core._student_submit_deps(),
        )
