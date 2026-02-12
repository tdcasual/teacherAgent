from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from ..api_models import TeacherSkillCreateRequest, TeacherSkillUpdateRequest


def register_skill_crud_routes(router: APIRouter, core: Any) -> None:
    @router.post("/teacher/skills")
    def create_skill(req: TeacherSkillCreateRequest) -> Any:
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
    def update_skill(skill_id: str, req: TeacherSkillUpdateRequest) -> Any:
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
    def delete_skill(skill_id: str) -> Any:
        try:
            return core.delete_teacher_skill(skill_id=skill_id)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
