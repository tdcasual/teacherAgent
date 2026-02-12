from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter

from ..api_models import (
    RoutingProposalCreateRequest,
    RoutingProposalReviewRequest,
    RoutingRollbackRequest,
    RoutingSimulateRequest,
)
from .teacher_route_helpers import ensure_ok_result, scoped_payload_teacher_id, scoped_teacher_id


def register_llm_routing_routes(router: APIRouter, core: Any) -> None:
    @router.get("/teacher/llm-routing")
    def teacher_llm_routing(
        teacher_id: Optional[str] = None,
        history_limit: int = 20,
        proposal_limit: int = 20,
        proposal_status: Optional[str] = None,
    ) -> Any:
        teacher_id_scoped = scoped_teacher_id(teacher_id)
        result = core._get_routing_api_impl(
            {
                "teacher_id": teacher_id_scoped,
                "history_limit": history_limit,
                "proposal_limit": proposal_limit,
                "proposal_status": proposal_status,
            },
            deps=core._teacher_routing_api_deps(),
        )
        ensure_ok_result(result)
        return result

    @router.post("/teacher/llm-routing/simulate")
    def teacher_llm_routing_simulate_api(req: RoutingSimulateRequest) -> Any:
        payload = scoped_payload_teacher_id(core.model_dump_compat(req, exclude_none=True))
        result = core.teacher_llm_routing_simulate(payload)
        ensure_ok_result(result)
        return result

    @router.post("/teacher/llm-routing/proposals")
    def teacher_llm_routing_proposals_api(req: RoutingProposalCreateRequest) -> Any:
        payload = scoped_payload_teacher_id(core.model_dump_compat(req, exclude_none=True))
        result = core.teacher_llm_routing_propose(payload)
        ensure_ok_result(result)
        return result

    @router.get("/teacher/llm-routing/proposals/{proposal_id}")
    def teacher_llm_routing_proposal_api(proposal_id: str, teacher_id: Optional[str] = None) -> Any:
        teacher_id_scoped = scoped_teacher_id(teacher_id)
        result = core.teacher_llm_routing_proposal_get(
            {"proposal_id": proposal_id, "teacher_id": teacher_id_scoped}
        )
        ensure_ok_result(result, not_found_errors={"proposal_not_found"})
        return result

    @router.post("/teacher/llm-routing/proposals/{proposal_id}/review")
    def teacher_llm_routing_proposal_review_api(
        proposal_id: str, req: RoutingProposalReviewRequest
    ) -> Any:
        payload = scoped_payload_teacher_id(core.model_dump_compat(req, exclude_none=True))
        payload["proposal_id"] = proposal_id
        result = core.teacher_llm_routing_apply(payload)
        ensure_ok_result(result, not_found_errors={"proposal_not_found"})
        return result

    @router.post("/teacher/llm-routing/rollback")
    def teacher_llm_routing_rollback_api(req: RoutingRollbackRequest) -> Any:
        payload = scoped_payload_teacher_id(core.model_dump_compat(req, exclude_none=True))
        result = core.teacher_llm_routing_rollback(payload)
        ensure_ok_result(result, not_found_errors={"history_not_found", "target_version_not_found"})
        return result
