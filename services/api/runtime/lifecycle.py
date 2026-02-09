from __future__ import annotations

from contextlib import asynccontextmanager

from services.api.runtime import bootstrap


@asynccontextmanager
async def app_lifespan(_app):
    bootstrap.start_runtime()
    try:
        yield
    finally:
        bootstrap.stop_runtime()
