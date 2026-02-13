from services.api.routes import student_routes


def _has_route(router, method, path):
    return any(
        path == route.path and method in (route.methods or set())
        for route in router.routes
    )


def test_student_routes_build_router():
    router = student_routes.build_router(object())
    assert _has_route(router, "GET", "/student/history/sessions")
    assert _has_route(router, "GET", "/student/session/view-state")
    assert _has_route(router, "PUT", "/student/session/view-state")
    assert _has_route(router, "GET", "/student/history/session")
    assert _has_route(router, "GET", "/student/profile/{student_id}")
    assert _has_route(router, "POST", "/student/profile/update")
    assert _has_route(router, "GET", "/student/personas")
    assert _has_route(router, "POST", "/student/personas/custom")
    assert _has_route(router, "POST", "/student/personas/activate")
    assert _has_route(router, "DELETE", "/student/personas/custom/{persona_id}")
    assert _has_route(router, "POST", "/student/import")
    assert _has_route(router, "POST", "/student/verify")
    assert _has_route(router, "POST", "/student/submit")
