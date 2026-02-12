"""API routes for teacher skill CRUD and GitHub import."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from starlette.concurrency import run_in_threadpool

from ..api_models import (
    TeacherSkillCreateRequest,
    TeacherSkillImportRequest,
    TeacherSkillUpdateRequest,
)


def build_router(core) -> APIRouter:
    router = APIRouter()

    @router.post("/teacher/skills")
    def create_skill(req: TeacherSkillCreateRequest):
        try:
            return core.create_teacher_skill(
                title=req.title,
                description=req.description,
                keywords=req.keywords,
                examples=req.examples,
                allowed_roles=req.allowed_roles,
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @router.put("/teacher/skills/{skill_id}")
    def update_skill(skill_id: str, req: TeacherSkillUpdateRequest):
        try:
            return core.update_teacher_skill(
                skill_id=skill_id,
                title=req.title,
                description=req.description,
                keywords=req.keywords,
                examples=req.examples,
                allowed_roles=req.allowed_roles,
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @router.delete("/teacher/skills/{skill_id}")
    def delete_skill(skill_id: str):
        try:
            return core.delete_teacher_skill(skill_id=skill_id)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @router.post("/teacher/skills/import")
    async def import_skill(req: TeacherSkillImportRequest):
        try:
            return await run_in_threadpool(core.import_skill_from_github, github_url=req.github_url, overwrite=req.overwrite)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @router.post("/teacher/skills/preview")
    async def preview_skill(req: TeacherSkillImportRequest):
        try:
            return await run_in_threadpool(core.preview_github_skill, github_url=req.github_url)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @router.get("/teacher/skills/{skill_id}/deps")
    async def check_deps(skill_id: str):
        try:
            return await run_in_threadpool(core.check_skill_dependencies, skill_id=skill_id)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @router.post("/teacher/skills/{skill_id}/install-deps")
    async def install_deps(skill_id: str):
        try:
            return await run_in_threadpool(core.install_skill_dependencies, skill_id=skill_id)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    return router
