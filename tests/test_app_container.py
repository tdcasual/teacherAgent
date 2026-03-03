from fastapi.testclient import TestClient

import services.api.app as app_mod
from services.api.runtime_settings import load_settings


def test_app_has_container_on_startup(tmp_path) -> None:
    app = app_mod.create_app(
        load_settings(
            {
                "DATA_DIR": str(tmp_path / "data"),
                "UPLOADS_DIR": str(tmp_path / "uploads"),
                "PYTEST_CURRENT_TEST": "1",
            }
        )
    )
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert hasattr(client.app.state, "container")
        assert client.app.state.container.core is client.app.state.core


def test_create_app_uses_fresh_core_runtime(tmp_path) -> None:
    app_a = app_mod.create_app(
        load_settings(
            {
                "DATA_DIR": str(tmp_path / "data_a"),
                "UPLOADS_DIR": str(tmp_path / "uploads_a"),
            }
        )
    )
    app_b = app_mod.create_app(
        load_settings(
            {
                "DATA_DIR": str(tmp_path / "data_b"),
                "UPLOADS_DIR": str(tmp_path / "uploads_b"),
            }
        )
    )

    assert app_a.state.core is not app_b.state.core
    assert app_a.state.core.DATA_DIR == tmp_path / "data_a"
    assert app_b.state.core.DATA_DIR == tmp_path / "data_b"
