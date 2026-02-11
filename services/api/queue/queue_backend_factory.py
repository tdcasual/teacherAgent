from __future__ import annotations

import threading
from typing import Callable, Dict, Optional

from .queue_backend import QueueBackend, get_queue_backend


_QUEUE_BACKENDS: Dict[str, QueueBackend] = {}
_BACKEND_LOCK = threading.Lock()


def get_app_queue_backend(
    *,
    tenant_id: Optional[str],
    is_pytest: bool,
    inline_backend_factory: Callable[[], QueueBackend],
    get_backend: Callable[..., QueueBackend] = get_queue_backend,
) -> QueueBackend:
    key = str(tenant_id or "_default").strip() or "_default"
    with _BACKEND_LOCK:
        backend = _QUEUE_BACKENDS.get(key)
        if backend is None:
            backend = inline_backend_factory() if is_pytest else get_backend(tenant_id=tenant_id)
            _QUEUE_BACKENDS[key] = backend
    return backend


def reset_queue_backend() -> None:
    with _BACKEND_LOCK:
        _QUEUE_BACKENDS.clear()
