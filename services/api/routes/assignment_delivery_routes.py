from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException

from ..assignment.application import AssignmentAccessError
from ..assignment_today_service import AssignmentTodayError
from ..auth_service import AuthError, resolve_student_scope


def _scoped_student_id(student_id: Optional[str]) -> str:
    try:
        scoped = resolve_student_scope(student_id, required_for_admin=False)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    sid = str(scoped or "").strip()
    if not sid:
        raise HTTPException(status_code=400, detail="student_id is required")
    return sid


def _http_from_assignment_access(exc: AssignmentAccessError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


def register_assignment_delivery_routes(
    router: APIRouter, *, app_deps: Any, assignment_app: Any
) -> None:
    @router.get("/assignment/{assignment_id}/download")
    async def assignment_download(assignment_id: str, file: str) -> Any:
        try:
            return await assignment_app.download_assignment_file(
                assignment_id,
                file,
                deps=app_deps,
            )
        except AssignmentAccessError as exc:
            raise _http_from_assignment_access(exc) from exc

    @router.get("/assignment/today")
    async def assignment_today(
        student_id: str,
        date: Optional[str] = None,
        auto_generate: bool = False,
        generate: bool = True,
        per_kp: int = 5,
    ) -> Any:
        sid = _scoped_student_id(student_id)
        try:
            return await assignment_app.get_assignment_today(
                student_id=sid,
                date=date,
                auto_generate=auto_generate,
                generate=generate,
                per_kp=per_kp,
                deps=app_deps,
            )
        except AssignmentTodayError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    @router.get("/assignment/{assignment_id}")
    async def assignment_detail(assignment_id: str) -> Any:
        try:
            return await assignment_app.get_assignment_detail(
                assignment_id,
                deps=app_deps,
            )
        except AssignmentAccessError as exc:
            raise _http_from_assignment_access(exc) from exc
