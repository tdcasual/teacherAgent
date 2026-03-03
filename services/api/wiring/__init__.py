"""Wiring package — deps builder modules extracted from app_core."""
from __future__ import annotations

import contextvars
from typing import Any

# Context variable holding the current app_core module for the active request.
# Set by app.py middleware so tenant-specific core modules are used correctly.
CURRENT_CORE: contextvars.ContextVar = contextvars.ContextVar("CURRENT_CORE", default=None)
_DEFAULT_CORE: Any = None


def set_default_core(core: Any) -> None:
    global _DEFAULT_CORE
    _DEFAULT_CORE = core


def get_app_core(core: Any | None = None) -> Any:
    """Return explicit core first, then request core, then app default core."""
    if core is not None:
        return core
    ctx_core = CURRENT_CORE.get(None)
    if ctx_core is not None:
        return ctx_core
    if _DEFAULT_CORE is not None:
        return _DEFAULT_CORE
    return None
