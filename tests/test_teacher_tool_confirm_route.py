from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.api.routes.teacher_tool_confirm_routes import register_tool_confirm_routes


class _Core:
    def __init__(self) -> None:
        self.calls = []

    def tool_dispatch(self, *args, **kwargs):
        self.calls.append(("dispatch", args, kwargs))
        return {"ok": True}


def test_teacher_tools_confirm_route_404_unknown(monkeypatch) -> None:
    monkeypatch.setattr(
        "services.api.routes.teacher_tool_confirm_routes.resolve_confirm_actor_id",
        lambda: "teacher-1",
    )
    monkeypatch.setattr(
        "services.api.routes.teacher_tool_confirm_routes.confirm_teacher_tool",
        lambda **kwargs: {"error": "confirm_not_found"},
    )
    app = FastAPI()
    from fastapi import APIRouter

    router = APIRouter()
    register_tool_confirm_routes(router, _Core())
    app.include_router(router)
    client = TestClient(app)
    res = client.post("/teacher/tools/confirm", json={"confirm_id": "missing", "confirmed": True})
    assert res.status_code == 404
    assert res.json()["detail"] == "confirm_not_found"


def test_teacher_tools_confirm_route_ok(monkeypatch) -> None:
    monkeypatch.setattr(
        "services.api.routes.teacher_tool_confirm_routes.resolve_confirm_actor_id",
        lambda: "teacher-1",
    )
    monkeypatch.setattr(
        "services.api.routes.teacher_tool_confirm_routes.confirm_teacher_tool",
        lambda **kwargs: {"ok": True, "job_id": "job-1", "executed": True},
    )
    app = FastAPI()
    from fastapi import APIRouter

    router = APIRouter()
    register_tool_confirm_routes(router, _Core())
    app.include_router(router)
    client = TestClient(app)
    res = client.post("/teacher/tools/confirm", json={"confirm_id": "abc", "confirmed": True})
    assert res.status_code == 200
    assert res.json()["ok"] is True
