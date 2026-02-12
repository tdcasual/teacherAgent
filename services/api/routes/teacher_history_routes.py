from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException

from .teacher_route_helpers import scoped_teacher_id


def register_history_routes(router: APIRouter, core: Any) -> None:
    @router.get("/teacher/history/sessions")
    def teacher_history_sessions(
        teacher_id: Optional[str] = None, limit: int = 20, cursor: int = 0
    ) -> Any:
        teacher_id_scoped = scoped_teacher_id(teacher_id)
        return core._teacher_history_sessions_api_impl(
            teacher_id_scoped,
            limit=limit,
            cursor=cursor,
            deps=core._session_history_api_deps(),
        )

    @router.get("/teacher/session/view-state")
    def teacher_session_view_state(teacher_id: Optional[str] = None) -> Any:
        teacher_id_scoped = scoped_teacher_id(teacher_id)
        return core._teacher_session_view_state_api_impl(
            teacher_id_scoped, deps=core._session_history_api_deps()
        )

    @router.put("/teacher/session/view-state")
    def update_teacher_session_view_state(req: dict[str, Any]) -> Any:
        payload = dict(req or {})
        payload["teacher_id"] = scoped_teacher_id(payload.get("teacher_id"))
        return core._update_teacher_session_view_state_api_impl(
            payload, deps=core._session_history_api_deps()
        )

    @router.get("/teacher/history/session")
    def teacher_history_session(
        session_id: str,
        teacher_id: Optional[str] = None,
        cursor: int = -1,
        limit: int = 50,
        direction: str = "backward",
    ) -> Any:
        teacher_id_scoped = scoped_teacher_id(teacher_id)
        try:
            return core._teacher_history_session_api_impl(
                session_id,
                teacher_id_scoped,
                cursor=cursor,
                limit=limit,
                direction=direction,
                deps=core._session_history_api_deps(),
            )
        except core.SessionHistoryApiError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)
