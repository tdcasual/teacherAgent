from __future__ import annotations

from typing import Callable, Optional

from .queue_backend import QueueBackend, get_queue_backend


_QUEUE_BACKEND: Optional[QueueBackend] = None


def get_app_queue_backend(
    *,
    tenant_id: Optional[str],
    is_pytest: bool,
    inline_backend_factory: Callable[[], QueueBackend],
    get_backend: Callable[..., QueueBackend] = get_queue_backend,
) -> QueueBackend:
    global _QUEUE_BACKEND
    if _QUEUE_BACKEND is None:
        _QUEUE_BACKEND = inline_backend_factory() if is_pytest else get_backend(tenant_id=tenant_id)
    return _QUEUE_BACKEND


def reset_queue_backend() -> None:
    global _QUEUE_BACKEND
    _QUEUE_BACKEND = None
