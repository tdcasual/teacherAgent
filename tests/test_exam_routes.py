from services.api.routes import exam_routes


def _has_route(router, method, path):
    return any(
        path == route.path and method in (route.methods or set())
        for route in router.routes
    )


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
