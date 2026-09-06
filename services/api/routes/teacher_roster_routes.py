from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from ..auth_registry_service import build_auth_registry_store
from ..auth_service import AuthError, require_principal


def register_roster_routes(router: APIRouter, core: Any) -> None:
    @router.get("/teacher/roster")
    def teacher_roster() -> Any:
        try:
            principal = require_principal(roles=("teacher", "admin"))
        except AuthError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)
        if principal is None:
            raise HTTPException(status_code=401, detail="missing_authorization")
        teacher_id = str(principal.actor_id or "").strip()
        if not teacher_id:
            raise HTTPException(status_code=400, detail="teacher_id_required")
        return build_auth_registry_store(data_dir=core.DATA_DIR).list_roster(
            teacher_id=teacher_id
        )
