from services.api.routes import skill_routes


def _has_route(router, method, path):
    return any(path == route.path and method in (route.methods or set()) for route in router.routes)


def test_skill_routes_build_router():
    router = skill_routes.build_router(object())
    assert _has_route(router, "POST", "/teacher/skills")
    assert _has_route(router, "PUT", "/teacher/skills/{skill_id}")
    assert _has_route(router, "DELETE", "/teacher/skills/{skill_id}")
    assert _has_route(router, "POST", "/teacher/skills/import")
    assert _has_route(router, "POST", "/teacher/skills/preview")
    assert _has_route(router, "GET", "/teacher/skills/{skill_id}/deps")
    assert _has_route(router, "POST", "/teacher/skills/{skill_id}/install-deps")
