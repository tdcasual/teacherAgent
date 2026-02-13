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

_ENV_KEYS = [
    "DATA_DIR",
    "UPLOADS_DIR",
    "DIAG_LOG",
    "MASTER_KEY_DEV_DEFAULT",
    "AUTH_REQUIRED",
    "AUTH_TOKEN_SECRET",
]


def _load_app(tmp_dir: Path, *, auth_required: str, auth_secret: str = ""):
    os.environ["DATA_DIR"] = str(tmp_dir / "data")
    os.environ["UPLOADS_DIR"] = str(tmp_dir / "uploads")
    os.environ["DIAG_LOG"] = "0"
    os.environ["MASTER_KEY_DEV_DEFAULT"] = "dev-key"
    os.environ["AUTH_REQUIRED"] = auth_required
    if auth_secret:
        os.environ["AUTH_TOKEN_SECRET"] = auth_secret
    else:
        os.environ.pop("AUTH_TOKEN_SECRET", None)
    import services.api.app as app_mod

    importlib.reload(app_mod)
    return app_mod


def _auth_headers(*, actor_id: str = "ops_service", role: str = "service", secret: str) -> Dict[str, str]:
    now = int(time.time())
    token = mint_test_token(
        {"sub": actor_id, "role": role, "exp": now + 3600},
        secret=secret,
    )
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


def test_ops_metrics_exposes_observability_snapshot() -> None:
    with _env_guard():
        with TemporaryDirectory() as td:
            app_mod = _load_app(Path(td), auth_required="0")
            with TestClient(app_mod.app) as client:
                assert client.get("/health").status_code == 200

                response = client.get("/ops/metrics")
                assert response.status_code == 200
                payload = response.json()
                assert payload["ok"] is True
                metrics = payload["metrics"]
                assert metrics["http_requests_total"] >= 1
                assert "http_latency_sec" in metrics
                assert "slo" in metrics
                assert "GET /health" in metrics["requests_by_route"]
                assert response.headers.get("x-request-id")


def test_ops_slo_includes_core_projection_fields() -> None:
    with _env_guard():
        with TemporaryDirectory() as td:
            app_mod = _load_app(Path(td), auth_required="0")
            with TestClient(app_mod.app) as client:
                assert client.get("/health").status_code == 200

                response = client.get("/ops/slo")
                assert response.status_code == 200
                payload = response.json()
                assert payload["ok"] is True
                assert isinstance(payload["slo"], dict)
                assert "http_requests_total" in payload
                assert "http_error_rate" in payload
                assert "http_latency_p95_sec" in payload
                assert "uptime_sec" in payload
                assert "inflight_requests" in payload


def test_ops_endpoints_require_auth_when_enabled() -> None:
    with _env_guard():
        with TemporaryDirectory() as td:
            secret = "ops-auth-secret"
            app_mod = _load_app(Path(td), auth_required="1", auth_secret=secret)
            with TestClient(app_mod.app) as client:
                assert client.get("/ops/metrics").status_code == 401
                headers = _auth_headers(secret=secret)

                metrics = client.get("/ops/metrics", headers=headers)
                slo = client.get("/ops/slo", headers=headers)
                assert metrics.status_code == 200
                assert slo.status_code == 200


def test_ops_endpoints_restrict_role_to_service_or_admin_when_auth_enabled() -> None:
    with _env_guard():
        with TemporaryDirectory() as td:
            secret = "ops-auth-secret"
            app_mod = _load_app(Path(td), auth_required="1", auth_secret=secret)
            with TestClient(app_mod.app) as client:
                teacher_headers = _auth_headers(actor_id="teacher_a", role="teacher", secret=secret)
                student_headers = _auth_headers(actor_id="student_a", role="student", secret=secret)
                service_headers = _auth_headers(actor_id="svc_ops", role="service", secret=secret)
                admin_headers = _auth_headers(actor_id="admin_a", role="admin", secret=secret)

                assert client.get("/ops/metrics", headers=teacher_headers).status_code == 403
                assert client.get("/ops/slo", headers=teacher_headers).status_code == 403
                assert client.get("/ops/metrics", headers=student_headers).status_code == 403
                assert client.get("/ops/slo", headers=student_headers).status_code == 403
                assert client.get("/ops/metrics", headers=service_headers).status_code == 200
                assert client.get("/ops/slo", headers=service_headers).status_code == 200
                assert client.get("/ops/metrics", headers=admin_headers).status_code == 200
                assert client.get("/ops/slo", headers=admin_headers).status_code == 200
