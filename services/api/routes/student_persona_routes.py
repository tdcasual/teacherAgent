from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from ..auth_service import AuthError, resolve_student_scope


def _scoped_student_id(student_id: Optional[str]) -> str:
    try:
        scoped = resolve_student_scope(student_id, required_for_admin=False)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    sid = str(scoped or "").strip()
    if not sid:
        raise HTTPException(status_code=400, detail={"error": "missing_student_id"})
    return sid


def register_student_persona_routes(router: APIRouter, core: Any) -> None:
    @router.get("/student/personas")
    def get_student_personas(student_id: str) -> Any:
        sid = _scoped_student_id(student_id)
        result = core._student_personas_get_api_impl(
            sid,
            deps=core._student_persona_api_deps(),
        )
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result)
        return result

    @router.post("/student/personas/custom")
    def create_student_persona(req: Dict[str, Any]) -> Any:
        student_id = _scoped_student_id(str(req.get("student_id") or ""))
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

    @router.patch("/student/personas/custom/{persona_id}")
    def update_student_persona(persona_id: str, req: Dict[str, Any]) -> Any:
        student_id = _scoped_student_id(str(req.get("student_id") or ""))
        payload = dict(req)
        payload.pop("student_id", None)
        result = core._student_persona_custom_update_api_impl(
            student_id,
            persona_id,
            payload,
            deps=core._student_persona_api_deps(),
        )
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result)
        return result

    @router.post("/student/personas/activate")
    def activate_student_persona(req: Dict[str, Any]) -> Any:
        student_id = _scoped_student_id(str(req.get("student_id") or ""))
        persona_id = str(req.get("persona_id") or "").strip()
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
        sid = _scoped_student_id(student_id)
        result = core._student_persona_custom_delete_api_impl(
            sid,
            persona_id,
            deps=core._student_persona_api_deps(),
        )
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result)
        return result

    @router.post("/student/personas/avatar/upload")
    async def upload_student_persona_avatar(
        student_id: str = Form(...),
        persona_id: str = Form(...),
        file: UploadFile = File(...),
    ) -> Any:
        sid = _scoped_student_id(student_id)
        content = await file.read()
        result = core._student_persona_avatar_upload_api_impl(
            sid,
            persona_id,
            filename=str(getattr(file, "filename", "") or ""),
            content=content,
            deps=core._student_persona_api_deps(),
        )
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result)
        return result

    @router.get("/student/personas/avatar/{student_id}/{persona_id}/{file_name}")
    def get_student_persona_avatar(student_id: str, persona_id: str, file_name: str) -> Any:
        sid = _scoped_student_id(student_id)
        path = core._resolve_student_persona_avatar_path_impl(
            sid,
            persona_id,
            file_name,
            deps=core._student_persona_api_deps(),
        )
        if path is None:
            raise HTTPException(status_code=404, detail="avatar_not_found")
        return FileResponse(path, filename=path.name)
