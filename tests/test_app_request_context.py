from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.api import app as app_mod
from services.api.wiring import CURRENT_CORE


def test_request_core_context_uses_app_state_core(monkeypatch) -> None:
    monkeypatch.setenv('AUTH_REQUIRED', '0')

    sentinel = object()
    app = FastAPI()
    app.state.core = sentinel
    app.middleware('http')(app_mod._set_core_context)

    @app.get('/probe')
    async def probe():
        return {'uses_app_state_core': CURRENT_CORE.get(None) is sentinel}

    with TestClient(app) as client:
        response = client.get('/probe')
    assert response.status_code == 200
    assert response.json().get('uses_app_state_core') is True
