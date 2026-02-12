from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from ..exam import application as exam_application
from ..exam import deps as exam_deps
from .exam_query_routes import register_exam_query_routes
from .exam_upload_routes import register_exam_upload_routes


def build_router(core: Any) -> APIRouter:
    router = APIRouter()
    app_deps = exam_deps.build_exam_application_deps(core)
    register_exam_query_routes(router, app_deps=app_deps, exam_app=exam_application)
    register_exam_upload_routes(router, app_deps=app_deps, exam_app=exam_application)
    return router
