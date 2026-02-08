def test_health_router_included():
    from fastapi.testclient import TestClient
    from services.api import app as app_mod

    client = TestClient(app_mod.app)
    res = client.get("/health")
    assert res.status_code == 200


def test_app_core_module_exists():
    from services.api import app_core

    assert hasattr(app_core, "health")
