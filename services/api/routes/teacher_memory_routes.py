from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter

from ..api_models import TeacherMemoryProposalReviewRequest
from .teacher_route_helpers import ensure_ok_error_detail, scoped_teacher_id


def register_memory_routes(router: APIRouter, core: Any) -> None:
    @router.get("/teacher/memory/proposals")
    def teacher_memory_proposals(
        teacher_id: Optional[str] = None, status: Optional[str] = None, limit: int = 20
    ) -> Any:
        teacher_id_scoped = scoped_teacher_id(teacher_id)
        result = core._list_teacher_memory_proposals_api_impl(
            teacher_id_scoped,
            status=status,
            limit=limit,
            deps=core._teacher_memory_api_deps(),
        )
        ensure_ok_error_detail(result)
        return result

    @router.get("/teacher/memory/insights")
    def teacher_memory_insights_api(teacher_id: Optional[str] = None, days: int = 14) -> Any:
        teacher_id_scoped = scoped_teacher_id(teacher_id)
        teacher_id_final = core.resolve_teacher_id(teacher_id_scoped)
        return core.teacher_memory_insights(teacher_id_final, days=days)

    @router.post("/teacher/memory/proposals/{proposal_id}/review")
    def teacher_memory_proposal_review(
        proposal_id: str, req: TeacherMemoryProposalReviewRequest
    ) -> Any:
        teacher_id_scoped = scoped_teacher_id(req.teacher_id)
        result = core._review_teacher_memory_proposal_api_impl(
            proposal_id,
            teacher_id=teacher_id_scoped,
            approve=bool(req.approve),
            deps=core._teacher_memory_api_deps(),
        )
        if result.get("error"):
            ensure_ok_error_detail(result, not_found_errors={"proposal not found"})
        return result

    @router.delete("/teacher/memory/proposals/{proposal_id}")
    def teacher_memory_proposal_delete(
        proposal_id: str, teacher_id: Optional[str] = None
    ) -> Any:
        teacher_id_scoped = scoped_teacher_id(teacher_id)
        result = core._delete_teacher_memory_proposal_api_impl(
            proposal_id,
            teacher_id=teacher_id_scoped,
            deps=core._teacher_memory_api_deps(),
        )
        if result.get("error"):
            ensure_ok_error_detail(result, not_found_errors={"proposal not found"})
        return result
