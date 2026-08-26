from __future__ import annotations

from fastapi.testclient import TestClient

from llm_gateway import LLMGateway
from services.api.app import create_app
from services.api.container import AppContainer, build_app_container
from services.api.core_runtime import build_core_runtime
from services.api.observability import ObservabilityStore
from services.api.runtime_settings import load_settings
from services.api.wiring import CURRENT_CORE


def _settings(tmp_path, name: str = "data"):
    return load_settings(
        {
            "DATA_DIR": str(tmp_path / name),
            "UPLOADS_DIR": str(tmp_path / f"{name}_uploads"),
            "PYTEST_CURRENT_TEST": "1",
        }
    )


def test_build_app_container_accepts_explicit_gateway_and_observability(tmp_path) -> None:
    core = build_core_runtime(settings=_settings(tmp_path))
    gateway = LLMGateway()
    obs = ObservabilityStore()
    container = build_app_container(core=core, llm_gateway=gateway, observability=obs)
    assert isinstance(container, AppContainer)
    assert container.core is core
    assert container.llm_gateway is gateway
    assert container.observability is obs


def test_build_app_container_defaults_mount_gateway_and_observability(tmp_path) -> None:
    core = build_core_runtime(settings=_settings(tmp_path))
    container = build_app_container(core=core)
    assert container.llm_gateway is not None
    assert hasattr(container.llm_gateway, "generate")
    assert container.llm_gateway is core.LLM_GATEWAY
    assert container.observability is not None
    assert callable(container.observability.snapshot)
    snap = container.observability.snapshot()
    assert "http_requests_total" in snap
    assert "slo" in snap


def test_create_app_exposes_gateway_and_obs_on_state_container(tmp_path) -> None:
    app = create_app(_settings(tmp_path))
    container = app.state.container
    assert container.core is app.state.core
    assert container.llm_gateway is app.state.core.LLM_GATEWAY
    assert hasattr(container.observability, "snapshot")
    # CURRENT_CORE remains the request/runtime core handle this PR.
    assert CURRENT_CORE.get(None) is app.state.core


def test_ops_metrics_reads_observability_from_container_not_module_global(tmp_path) -> None:
    app = create_app(_settings(tmp_path))
    injected = ObservabilityStore()
    injected.record(method="GET", route="/from-container", status_code=200, latency_sec=0.02)
    app.state.container = build_app_container(
        core=app.state.container.core,
        llm_gateway=app.state.container.llm_gateway,
        observability=injected,
    )
    with TestClient(app) as client:
        response = client.get("/ops/metrics")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    routes = payload["metrics"]["requests_by_route"]
    assert "GET /from-container" in routes


def test_ops_slo_reads_observability_from_container(tmp_path) -> None:
    app = create_app(_settings(tmp_path))
    injected = ObservabilityStore()
    injected.record(method="POST", route="/slo-probe", status_code=500, latency_sec=0.5)
    app.state.container = build_app_container(
        core=app.state.container.core,
        llm_gateway=app.state.container.llm_gateway,
        observability=injected,
    )
    with TestClient(app) as client:
        response = client.get("/ops/slo")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["http_requests_total"] == 1
    assert payload["http_error_rate"] == 1.0


def test_middleware_records_to_container_observability(tmp_path) -> None:
    app = create_app(_settings(tmp_path))
    injected = ObservabilityStore()
    app.state.container = build_app_container(
        core=app.state.container.core,
        llm_gateway=app.state.container.llm_gateway,
        observability=injected,
    )
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
    snap = injected.snapshot()
    assert snap["http_requests_total"] >= 1
    assert "GET /health" in snap["requests_by_route"]
