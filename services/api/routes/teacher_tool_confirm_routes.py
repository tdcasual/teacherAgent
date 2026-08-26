from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from ..api_models import TeacherToolConfirmRequest
from ..auth_service import AuthError
from ..tool_confirm_service import confirm_teacher_tool, resolve_confirm_actor_id


def register_tool_confirm_routes(router: APIRouter, core: Any) -> None:
    @router.post("/teacher/tools/confirm")
    def teacher_tools_confirm(req: TeacherToolConfirmRequest) -> Any:
        try:
            actor_id = resolve_confirm_actor_id()
        except AuthError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
        result = confirm_teacher_tool(
            confirm_id=str(req.confirm_id or "").strip(),
            confirmed=bool(req.confirmed),
            actor_id=actor_id,
            core=core,
        )
        error = str(result.get("error") or "")
        if error == "confirm_not_found":
            raise HTTPException(status_code=404, detail="confirm_not_found")
        if error == "forbidden":
            raise HTTPException(status_code=403, detail="forbidden")
        if error:
            raise HTTPException(status_code=400, detail=error)
        return result
