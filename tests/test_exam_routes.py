from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.api.routes import exam_routes


def _has_route(router, method, path):
    return any(path == route.path and method in (route.methods or set()) for route in router.routes)


def test_exam_routes_build_router():
    router = exam_routes.build_router(object())
    assert _has_route(router, "GET", "/exams")
    assert _has_route(router, "GET", "/exam/{exam_id}")
    assert _has_route(router, "GET", "/exam/{exam_id}/analysis")
    assert _has_route(router, "GET", "/exam/{exam_id}/students")
    assert _has_route(router, "GET", "/exam/{exam_id}/student/{student_id}")
    assert _has_route(router, "GET", "/exam/{exam_id}/question/{question_id}")
    assert _has_route(router, "POST", "/exam/upload/start")
    assert _has_route(router, "GET", "/exam/upload/status")
    assert _has_route(router, "GET", "/exam/upload/draft")
    assert _has_route(router, "POST", "/exam/upload/draft/save")
    assert _has_route(router, "POST", "/exam/upload/confirm")


def test_exam_routes_call_exam_application_layer(monkeypatch):
    class _Core:
        pass

    called = {"count": 0, "exam_id": ""}

    def _fake_get_exam_detail(exam_id: str, *, deps):
        called["count"] += 1
        called["exam_id"] = exam_id
        return {"ok": True, "exam_id": exam_id}

    monkeypatch.setattr(exam_routes.exam_application, "get_exam_detail", _fake_get_exam_detail)
    monkeypatch.setattr(
        exam_routes.exam_deps,
        "build_exam_application_deps",
        lambda _core: object(),
    )

    app = FastAPI()
    app.include_router(exam_routes.build_router(_Core()))
    with TestClient(app) as client:
        res = client.get("/exam/demo_exam")

    assert res.status_code == 200
    assert called["count"] == 1
    assert called["exam_id"] == "demo_exam"
