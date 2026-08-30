from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException

from ..api_models import AssignmentRequirementsRequest, TeacherGradeRequest
from ..assignment.application import AssignmentAccessError
from ..assignment_archive_service import (
    AssignmentArchiveError,
    archive_assignment,
    maybe_auto_archive,
    maybe_auto_archive_owner_assignments,
    unarchive_assignment,
)
from ..assignment_recompute_roster_service import (
    AssignmentRecomputeRosterError,
    recompute_assignment_roster,
)
from ..auth_service import AuthError, require_principal
from ..teacher_grade_service import TeacherGradeError, save_teacher_grade_from_request


def _require_teacher_or_admin() -> None:
    try:
        require_principal(roles=("teacher", "admin", "service"))
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


def _http_from_assignment_access(exc: AssignmentAccessError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


def _owner_principal() -> Any:
    try:
        principal = require_principal(roles=("teacher", "admin"))
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    if principal is None:
        raise HTTPException(status_code=401, detail="missing_authorization")
    return principal


def _register_progress_routes(
    router: APIRouter, *, app_deps: Any, assignment_app: Any, data_dir: Any
) -> None:
    @router.get("/teacher/assignment/progress")
    async def teacher_assignment_progress(assignment_id: str, include_students: bool = True) -> Any:
        _require_teacher_or_admin()
        try:
            assignment_app.require_assignment_access(assignment_id, deps=app_deps)
            owner = assignment_app.listing_owner_teacher_id()
            maybe_auto_archive(assignment_id, data_dir=data_dir, owner_teacher_id=owner)
            return await assignment_app.get_teacher_assignment_progress(
                assignment_id,
                include_students=include_students,
                deps=app_deps,
            )
        except AssignmentAccessError as exc:
            raise _http_from_assignment_access(exc) from exc

    @router.get("/teacher/assignments/progress")
    async def teacher_assignments_progress(date: Optional[str] = None) -> Any:
        _require_teacher_or_admin()
        try:
            owner = assignment_app.listing_owner_teacher_id()
            maybe_auto_archive_owner_assignments(owner, data_dir=data_dir)
            return await assignment_app.get_teacher_assignments_progress(
                date=date,
                deps=app_deps,
            )
        except AssignmentAccessError as exc:
            raise _http_from_assignment_access(exc) from exc


def _register_grade_routes(
    router: APIRouter, *, app_deps: Any, assignment_app: Any, data_dir: Any
) -> None:
    @router.post("/teacher/assignment/{assignment_id}/student/{student_id}/grade")
    def teacher_student_grade(
        assignment_id: str, student_id: str, req: TeacherGradeRequest
    ) -> Any:
        _require_teacher_or_admin()
        try:
            assignment_app.require_assignment_access(assignment_id, deps=app_deps)
            principal = require_principal(roles=("teacher", "admin"))
            return save_teacher_grade_from_request(
                assignment_id,
                student_id,
                principal=principal,
                data_dir=data_dir,
                request=req,
            )
        except AssignmentAccessError as exc:
            raise _http_from_assignment_access(exc) from exc
        except TeacherGradeError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


def _register_archive_routes(router: APIRouter, *, data_dir: Any) -> None:
    @router.post("/assignment/{assignment_id}/archive")
    def assignment_archive(assignment_id: str) -> Any:
        principal = _owner_principal()
        try:
            return archive_assignment(assignment_id, principal=principal, data_dir=data_dir)
        except AssignmentArchiveError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)

    @router.post("/assignment/{assignment_id}/unarchive")
    def assignment_unarchive(assignment_id: str) -> Any:
        principal = _owner_principal()
        try:
            return unarchive_assignment(assignment_id, principal=principal, data_dir=data_dir)
        except AssignmentArchiveError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)


def register_assignment_listing_routes(
    router: APIRouter, *, app_deps: Any, assignment_app: Any, data_dir: Any = None
) -> None:
    @router.get("/assignments")
    async def assignments(limit: int = 50, cursor: int = 0) -> Any:
        _require_teacher_or_admin()
        try:
            return await assignment_app.list_assignments(limit=limit, cursor=cursor, deps=app_deps)
        except AssignmentAccessError as exc:
            raise _http_from_assignment_access(exc) from exc

    _register_progress_routes(
        router, app_deps=app_deps, assignment_app=assignment_app, data_dir=data_dir
    )
    _register_grade_routes(
        router, app_deps=app_deps, assignment_app=assignment_app, data_dir=data_dir
    )

    @router.post("/assignment/requirements")
    async def assignment_requirements(req: AssignmentRequirementsRequest) -> Any:
        _require_teacher_or_admin()
        try:
            return await assignment_app.post_assignment_requirements(req, deps=app_deps)
        except AssignmentAccessError as exc:
            raise _http_from_assignment_access(exc) from exc

    @router.get("/assignment/{assignment_id}/requirements")
    async def assignment_requirements_get(assignment_id: str) -> Any:
        _require_teacher_or_admin()
        try:
            return await assignment_app.get_assignment_requirements(assignment_id, deps=app_deps)
        except AssignmentAccessError as exc:
            raise _http_from_assignment_access(exc) from exc

    @router.post("/assignment/{assignment_id}/recompute-roster")
    def assignment_recompute_roster(assignment_id: str) -> Any:
        principal = _owner_principal()
        try:
            return recompute_assignment_roster(
                assignment_id, principal=principal, data_dir=data_dir
            )
        except AssignmentRecomputeRosterError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)

    _register_archive_routes(router, data_dir=data_dir)
