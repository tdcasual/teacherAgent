from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from starlette.concurrency import run_in_threadpool

from ..api_models import TeacherSkillImportRequest
from ..auth_service import AuthError, require_principal


def _require_teacher_or_admin() -> None:
    try:
        require_principal(roles=("teacher", "admin"))
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


def register_skill_import_routes(router: APIRouter, core: Any) -> None:
    @router.post("/teacher/skills/import")
    async def import_skill(req: TeacherSkillImportRequest) -> Any:
        _require_teacher_or_admin()
        try:
            return await run_in_threadpool(
                core.import_skill_from_github,
                github_url=req.github_url,
                overwrite=req.overwrite,
            )
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @router.post("/teacher/skills/preview")
    async def preview_skill(req: TeacherSkillImportRequest) -> Any:
        _require_teacher_or_admin()
        try:
            return await run_in_threadpool(core.preview_github_skill, github_url=req.github_url)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @router.get("/teacher/skills/{skill_id}/deps")
    async def check_deps(skill_id: str) -> Any:
        _require_teacher_or_admin()
        try:
            return await run_in_threadpool(core.check_skill_dependencies, skill_id=skill_id)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @router.post("/teacher/skills/{skill_id}/install-deps")
    async def install_deps(skill_id: str) -> Any:
        _require_teacher_or_admin()
        try:
            return await run_in_threadpool(core.install_skill_dependencies, skill_id=skill_id)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
