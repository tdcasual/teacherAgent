from __future__ import annotations

from typing import Callable, Optional

from services.api import settings
from services.api.queue.queue_backend import get_queue_backend


def start_runtime(
    *,
    backend=None,
    require_redis: Optional[Callable[[], None]] = None,
    is_pytest: Optional[bool] = None,
) -> None:
    if backend is None:
        backend = get_queue_backend(tenant_id=settings.tenant_id() or None)
    if is_pytest is None:
        is_pytest = settings.is_pytest()
    if not is_pytest:
        if require_redis is None:
            from services.api.workers import rq_tasks

            require_redis = rq_tasks.require_redis
        require_redis()
    backend.start()


def stop_runtime(*, backend=None) -> None:
    if backend is None:
        backend = get_queue_backend(tenant_id=settings.tenant_id() or None)
    backend.stop()
