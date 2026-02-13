from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from ..auth_service import AuthError, resolve_student_scope


def _scoped_student_id(student_id: str | None) -> str:
    try:
        scoped = resolve_student_scope(student_id, required_for_admin=False)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    sid = str(scoped or "").strip()
    if not sid:
        raise HTTPException(status_code=400, detail="student_id is required")
    return sid


def register_student_history_routes(router: APIRouter, core: Any) -> None:
    @router.get("/student/history/sessions")
    def student_history_sessions(student_id: str, limit: int = 20, cursor: int = 0) -> Any:
        sid = _scoped_student_id(student_id)
        try:
            return core._student_history_sessions_api_impl(
                sid,
                limit=limit,
                cursor=cursor,
                deps=core._session_history_api_deps(),
            )
        except core.SessionHistoryApiError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)

    @router.get("/student/session/view-state")
    def student_session_view_state(student_id: str) -> Any:
        sid = _scoped_student_id(student_id)
        try:
            return core._student_session_view_state_api_impl(
                sid, deps=core._session_history_api_deps()
            )
        except core.SessionHistoryApiError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)

    @router.put("/student/session/view-state")
    def update_student_session_view_state(req: Dict[str, Any]) -> Any:
        payload = dict(req or {})
        payload["student_id"] = _scoped_student_id(str(payload.get("student_id") or ""))
        try:
            return core._update_student_session_view_state_api_impl(
                payload, deps=core._session_history_api_deps()
            )
        except core.SessionHistoryApiError as exc:
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
            return core._student_history_session_api_impl(
                sid,
                session_id,
                cursor=cursor,
                limit=limit,
                direction=direction,
                deps=core._session_history_api_deps(),
            )
        except core.SessionHistoryApiError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)
