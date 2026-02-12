from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from .misc_chart_routes import register_misc_chart_routes
from .misc_general_routes import register_misc_general_routes
from .misc_health_routes import register_misc_health_routes


def build_router(core: Any) -> APIRouter:
    router = APIRouter()
    register_misc_health_routes(router, core)
    register_misc_general_routes(router, core)
    register_misc_chart_routes(router, core)
    return router
