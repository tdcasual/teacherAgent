from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile

from ..auth_service import AuthError, require_principal


def register_misc_general_routes(router: APIRouter, core: Any) -> None:
    @router.post("/upload")
    async def upload(files: list[UploadFile] = File(...)) -> Any:
        try:
            require_principal()
        except AuthError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)
        return await core.upload_files(files)

    @router.get("/lessons")
    def lessons() -> Any:
        try:
            require_principal()
        except AuthError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)
        return core.list_lessons()

    @router.get("/skills")
    def skills() -> Any:
        try:
            principal = require_principal()
        except AuthError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)
        from ..skills.affiliates import extra_skill_ids_for_principal

        extra = extra_skill_ids_for_principal(core, principal)
        return core.list_skills(extra_skill_ids=extra)
