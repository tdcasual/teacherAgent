from fastapi.testclient import TestClient

import services.api.app as app_mod


def test_app_has_container_on_startup() -> None:
    app = getattr(app_mod, '_DEFAULT_APP', app_mod.app)
    with TestClient(app) as client:
        response = client.get('/health')
        assert response.status_code == 200
        assert hasattr(client.app.state, 'container')
