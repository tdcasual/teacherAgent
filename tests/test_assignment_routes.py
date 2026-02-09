from services.api.routes import assignment_routes


def _has_route(router, method, path):
    return any(
        path == route.path and method in (route.methods or set())
        for route in router.routes
    )


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
