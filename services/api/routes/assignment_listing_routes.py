from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException

from ..api_models import AssignmentRequirementsRequest
from ..auth_service import AuthError, require_principal


def _require_teacher_or_admin() -> None:
    try:
        require_principal(roles=("teacher", "admin"))
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


def register_assignment_listing_routes(
    router: APIRouter, *, app_deps: Any, assignment_app: Any
) -> None:
    @router.get("/assignments")
    async def assignments(limit: int = 50, cursor: int = 0) -> Any:
        _require_teacher_or_admin()
        return await assignment_app.list_assignments(limit=limit, cursor=cursor, deps=app_deps)

    @router.get("/teacher/assignment/progress")
    async def teacher_assignment_progress(assignment_id: str, include_students: bool = True) -> Any:
        _require_teacher_or_admin()
        return await assignment_app.get_teacher_assignment_progress(
            assignment_id,
            include_students=include_students,
            deps=app_deps,
        )

    @router.get("/teacher/assignments/progress")
    async def teacher_assignments_progress(date: Optional[str] = None) -> Any:
        _require_teacher_or_admin()
        return await assignment_app.get_teacher_assignments_progress(
            date=date,
            deps=app_deps,
        )

    @router.post("/assignment/requirements")
    async def assignment_requirements(req: AssignmentRequirementsRequest) -> Any:
        _require_teacher_or_admin()
        return await assignment_app.post_assignment_requirements(req, deps=app_deps)

    @router.get("/assignment/{assignment_id}/requirements")
    async def assignment_requirements_get(assignment_id: str) -> Any:
        _require_teacher_or_admin()
        return await assignment_app.get_assignment_requirements(assignment_id, deps=app_deps)
