from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import JSONResponse

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


def register_student_profile_routes(router: APIRouter, core: Any) -> None:
    @router.get("/student/profile/{student_id}")
    def get_profile(student_id: str) -> Any:
        sid = _scoped_student_id(student_id)
        result = core._get_profile_api_impl(sid, deps=core._student_profile_api_deps())
        if result.get("error") in {"profile not found", "profile_not_found"}:
            raise HTTPException(status_code=404, detail="profile not found")
        if result.get("error"):
            raise HTTPException(status_code=400, detail=result)
        return result

    @router.post("/student/profile/update")
    def update_profile(
        student_id: str = Form(...),
        weak_kp: Optional[str] = Form(""),
        strong_kp: Optional[str] = Form(""),
        medium_kp: Optional[str] = Form(""),
        next_focus: Optional[str] = Form(""),
        interaction_note: Optional[str] = Form(""),
    ) -> JSONResponse:
        sid = _scoped_student_id(student_id)
        payload = core._update_profile_api_impl(
            student_id=sid,
            weak_kp=weak_kp,
            strong_kp=strong_kp,
            medium_kp=medium_kp,
            next_focus=next_focus,
            interaction_note=interaction_note,
            deps=core._student_ops_api_deps(),
        )
        return JSONResponse(payload)
