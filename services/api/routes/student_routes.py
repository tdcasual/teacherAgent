from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from ..api_models import StudentImportRequest, StudentVerifyRequest


def build_router(core) -> APIRouter:
    router = APIRouter()

    @router.get("/student/history/sessions")
    async def student_history_sessions(student_id: str, limit: int = 20, cursor: int = 0):
        try:
            return core._student_history_sessions_api_impl(
                student_id,
                limit=limit,
                cursor=cursor,
                deps=core._session_history_api_deps(),
            )
        except core.SessionHistoryApiError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)

    @router.get("/student/session/view-state")
    async def student_session_view_state(student_id: str):
        try:
            return core._student_session_view_state_api_impl(student_id, deps=core._session_history_api_deps())
        except core.SessionHistoryApiError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)

    @router.put("/student/session/view-state")
    async def update_student_session_view_state(req: Dict[str, Any]):
        try:
            return core._update_student_session_view_state_api_impl(req, deps=core._session_history_api_deps())
        except core.SessionHistoryApiError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)

    @router.get("/student/history/session")
    async def student_history_session(
        student_id: str,
        session_id: str,
        cursor: int = -1,
        limit: int = 50,
        direction: str = "backward",
    ):
        try:
            return core._student_history_session_api_impl(
                student_id,
                session_id,
                cursor=cursor,
                limit=limit,
                direction=direction,
                deps=core._session_history_api_deps(),
            )
        except core.SessionHistoryApiError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)

    @router.get("/student/profile/{student_id}")
    async def get_profile(student_id: str):
        result = core._get_profile_api_impl(student_id, deps=core._student_profile_api_deps())
        if result.get("error") in {"profile not found", "profile_not_found"}:
            raise HTTPException(status_code=404, detail="profile not found")
        if result.get("error"):
            raise HTTPException(status_code=400, detail=result)
        return result

    @router.post("/student/profile/update")
    async def update_profile(
        student_id: str = Form(...),
        weak_kp: Optional[str] = Form(""),
        strong_kp: Optional[str] = Form(""),
        medium_kp: Optional[str] = Form(""),
        next_focus: Optional[str] = Form(""),
        interaction_note: Optional[str] = Form(""),
    ):
        payload = core._update_profile_api_impl(
            student_id=student_id,
            weak_kp=weak_kp,
            strong_kp=strong_kp,
            medium_kp=medium_kp,
            next_focus=next_focus,
            interaction_note=interaction_note,
            deps=core._student_ops_api_deps(),
        )
        return JSONResponse(payload)

    @router.post("/student/import")
    async def import_students(req: StudentImportRequest):
        result = core.student_import(req.dict())
        if result.get("error"):
            raise HTTPException(status_code=400, detail=result["error"])
        return result

    @router.post("/student/verify")
    async def verify_student(req: StudentVerifyRequest):
        return core._verify_student_api_impl(req.name, req.class_name, deps=core._student_ops_api_deps())

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

    return router
