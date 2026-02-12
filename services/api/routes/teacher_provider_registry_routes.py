from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter

from ..api_models import (
    TeacherProviderRegistryCreateRequest,
    TeacherProviderRegistryDeleteRequest,
    TeacherProviderRegistryProbeRequest,
    TeacherProviderRegistryUpdateRequest,
)
from .teacher_route_helpers import ensure_ok_result, scoped_payload_teacher_id, scoped_teacher_id


def register_provider_registry_routes(router: APIRouter, core: Any) -> None:
    @router.get("/teacher/provider-registry")
    def teacher_provider_registry_api(teacher_id: Optional[str] = None):
        teacher_id_scoped = scoped_teacher_id(teacher_id)
        result = core.teacher_provider_registry_get({"teacher_id": teacher_id_scoped})
        ensure_ok_result(result)
        return result

    @router.post("/teacher/provider-registry/providers")
    def teacher_provider_registry_create_api(req: TeacherProviderRegistryCreateRequest):
        payload = scoped_payload_teacher_id(core.model_dump_compat(req, exclude_none=True))
        result = core.teacher_provider_registry_create(payload)
        ensure_ok_result(result)
        return result

    @router.patch("/teacher/provider-registry/providers/{provider_id}")
    def teacher_provider_registry_update_api(
        provider_id: str, req: TeacherProviderRegistryUpdateRequest
    ):
        payload = scoped_payload_teacher_id(core.model_dump_compat(req, exclude_none=True))
        payload["provider_id"] = provider_id
        result = core.teacher_provider_registry_update(payload)
        ensure_ok_result(result, not_found_errors={"provider_not_found"})
        return result

    @router.delete("/teacher/provider-registry/providers/{provider_id}")
    def teacher_provider_registry_delete_api(
        provider_id: str, req: TeacherProviderRegistryDeleteRequest
    ):
        payload = scoped_payload_teacher_id(core.model_dump_compat(req, exclude_none=True))
        payload["provider_id"] = provider_id
        result = core.teacher_provider_registry_delete(payload)
        ensure_ok_result(result, not_found_errors={"provider_not_found"})
        return result

    @router.post("/teacher/provider-registry/providers/{provider_id}/probe-models")
    def teacher_provider_registry_probe_models_api(
        provider_id: str, req: TeacherProviderRegistryProbeRequest
    ):
        payload = scoped_payload_teacher_id(core.model_dump_compat(req, exclude_none=True))
        payload["provider_id"] = provider_id
        result = core.teacher_provider_registry_probe_models(payload)
        ensure_ok_result(result, not_found_errors={"provider_not_found"})
        return result
