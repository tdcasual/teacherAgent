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
