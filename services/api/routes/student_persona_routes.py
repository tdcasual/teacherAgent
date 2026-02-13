from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException


def register_student_persona_routes(router: APIRouter, core: Any) -> None:
    @router.get("/student/personas")
    def get_student_personas(student_id: str) -> Any:
        result = core._student_personas_get_api_impl(
            student_id,
            deps=core._student_persona_api_deps(),
        )
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result)
        return result

    @router.post("/student/personas/custom")
    def create_student_persona(req: Dict[str, Any]) -> Any:
        student_id = str(req.get("student_id") or "").strip()
        if not student_id:
            raise HTTPException(status_code=400, detail={"error": "missing_student_id"})
        payload = dict(req)
        payload.pop("student_id", None)
        result = core._student_persona_custom_create_api_impl(
            student_id,
            payload,
            deps=core._student_persona_api_deps(),
        )
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result)
        return result

    @router.post("/student/personas/activate")
    def activate_student_persona(req: Dict[str, Any]) -> Any:
        student_id = str(req.get("student_id") or "").strip()
        persona_id = str(req.get("persona_id") or "").strip()
        if not student_id:
            raise HTTPException(status_code=400, detail={"error": "missing_student_id"})
        result = core._student_persona_activate_api_impl(
            student_id,
            persona_id,
            deps=core._student_persona_api_deps(),
        )
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result)
        return result

    @router.delete("/student/personas/custom/{persona_id}")
    def delete_student_persona(persona_id: str, student_id: Optional[str] = None) -> Any:
        sid = str(student_id or "").strip()
        if not sid:
            raise HTTPException(status_code=400, detail={"error": "missing_student_id"})
        result = core._student_persona_custom_delete_api_impl(
            sid,
            persona_id,
            deps=core._student_persona_api_deps(),
        )
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result)
        return result

