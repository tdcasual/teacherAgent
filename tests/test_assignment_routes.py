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
    assert _has_route(router, "POST", "/assignment/upload/start")
    assert _has_route(router, "POST", "/assignment/upload/confirm")
    assert _has_route(router, "GET", "/assignment/{assignment_id}/download")
    assert _has_route(router, "POST", "/assignment/questions/ocr")
    assert _has_route(router, "POST", "/assignment/{assignment_id}/recompute-roster")
    assert _has_route(router, "POST", "/assignment/{assignment_id}/archive")
    assert _has_route(router, "POST", "/assignment/{assignment_id}/unarchive")


def test_assignment_routes_call_assignment_application_layer(monkeypatch):
    class _Core:
        pass

    called = {"count": 0}

    async def _fake_list_assignments(*, limit=50, cursor=0, deps):
        called["count"] += 1
        called["limit"] = limit
        called["cursor"] = cursor
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
    assert called["limit"] == 50
    assert called["cursor"] == 0


def test_teacher_progress_does_not_auto_archive_before_owner_access(monkeypatch):
    from services.api.assignment.application import AssignmentAccessError
    from services.api.routes import assignment_listing_routes

    order: list[str] = []

    def _require_teacher_or_admin() -> None:
        order.append("role")

    def _deny_access(assignment_id: str, *, deps):
        order.append("access")
        raise AssignmentAccessError(403, "forbidden_assignment_owner")

    def _auto_archive(assignment_id: str, **_kwargs):
        order.append("auto")
        return True

    monkeypatch.setattr(assignment_listing_routes, "_require_teacher_or_admin", _require_teacher_or_admin)
    monkeypatch.setattr(assignment_listing_routes, "maybe_auto_archive", _auto_archive)

    class _App:
        def require_assignment_access(self, assignment_id, *, deps):
            _deny_access(assignment_id, deps=deps)

        async def get_teacher_assignment_progress(self, assignment_id, *, include_students, deps):
            order.append("progress")
            return {"ok": True}

    app = FastAPI()
    assignment_listing_routes.register_assignment_listing_routes(
        app.router, app_deps=object(), assignment_app=_App(), data_dir=None
    )
    with TestClient(app) as client:
        res = client.get("/teacher/assignment/progress", params={"assignment_id": "HW_OTHER"})
    assert res.status_code == 403
    assert "auto" not in order
    assert order == ["role", "access"]
