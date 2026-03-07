from __future__ import annotations

from fastapi import APIRouter, FastAPI

from services.api import app_routes
from services.api.routes import survey_routes


class DummyCore:
    pass


def _has_route(router, method, path):
    return any(path == route.path and method in (route.methods or set()) for route in router.routes)


def test_survey_routes_build_router() -> None:
    router = survey_routes.build_router(object())
    assert _has_route(router, "POST", "/webhooks/surveys/provider")
    assert _has_route(router, "GET", "/teacher/surveys/reports")
    assert _has_route(router, "GET", "/teacher/surveys/reports/{report_id}")
    assert _has_route(router, "POST", "/teacher/surveys/reports/{report_id}/rerun")
    assert _has_route(router, "GET", "/teacher/surveys/review-queue")


def test_register_routes_includes_survey_router() -> None:
    app = FastAPI()
    called = {}

    def fake_build(core):
        called["core"] = core
        router = APIRouter()

        @router.get("/__survey_probe")
        async def probe():
            return {"ok": True}

        return router

    original = app_routes.build_survey_router
    app_routes.build_survey_router = fake_build
    try:
        app_routes.register_routes(app, DummyCore())
    finally:
        app_routes.build_survey_router = original

    assert called.get("core").__class__ is DummyCore
    assert any(route.path == "/__survey_probe" for route in app.router.routes)
