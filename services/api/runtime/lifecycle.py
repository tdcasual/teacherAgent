from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from services.api.auth_registry_service import build_auth_registry_store
from services.api.auth_secret_bootstrap import ensure_auth_token_secret
from services.api.auth_service import validate_auth_secret_policy
from services.api.container import build_app_container
from services.api.logging_config import configure_logging
from services.api.runtime import bootstrap

_log = logging.getLogger(__name__)


@asynccontextmanager
async def app_lifespan(_app):
    state = getattr(_app, "state", None)
    if state is not None and not hasattr(state, "container"):
        core = getattr(state, "core", None)
        state.container = build_app_container(core=core)
    ensure_auth_token_secret()
    validate_auth_secret_policy()
    configure_logging()
    try:
        core = getattr(state, "core", None) if state is not None else None
        data_dir = getattr(core, "DATA_DIR", None)
        if data_dir is not None:
            result = build_auth_registry_store(data_dir=data_dir).bootstrap_admin()
            if result.get("generated_password") and result.get("bootstrap_file"):
                _log.warning(
                    "Admin bootstrap created; read credentials from %s",
                    result.get("bootstrap_file"),
                )
    except Exception:
        _log.error("Admin bootstrap failed", exc_info=True)
    try:
        bootstrap.start_runtime()
    except Exception:
        _log.error("Runtime startup failed; running in degraded mode", exc_info=True)
    try:
        yield
    finally:
        try:
            bootstrap.stop_runtime()
        except Exception:
            _log.error("Runtime shutdown error", exc_info=True)
