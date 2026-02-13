from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from .teacher_history_routes import register_history_routes
from .teacher_llm_routing_routes import register_llm_routing_routes
from .teacher_memory_routes import register_memory_routes
from .teacher_persona_routes import register_teacher_persona_routes
from .teacher_provider_registry_routes import register_provider_registry_routes


def build_router(core: Any) -> APIRouter:
    router = APIRouter()
    register_history_routes(router, core)
    register_memory_routes(router, core)
    register_llm_routing_routes(router, core)
    register_provider_registry_routes(router, core)
    register_teacher_persona_routes(router, core)
    return router
