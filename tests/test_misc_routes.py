from services.api.routes import misc_routes


def _has_route(router, method, path):
    return any(
        path == route.path and method in (route.methods or set())
        for route in router.routes
    )


def test_misc_routes_build_router():
    router = misc_routes.build_router(object())
    assert _has_route(router, "GET", "/health")
    assert _has_route(router, "POST", "/upload")
    assert _has_route(router, "GET", "/lessons")
    assert _has_route(router, "GET", "/skills")
    assert _has_route(router, "POST", "/auth/student/identify")
    assert _has_route(router, "POST", "/auth/student/login")
    assert _has_route(router, "POST", "/auth/student/set-password")
    assert _has_route(router, "POST", "/auth/teacher/identify")
    assert _has_route(router, "POST", "/auth/teacher/login")
    assert _has_route(router, "POST", "/auth/teacher/set-password")
    assert _has_route(router, "POST", "/auth/admin/login")
    assert _has_route(router, "GET", "/auth/admin/teacher/list")
    assert _has_route(router, "POST", "/auth/admin/teacher/set-disabled")
    assert _has_route(router, "POST", "/auth/admin/teacher/reset-password")
    assert _has_route(router, "POST", "/auth/admin/student/reset-token")
    assert _has_route(router, "POST", "/auth/admin/teacher/reset-token")
    assert _has_route(router, "POST", "/auth/admin/student/export-tokens")
    assert _has_route(router, "POST", "/auth/admin/teacher/export-tokens")
    assert _has_route(router, "GET", "/charts/{run_id}/{file_name}")
    assert _has_route(router, "GET", "/chart-runs/{run_id}/meta")
