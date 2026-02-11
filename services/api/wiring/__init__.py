"""Wiring package — deps builder modules extracted from app_core."""
from __future__ import annotations

import contextvars
import logging
import os

# Context variable holding the current app_core module for the active request.
# Set by app.py middleware so tenant-specific core modules are used correctly.
CURRENT_CORE: contextvars.ContextVar = contextvars.ContextVar("CURRENT_CORE", default=None)

_log = logging.getLogger(__name__)


def get_app_core():
    """Return the active app_core module (tenant-aware)."""
    _ctx = CURRENT_CORE.get(None)
    if _ctx is not None:
        return _ctx
    if os.getenv("MULTI_TENANT_ENABLED"):
        raise RuntimeError("CURRENT_CORE not set — tenant context is required in multi-tenant mode")
    _log.warning("CURRENT_CORE not set, falling back to default tenant module")
    from services.api import app_core as _mod
    return _mod
