from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from ..assignment_data_service import load_assignment_meta
from ..assignment_student_list_service import (
    StudentAssignmentListDeps,
    list_student_assignment_history,
    student_currently_enrolled,
    today_lookback_days,
)
from ..auth_service import AuthError, resolve_student_scope
from ..session_history_service import SessionHistoryError


def _scoped_student_id(student_id: str | None) -> str:
    try:
        scoped = resolve_student_scope(student_id, required_for_admin=False)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    sid = str(scoped or "").strip()
    if not sid:
        raise HTTPException(status_code=400, detail="student_id is required")
    return sid


def _student_assignment_list_deps(core: Any) -> StudentAssignmentListDeps:
    data_dir = Path(getattr(core, "DATA_DIR"))
    return StudentAssignmentListDeps(
        data_dir=data_dir,
        load_assignment_meta=getattr(core, "load_assignment_meta", load_assignment_meta),
        student_enrolled=lambda sid, tid, sub: student_currently_enrolled(
            sid, tid, sub, data_dir=data_dir
        ),
        list_submission_attempts=core.list_submission_attempts,
        lookback_days=today_lookback_days(),
    )


def register_student_history_routes(router: APIRouter, core: Any) -> None:
    @router.get("/student/assignments/history")
    def student_assignments_history(student_id: str, limit: int = 50, cursor: int = 0) -> Any:
        sid = _scoped_student_id(student_id)
        return list_student_assignment_history(
            student_id=sid,
            limit=limit,
            cursor=cursor,
            deps=_student_assignment_list_deps(core),
        )

    @router.get("/student/history/sessions")
    def student_history_sessions(student_id: str, limit: int = 20, cursor: int = 0) -> Any:
        sid = _scoped_student_id(student_id)
        try:
            return core.student_history_sessions(sid, limit=limit, cursor=cursor)
        except SessionHistoryError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)

    @router.get("/student/session/view-state")
    def student_session_view_state(student_id: str) -> Any:
        sid = _scoped_student_id(student_id)
        try:
            return core.student_session_view_state(sid)
        except SessionHistoryError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)

    @router.put("/student/session/view-state")
    def update_student_session_view_state(req: Dict[str, Any]) -> Any:
        payload = dict(req or {})
        payload["student_id"] = _scoped_student_id(str(payload.get("student_id") or ""))
        try:
            return core.update_student_session_view_state(payload)
        except SessionHistoryError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)

    @router.get("/student/history/session")
    def student_history_session(
        student_id: str,
        session_id: str,
        cursor: int = -1,
        limit: int = 50,
        direction: str = "backward",
    ) -> Any:
        sid = _scoped_student_id(student_id)
        try:
            return core.student_history_session(
                sid,
                session_id,
                cursor=cursor,
                limit=limit,
                direction=direction,
            )
        except SessionHistoryError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)
