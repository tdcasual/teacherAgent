from __future__ import annotations

import importlib
import os
import time
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Dict, Iterator

from fastapi.testclient import TestClient

from services.api.auth_service import mint_test_token
from services.api.observability import ObservabilityStore

_ENV_KEYS = [
    "DATA_DIR",
    "UPLOADS_DIR",
    "DIAG_LOG",
    "MASTER_KEY_DEV_DEFAULT",
    "AUTH_REQUIRED",
    "AUTH_TOKEN_SECRET",
    "ADMIN_USERNAME",
]


def _load_app(tmp_dir: Path, *, auth_required: str, auth_secret: str = ""):
    os.environ["DATA_DIR"] = str(tmp_dir / "data")
    os.environ["UPLOADS_DIR"] = str(tmp_dir / "uploads")
    os.environ["DIAG_LOG"] = "0"
    os.environ["MASTER_KEY_DEV_DEFAULT"] = "dev-key"
    os.environ["AUTH_REQUIRED"] = auth_required
    os.environ["ADMIN_USERNAME"] = "admin"
    if auth_secret:
        os.environ["AUTH_TOKEN_SECRET"] = auth_secret
    else:
        os.environ.pop("AUTH_TOKEN_SECRET", None)
    import services.api.app as app_mod

    importlib.reload(app_mod)
    return app_mod


def _auth_headers(*, actor_id: str, role: str, secret: str) -> Dict[str, str]:
    now = int(time.time())
    claims = {"sub": actor_id, "role": role, "exp": now + 3600}
    if role == "admin":
        claims["tv"] = 1
    token = mint_test_token(claims, secret=secret)
    return {"Authorization": f"Bearer {token}"}


@contextmanager
def _env_guard() -> Iterator[None]:
    backup = {key: os.environ.get(key) for key in _ENV_KEYS}
    try:
        yield
    finally:
        for key, value in backup.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def test_prometheus_text_exports_in_process_http_series() -> None:
    store = ObservabilityStore()
    store.record(method="GET", route="/health", status_code=200, latency_sec=0.04)
    store.record(method="POST", route="/chat/start", status_code=503, latency_sec=1.2)

    text = store.prometheus_text()
    assert "# TYPE http_requests_total counter" in text
    assert "http_requests_total 2" in text
    assert "http_5xx_total 1" in text
    assert 'http_latency_seconds{quantile="0.95"}' in text
    assert 'http_requests_by_route_total{route="GET /health"} 1' in text
    assert 'http_5xx_by_route_total{route="POST /chat/start"} 1' in text
    assert "slo_latency_p95_ok" in text
    assert "slo_error_rate_ok" in text
    assert 'http_request_duration_seconds_bucket{le="+Inf"} 2' in text


def test_prometheus_metrics_export_requires_service_or_admin() -> None:
    with _env_guard():
        with TemporaryDirectory() as td:
            secret = "prom-auth-secret"
            app_mod = _load_app(Path(td), auth_required="1", auth_secret=secret)
            with TestClient(app_mod.app) as client:
                assert client.get("/ops/metrics.prom").status_code == 401

                service_headers = _auth_headers(actor_id="svc_ops", role="service", secret=secret)
                admin_headers = _auth_headers(actor_id="admin", role="admin", secret=secret)

                service = client.get("/ops/metrics.prom", headers=service_headers)
                admin = client.get("/ops/metrics.prom", headers=admin_headers)
                assert service.status_code == 200
                assert admin.status_code == 200
                assert service.text.startswith("#")
                assert "http_requests_total" in service.text
                content_type = (service.headers.get("content-type") or "").lower()
                assert content_type.startswith("text/plain")
