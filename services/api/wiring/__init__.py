"""Wiring package — deps builder modules extracted from app_core."""
from __future__ import annotations

import contextvars

# Context variable holding the current app_core module for the active request.
# Set by app.py middleware so tenant-specific core modules are used correctly.
CURRENT_CORE: contextvars.ContextVar = contextvars.ContextVar("CURRENT_CORE", default=None)


def get_app_core():
    """Return the active app_core module (tenant-aware)."""
    _ctx = CURRENT_CORE.get(None)
    if _ctx is not None:
        return _ctx
    from services.api import app_core as _mod
    return _mod
