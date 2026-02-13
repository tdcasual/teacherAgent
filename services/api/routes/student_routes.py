from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from .student_history_routes import register_student_history_routes
from .student_ops_routes import register_student_ops_routes
from .student_persona_routes import register_student_persona_routes
from .student_profile_routes import register_student_profile_routes


def build_router(core: Any) -> APIRouter:
    router = APIRouter()
    register_student_history_routes(router, core)
    register_student_profile_routes(router, core)
    register_student_persona_routes(router, core)
    register_student_ops_routes(router, core)
    return router
