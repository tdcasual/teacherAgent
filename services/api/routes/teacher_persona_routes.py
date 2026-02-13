from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter

from .teacher_route_helpers import ensure_ok_result, scoped_payload_teacher_id, scoped_teacher_id


def register_teacher_persona_routes(router: APIRouter, core: Any) -> None:
    @router.get("/teacher/personas")
    def teacher_personas_get(teacher_id: Optional[str] = None) -> Any:
        teacher_id_scoped = scoped_teacher_id(teacher_id)
        result = core._teacher_personas_get_api_impl(
            teacher_id_scoped or "",
            deps=core._teacher_persona_api_deps(),
        )
        ensure_ok_result(result)
        return result

    @router.post("/teacher/personas")
    def teacher_persona_create(req: Dict[str, Any]) -> Any:
        payload = scoped_payload_teacher_id(req)
        teacher_id = str(payload.pop("teacher_id") or "")
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
        teacher_id = str(payload.pop("teacher_id") or "")
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
        teacher_id = str(payload.pop("teacher_id") or "")
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
        teacher_id = str(payload.pop("teacher_id") or "")
        result = core._teacher_persona_visibility_api_impl(
            teacher_id,
            persona_id,
            payload,
            deps=core._teacher_persona_api_deps(),
        )
        ensure_ok_result(result, not_found_errors={"persona_not_found"})
        return result

