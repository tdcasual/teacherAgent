"""API routes for teacher skill CRUD and GitHub import."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from .skill_crud_routes import register_skill_crud_routes
from .skill_import_routes import register_skill_import_routes


def build_router(core: Any) -> APIRouter:
    router = APIRouter()
    register_skill_crud_routes(router, core)
    register_skill_import_routes(router, core)
    return router
