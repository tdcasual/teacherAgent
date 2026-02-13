from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from .teacher_route_helpers import ensure_ok_result, scoped_payload_teacher_id, scoped_teacher_id

_AVATAR_MAX_BYTES = 2 * 1024 * 1024
_AVATAR_READ_CHUNK = 64 * 1024


def _effective_teacher_id(core: Any, teacher_id: Optional[str]) -> str:
    teacher_id_scoped = scoped_teacher_id(teacher_id)
    return core.resolve_teacher_id(str(teacher_id_scoped or "").strip())


async def _read_avatar_content_limited(file: UploadFile) -> Optional[bytes]:
    total = 0
    chunks: list[bytes] = []
    while True:
        chunk = await file.read(_AVATAR_READ_CHUNK)
        if not chunk:
            break
        total += len(chunk)
        if total > _AVATAR_MAX_BYTES:
            return None
        chunks.append(chunk)
    return b"".join(chunks)


def register_teacher_persona_routes(router: APIRouter, core: Any) -> None:
    @router.get("/teacher/personas")
    def teacher_personas_get(teacher_id: Optional[str] = None) -> Any:
        teacher_id_scoped = _effective_teacher_id(core, teacher_id)
        result = core._teacher_personas_get_api_impl(
            teacher_id_scoped or "",
            deps=core._teacher_persona_api_deps(),
        )
        ensure_ok_result(result)
        return result

    @router.post("/teacher/personas")
    def teacher_persona_create(req: Dict[str, Any]) -> Any:
        payload = scoped_payload_teacher_id(req)
        teacher_id = _effective_teacher_id(core, payload.pop("teacher_id", None))
        result = core._teacher_persona_create_api_impl(
            teacher_id,
            payload,
            deps=core._teacher_persona_api_deps(),
        )
        ensure_ok_result(result)
        return result

    @router.patch("/teacher/personas/{persona_id}")
    def teacher_persona_update(persona_id: str, req: Dict[str, Any]) -> Any:
        payload = scoped_payload_teacher_id(req)
        teacher_id = _effective_teacher_id(core, payload.pop("teacher_id", None))
        result = core._teacher_persona_update_api_impl(
            teacher_id,
            persona_id,
            payload,
            deps=core._teacher_persona_api_deps(),
        )
        ensure_ok_result(result, not_found_errors={"persona_not_found"})
        return result

    @router.post("/teacher/personas/{persona_id}/assign")
    def teacher_persona_assign(persona_id: str, req: Dict[str, Any]) -> Any:
        payload = scoped_payload_teacher_id(req)
        teacher_id = _effective_teacher_id(core, payload.pop("teacher_id", None))
        result = core._teacher_persona_assign_api_impl(
            teacher_id,
            persona_id,
            payload,
            deps=core._teacher_persona_api_deps(),
        )
        ensure_ok_result(result, not_found_errors={"persona_not_found"})
        return result

    @router.post("/teacher/personas/{persona_id}/visibility")
    def teacher_persona_visibility(persona_id: str, req: Dict[str, Any]) -> Any:
        payload = scoped_payload_teacher_id(req)
        teacher_id = _effective_teacher_id(core, payload.pop("teacher_id", None))
        result = core._teacher_persona_visibility_api_impl(
            teacher_id,
            persona_id,
            payload,
            deps=core._teacher_persona_api_deps(),
        )
        ensure_ok_result(result, not_found_errors={"persona_not_found"})
        return result

    @router.post("/teacher/personas/{persona_id}/avatar/upload")
    async def teacher_persona_avatar_upload(
        persona_id: str,
        teacher_id: Optional[str] = Form(None),
        file: UploadFile = File(...),
    ) -> Any:
        teacher_id_scoped = _effective_teacher_id(core, teacher_id)
        try:
            content = await _read_avatar_content_limited(file)
            if content is None:
                ensure_ok_result({"ok": False, "error": "avatar_too_large"})
            result = core._teacher_persona_avatar_upload_api_impl(
                teacher_id_scoped or "",
                persona_id,
                filename=str(getattr(file, "filename", "") or ""),
                content=content,
                deps=core._teacher_persona_api_deps(),
            )
            ensure_ok_result(result, not_found_errors={"persona_not_found"})
            return result
        finally:
            await file.close()

    @router.get("/teacher/personas/avatar/{teacher_id}/{persona_id}/{file_name}")
    def teacher_persona_avatar_get(teacher_id: str, persona_id: str, file_name: str) -> Any:
        teacher_id_scoped = _effective_teacher_id(core, teacher_id)
        path = core._resolve_teacher_persona_avatar_path_impl(
            teacher_id_scoped,
            persona_id,
            file_name,
            deps=core._teacher_persona_api_deps(),
        )
        if path is None:
            raise HTTPException(status_code=404, detail="avatar_not_found")
        return FileResponse(path, filename=path.name)
