from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.api.routes import assignment_routes


def _has_route(router, method, path):
    return any(path == route.path and method in (route.methods or set()) for route in router.routes)


def test_assignment_routes_build_router():
    router = assignment_routes.build_router(object())
    assert _has_route(router, "GET", "/assignments")
    assert _has_route(router, "GET", "/assignment/{assignment_id}")
    assert _has_route(router, "POST", "/assignment/requirements")
    assert _has_route(router, "POST", "/assignment/upload")
    assert _has_route(router, "POST", "/assignment/upload/start")
    assert _has_route(router, "POST", "/assignment/upload/confirm")
    assert _has_route(router, "GET", "/assignment/{assignment_id}/download")
    assert _has_route(router, "POST", "/assignment/questions/ocr")


def test_assignment_routes_call_assignment_application_layer(monkeypatch):
    class _Core:
        pass

    called = {"count": 0}

    async def _fake_list_assignments(*, deps):
        called["count"] += 1
        return {"ok": True, "assignments": []}

    monkeypatch.setattr(
        assignment_routes.assignment_application, "list_assignments", _fake_list_assignments
    )
    monkeypatch.setattr(
        assignment_routes.assignment_deps,
        "build_assignment_application_deps",
        lambda _core: object(),
    )

    app = FastAPI()
    app.include_router(assignment_routes.build_router(_Core()))
    with TestClient(app) as client:
        res = client.get("/assignments")

    assert res.status_code == 200
    assert called["count"] == 1
