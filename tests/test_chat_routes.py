from services.api.routes import chat_routes


def _has_route(router, method, path):
    return any(
        path == route.path and method in (route.methods or set())
        for route in router.routes
    )


def test_chat_routes_build_router():
    router = chat_routes.build_router(object())
    assert _has_route(router, "POST", "/chat")
    assert _has_route(router, "POST", "/chat/start")
    assert _has_route(router, "GET", "/chat/status")
    assert _has_route(router, "POST", "/chat/attachments")
    assert _has_route(router, "GET", "/chat/attachments/status")
    assert _has_route(router, "DELETE", "/chat/attachments/{attachment_id}")
