import pytest
from fastapi import APIRouter, FastAPI

from services.api import app_routes


class DummyCore:
    pass


def test_register_routes_includes_assignment_router():
    app = FastAPI()
    called = {}

    def fake_build(core):
        called["core"] = core
        router = APIRouter()

        @router.get("/__assignment_probe")
        async def probe():
            return {"ok": True}

        return router

    original = app_routes.build_assignment_router
    app_routes.build_assignment_router = fake_build
    try:
        app_routes.register_routes(app, DummyCore())
    finally:
        app_routes.build_assignment_router = original

    assert called.get("core").__class__ is DummyCore
    assert any(route.path == "/__assignment_probe" for route in app.router.routes)


def test_register_routes_rejects_missing_core() -> None:
    app = FastAPI()
    with pytest.raises(ValueError, match="core must not be None"):
        app_routes.register_routes(app, None)


def test_register_routes_does_not_mount_survey_class_report_or_analysis_report() -> None:
    app = FastAPI()
    app_routes.register_routes(app, DummyCore())
    paths = {getattr(route, "path", "") for route in app.router.routes}
    forbidden_prefixes = (
        "/teacher/analysis",
        "/teacher/surveys",
        "/webhooks/surveys",
        "/teacher/class-reports",
    )
    mounted = {path for path in paths if any(path.startswith(prefix) for prefix in forbidden_prefixes)}
    assert not mounted
    assert any("/assignment" in path for path in paths)
