from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import JSONResponse


def register_student_profile_routes(router: APIRouter, core: Any) -> None:
    @router.get("/student/profile/{student_id}")
    def get_profile(student_id: str) -> Any:
        result = core._get_profile_api_impl(student_id, deps=core._student_profile_api_deps())
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
