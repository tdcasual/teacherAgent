from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional
import os

from .queue_backend import QueueBackend
from .queue_backend_factory import get_app_queue_backend
from .queue_runtime import start_runtime as _start_runtime
from .queue_runtime import stop_runtime as _stop_runtime


@dataclass
class RuntimeManagerDeps:
    tenant_id: Optional[str]
    is_pytest: bool
    validate_master_key_policy: Callable[..., None]
    inline_backend_factory: Callable[[], QueueBackend]
    get_backend: Callable[..., QueueBackend] = get_app_queue_backend
    start_runtime: Callable[..., None] = _start_runtime
    stop_runtime: Callable[..., None] = _stop_runtime
    getenv: Callable[[str, Optional[str]], str] = os.getenv


def start_tenant_runtime(*, deps: RuntimeManagerDeps) -> None:
    deps.validate_master_key_policy(getenv=deps.getenv)
    backend = deps.get_backend(
        tenant_id=deps.tenant_id,
        is_pytest=deps.is_pytest,
        inline_backend_factory=deps.inline_backend_factory,
    )
    deps.start_runtime(backend=backend, is_pytest=deps.is_pytest)


def stop_tenant_runtime(*, deps: RuntimeManagerDeps) -> None:
    backend = deps.get_backend(
        tenant_id=deps.tenant_id,
        is_pytest=deps.is_pytest,
        inline_backend_factory=deps.inline_backend_factory,
    )
    deps.stop_runtime(backend=backend)
