def test_register_routes_adds_health_route():
    from fastapi import FastAPI
    from services.api.app_routes import register_routes

    app = FastAPI()
    register_routes(app, mod=None)
    paths = {route.path for route in app.router.routes}
    assert "/health" in paths
