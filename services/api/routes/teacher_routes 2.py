from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException

from ..api_models import (
    RoutingProposalCreateRequest,
    RoutingProposalReviewRequest,
    RoutingRollbackRequest,
    RoutingSimulateRequest,
    TeacherMemoryProposalReviewRequest,
    TeacherProviderRegistryCreateRequest,
    TeacherProviderRegistryDeleteRequest,
    TeacherProviderRegistryProbeRequest,
    TeacherProviderRegistryUpdateRequest,
)
from ..auth_service import AuthError, resolve_teacher_scope


def build_router(core) -> APIRouter:
    router = APIRouter()

    @router.get("/teacher/history/sessions")
    def teacher_history_sessions(teacher_id: Optional[str] = None, limit: int = 20, cursor: int = 0):
        try:
            teacher_id = resolve_teacher_scope(teacher_id)
        except AuthError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)
        return core._teacher_history_sessions_api_impl(teacher_id, limit=limit, cursor=cursor, deps=core._session_history_api_deps())

    @router.get("/teacher/session/view-state")
    def teacher_session_view_state(teacher_id: Optional[str] = None):
        try:
            teacher_id = resolve_teacher_scope(teacher_id)
        except AuthError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)
        return core._teacher_session_view_state_api_impl(teacher_id, deps=core._session_history_api_deps())

    @router.put("/teacher/session/view-state")
    def update_teacher_session_view_state(req: dict):
        try:
            req = dict(req or {})
            req["teacher_id"] = resolve_teacher_scope(req.get("teacher_id"))
        except AuthError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)
        return core._update_teacher_session_view_state_api_impl(req, deps=core._session_history_api_deps())

    @router.get("/teacher/history/session")
    def teacher_history_session(
        session_id: str,
        teacher_id: Optional[str] = None,
        cursor: int = -1,
        limit: int = 50,
        direction: str = "backward",
    ):
        try:
            teacher_id = resolve_teacher_scope(teacher_id)
        except AuthError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)
        try:
            return core._teacher_history_session_api_impl(
                session_id,
                teacher_id,
                cursor=cursor,
                limit=limit,
                direction=direction,
                deps=core._session_history_api_deps(),
            )
        except core.SessionHistoryApiError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)

    @router.get("/teacher/memory/proposals")
    def teacher_memory_proposals(teacher_id: Optional[str] = None, status: Optional[str] = None, limit: int = 20):
        try:
            teacher_id = resolve_teacher_scope(teacher_id)
        except AuthError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)
        result = core._list_teacher_memory_proposals_api_impl(
            teacher_id,
            status=status,
            limit=limit,
            deps=core._teacher_memory_api_deps(),
        )
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result.get("error") or "invalid_request")
        return result

    @router.get("/teacher/memory/insights")
    def teacher_memory_insights_api(teacher_id: Optional[str] = None, days: int = 14):
        try:
            teacher_id_scoped = resolve_teacher_scope(teacher_id)
        except AuthError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)
        teacher_id_final = core.resolve_teacher_id(teacher_id_scoped)
        return core.teacher_memory_insights(teacher_id_final, days=days)

    @router.post("/teacher/memory/proposals/{proposal_id}/review")
    def teacher_memory_proposal_review(proposal_id: str, req: TeacherMemoryProposalReviewRequest):
        try:
            teacher_id = resolve_teacher_scope(req.teacher_id)
        except AuthError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)
        result = core._review_teacher_memory_proposal_api_impl(
            proposal_id,
            teacher_id=teacher_id,
            approve=bool(req.approve),
            deps=core._teacher_memory_api_deps(),
        )
        if result.get("error"):
            code = 404 if str(result.get("error")) == "proposal not found" else 400
            raise HTTPException(status_code=code, detail=result.get("error"))
        return result

    @router.get("/teacher/llm-routing")
    def teacher_llm_routing(
        teacher_id: Optional[str] = None,
        history_limit: int = 20,
        proposal_limit: int = 20,
        proposal_status: Optional[str] = None,
    ):
        try:
            teacher_id = resolve_teacher_scope(teacher_id)
        except AuthError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)
        result = core._get_routing_api_impl(
            {
                "teacher_id": teacher_id,
                "history_limit": history_limit,
                "proposal_limit": proposal_limit,
                "proposal_status": proposal_status,
            },
            deps=core._teacher_routing_api_deps(),
        )
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result)
        return result

    @router.post("/teacher/llm-routing/simulate")
    def teacher_llm_routing_simulate_api(req: RoutingSimulateRequest):
        payload = core.model_dump_compat(req, exclude_none=True)
        try:
            payload["teacher_id"] = resolve_teacher_scope(payload.get("teacher_id"))
        except AuthError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)
        result = core.teacher_llm_routing_simulate(payload)
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result)
        return result

    @router.post("/teacher/llm-routing/proposals")
    def teacher_llm_routing_proposals_api(req: RoutingProposalCreateRequest):
        payload = core.model_dump_compat(req, exclude_none=True)
        try:
            payload["teacher_id"] = resolve_teacher_scope(payload.get("teacher_id"))
        except AuthError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)
        result = core.teacher_llm_routing_propose(payload)
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result)
        return result

    @router.get("/teacher/llm-routing/proposals/{proposal_id}")
    def teacher_llm_routing_proposal_api(proposal_id: str, teacher_id: Optional[str] = None):
        try:
            teacher_id = resolve_teacher_scope(teacher_id)
        except AuthError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)
        result = core.teacher_llm_routing_proposal_get({"proposal_id": proposal_id, "teacher_id": teacher_id})
        if not result.get("ok"):
            status_code = 404 if str(result.get("error") or "").strip() == "proposal_not_found" else 400
            raise HTTPException(status_code=status_code, detail=result)
        return result

    @router.post("/teacher/llm-routing/proposals/{proposal_id}/review")
    def teacher_llm_routing_proposal_review_api(proposal_id: str, req: RoutingProposalReviewRequest):
        payload = core.model_dump_compat(req, exclude_none=True)
        try:
            payload["teacher_id"] = resolve_teacher_scope(payload.get("teacher_id"))
        except AuthError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)
        payload["proposal_id"] = proposal_id
        result = core.teacher_llm_routing_apply(payload)
        if not result.get("ok"):
            status_code = 404 if str(result.get("error") or "").strip() == "proposal_not_found" else 400
            raise HTTPException(status_code=status_code, detail=result)
        return result

    @router.post("/teacher/llm-routing/rollback")
    def teacher_llm_routing_rollback_api(req: RoutingRollbackRequest):
        payload = core.model_dump_compat(req, exclude_none=True)
        try:
            payload["teacher_id"] = resolve_teacher_scope(payload.get("teacher_id"))
        except AuthError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)
        result = core.teacher_llm_routing_rollback(payload)
        if not result.get("ok"):
            status_code = 404 if str(result.get("error") or "").strip() in {"history_not_found", "target_version_not_found"} else 400
            raise HTTPException(status_code=status_code, detail=result)
        return result

    @router.get("/teacher/provider-registry")
    def teacher_provider_registry_api(teacher_id: Optional[str] = None):
        try:
            teacher_id = resolve_teacher_scope(teacher_id)
        except AuthError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)
        result = core.teacher_provider_registry_get({"teacher_id": teacher_id})
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result)
        return result

    @router.post("/teacher/provider-registry/providers")
    def teacher_provider_registry_create_api(req: TeacherProviderRegistryCreateRequest):
        payload = core.model_dump_compat(req, exclude_none=True)
        try:
            payload["teacher_id"] = resolve_teacher_scope(payload.get("teacher_id"))
        except AuthError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)
        result = core.teacher_provider_registry_create(payload)
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result)
        return result

    @router.patch("/teacher/provider-registry/providers/{provider_id}")
    def teacher_provider_registry_update_api(provider_id: str, req: TeacherProviderRegistryUpdateRequest):
        payload = core.model_dump_compat(req, exclude_none=True)
        try:
            payload["teacher_id"] = resolve_teacher_scope(payload.get("teacher_id"))
        except AuthError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)
        payload["provider_id"] = provider_id
        result = core.teacher_provider_registry_update(payload)
        if not result.get("ok"):
            status_code = 404 if str(result.get("error") or "").strip() == "provider_not_found" else 400
            raise HTTPException(status_code=status_code, detail=result)
        return result

    @router.delete("/teacher/provider-registry/providers/{provider_id}")
    def teacher_provider_registry_delete_api(provider_id: str, req: TeacherProviderRegistryDeleteRequest):
        payload = core.model_dump_compat(req, exclude_none=True)
        try:
            payload["teacher_id"] = resolve_teacher_scope(payload.get("teacher_id"))
        except AuthError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)
        payload["provider_id"] = provider_id
        result = core.teacher_provider_registry_delete(payload)
        if not result.get("ok"):
            status_code = 404 if str(result.get("error") or "").strip() == "provider_not_found" else 400
            raise HTTPException(status_code=status_code, detail=result)
        return result

    @router.post("/teacher/provider-registry/providers/{provider_id}/probe-models")
    def teacher_provider_registry_probe_models_api(provider_id: str, req: TeacherProviderRegistryProbeRequest):
        payload = core.model_dump_compat(req, exclude_none=True)
        try:
            payload["teacher_id"] = resolve_teacher_scope(payload.get("teacher_id"))
        except AuthError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)
        payload["provider_id"] = provider_id
        result = core.teacher_provider_registry_probe_models(payload)
        if not result.get("ok"):
            status_code = 404 if str(result.get("error") or "").strip() == "provider_not_found" else 400
            raise HTTPException(status_code=status_code, detail=result)
        return result

    return router
