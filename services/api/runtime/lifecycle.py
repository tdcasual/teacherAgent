from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from services.api.logging_config import configure_logging
from services.api.runtime import bootstrap

_log = logging.getLogger(__name__)


@asynccontextmanager
async def app_lifespan(_app):
    configure_logging()
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
