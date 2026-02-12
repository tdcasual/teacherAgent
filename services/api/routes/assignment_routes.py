from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from ..assignment import application as assignment_application
from ..assignment import deps as assignment_deps
from .assignment_delivery_routes import register_assignment_delivery_routes
from .assignment_generation_routes import register_assignment_generation_routes
from .assignment_listing_routes import register_assignment_listing_routes
from .assignment_upload_routes import register_assignment_upload_routes


def build_router(core: Any) -> APIRouter:
    router = APIRouter()
    app_deps = assignment_deps.build_assignment_application_deps(core)
    register_assignment_listing_routes(
        router, app_deps=app_deps, assignment_app=assignment_application
    )
    register_assignment_upload_routes(
        router, app_deps=app_deps, assignment_app=assignment_application
    )
    register_assignment_delivery_routes(
        router, app_deps=app_deps, assignment_app=assignment_application, core=core
    )
    register_assignment_generation_routes(
        router, app_deps=app_deps, assignment_app=assignment_application
    )
    return router
