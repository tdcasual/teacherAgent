from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter

from ..api_models import TeacherModelConfigUpdateRequest
from .teacher_route_helpers import ensure_ok_result, scoped_payload_teacher_id, scoped_teacher_id


def register_model_config_routes(router: APIRouter, core: Any) -> None:
    @router.get("/teacher/model-config")
    def teacher_model_config_get_api(teacher_id: Optional[str] = None) -> Any:
        teacher_id_scoped = scoped_teacher_id(teacher_id)
        result = core.teacher_model_config_get({"teacher_id": teacher_id_scoped})
        ensure_ok_result(result)
        return result

    @router.put("/teacher/model-config")
    def teacher_model_config_update_api(req: TeacherModelConfigUpdateRequest) -> Any:
        payload = scoped_payload_teacher_id(req.model_dump(exclude_none=True))
        result = core.teacher_model_config_update(payload)
        ensure_ok_result(result)
        return result
