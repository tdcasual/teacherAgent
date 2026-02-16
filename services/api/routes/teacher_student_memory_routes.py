from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter

from ..api_models import (
    StudentMemoryProposalCreateRequest,
    StudentMemoryProposalReviewRequest,
)
from ..student_memory_api_service import (
    StudentMemoryApiDeps,
    create_proposal_api,
    delete_proposal_api,
    insights_api,
    list_proposals_api,
    review_proposal_api,
)
from .teacher_route_helpers import ensure_ok_error_detail, scoped_teacher_id


def _student_memory_api_deps(core: Any) -> StudentMemoryApiDeps:
    return StudentMemoryApiDeps(
        resolve_teacher_id=core.resolve_teacher_id,
        teacher_workspace_dir=core.teacher_workspace_dir,
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
    )


def register_student_memory_routes(router: APIRouter, core: Any) -> None:
    @router.get("/teacher/student-memory/proposals")
    def teacher_student_memory_proposals(
        teacher_id: Optional[str] = None,
        student_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
    ) -> Any:
        teacher_id_scoped = scoped_teacher_id(teacher_id)
        result = list_proposals_api(
            teacher_id_scoped,
            student_id=student_id,
            status=status,
            limit=limit,
            deps=_student_memory_api_deps(core),
        )
        ensure_ok_error_detail(result)
        return result

    @router.post("/teacher/student-memory/proposals")
    def teacher_student_memory_proposal_create(req: StudentMemoryProposalCreateRequest) -> Any:
        teacher_id_scoped = scoped_teacher_id(req.teacher_id)
        result = create_proposal_api(
            teacher_id=teacher_id_scoped,
            student_id=req.student_id,
            memory_type=req.memory_type,
            content=req.content,
            evidence_refs=req.evidence_refs,
            source=req.source,
            deps=_student_memory_api_deps(core),
        )
        ensure_ok_error_detail(result)
        return result

    @router.post("/teacher/student-memory/proposals/{proposal_id}/review")
    def teacher_student_memory_proposal_review(
        proposal_id: str,
        req: StudentMemoryProposalReviewRequest,
    ) -> Any:
        teacher_id_scoped = scoped_teacher_id(req.teacher_id)
        result = review_proposal_api(
            proposal_id,
            teacher_id=teacher_id_scoped,
            approve=bool(req.approve),
            deps=_student_memory_api_deps(core),
        )
        if result.get("error"):
            ensure_ok_error_detail(result, not_found_errors={"proposal not found"})
        return result

    @router.delete("/teacher/student-memory/proposals/{proposal_id}")
    def teacher_student_memory_proposal_delete(
        proposal_id: str,
        teacher_id: Optional[str] = None,
    ) -> Any:
        teacher_id_scoped = scoped_teacher_id(teacher_id)
        result = delete_proposal_api(
            proposal_id,
            teacher_id=teacher_id_scoped,
            deps=_student_memory_api_deps(core),
        )
        if result.get("error"):
            ensure_ok_error_detail(result, not_found_errors={"proposal not found"})
        return result

    @router.get("/teacher/student-memory/insights")
    def teacher_student_memory_insights(
        teacher_id: Optional[str] = None,
        student_id: Optional[str] = None,
        days: int = 14,
    ) -> Any:
        teacher_id_scoped = scoped_teacher_id(teacher_id)
        result = insights_api(
            teacher_id_scoped,
            student_id=student_id,
            days=days,
            deps=_student_memory_api_deps(core),
        )
        ensure_ok_error_detail(result)
        return result
