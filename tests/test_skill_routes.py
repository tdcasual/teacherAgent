from services.api.routes import skill_routes


def _has_route(router, method, path):
    return any(path == route.path and method in (route.methods or set()) for route in router.routes)


def test_skill_routes_build_router():
    router = skill_routes.build_router(object())
    assert not _has_route(router, "POST", "/teacher/skills")
    assert not _has_route(router, "POST", "/teacher/skills/import")
