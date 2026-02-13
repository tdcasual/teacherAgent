from services.api.routes import teacher_routes


def _has_route(router, method, path):
    return any(
        path == route.path and method in (route.methods or set())
        for route in router.routes
    )


def test_teacher_routes_build_router():
    router = teacher_routes.build_router(object())
    assert _has_route(router, "GET", "/teacher/history/sessions")
    assert _has_route(router, "GET", "/teacher/session/view-state")
    assert _has_route(router, "PUT", "/teacher/session/view-state")
    assert _has_route(router, "GET", "/teacher/history/session")
    assert _has_route(router, "GET", "/teacher/memory/proposals")
    assert _has_route(router, "GET", "/teacher/memory/insights")
    assert _has_route(router, "POST", "/teacher/memory/proposals/{proposal_id}/review")
    assert _has_route(router, "GET", "/teacher/llm-routing")
    assert _has_route(router, "POST", "/teacher/llm-routing/simulate")
    assert _has_route(router, "POST", "/teacher/llm-routing/rollback")
    assert _has_route(router, "GET", "/teacher/provider-registry")
    assert _has_route(router, "POST", "/teacher/provider-registry/providers")
    assert _has_route(router, "GET", "/teacher/personas")
    assert _has_route(router, "POST", "/teacher/personas")
    assert _has_route(router, "PATCH", "/teacher/personas/{persona_id}")
    assert _has_route(router, "POST", "/teacher/personas/{persona_id}/assign")
    assert _has_route(router, "POST", "/teacher/personas/{persona_id}/visibility")
