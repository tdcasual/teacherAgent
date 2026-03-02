from __future__ import annotations

import os
import threading
from typing import Callable, Dict, Optional, Tuple

from services.api import settings

from .queue_backend import QueueBackend, get_queue_backend

_BackendKey = Tuple[str, ...]

_QUEUE_BACKENDS: Dict[_BackendKey, QueueBackend] = {}
_BACKEND_LOCK = threading.Lock()


def _is_inline_mode(mode: str) -> bool:
    normalized = str(mode or "").strip().lower()
    return normalized in {"inline", "inproc", "in-process", "in_process"}


def _normalize_pytest_case(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.endswith(")") and " (" in text:
        prefix, suffix = text.rsplit(" (", 1)
        phase = str(suffix[:-1]).strip().lower()
        if phase in {"setup", "call", "teardown"}:
            return prefix.strip()
    return text


def _build_backend_cache_key(
    *,
    tenant_id: Optional[str],
    is_pytest: bool,
    queue_mode: str,
) -> _BackendKey:
    tenant_key = str(tenant_id or "_default").strip() or "_default"
    if not is_pytest:
        mode_key = str(queue_mode or "").strip().lower() or "_default"
        return ("tenant", tenant_key, mode_key)

    data_dir = str(os.getenv("DATA_DIR", "") or "").strip()
    uploads_dir = str(os.getenv("UPLOADS_DIR", "") or "").strip()
    pytest_case = _normalize_pytest_case(os.getenv("PYTEST_CURRENT_TEST", ""))
    return ("pytest", tenant_key, data_dir, uploads_dir, pytest_case)


def get_app_queue_backend(
    *,
    tenant_id: Optional[str],
    is_pytest: bool,
    inline_backend_factory: Callable[[], QueueBackend],
    get_backend: Callable[..., QueueBackend] = get_queue_backend,
) -> QueueBackend:
    queue_mode = settings.job_queue_backend()
    key = _build_backend_cache_key(
        tenant_id=tenant_id,
        is_pytest=is_pytest,
        queue_mode=queue_mode,
    )
    with _BACKEND_LOCK:
        backend = _QUEUE_BACKENDS.get(key)
        if backend is None:
            if is_pytest or _is_inline_mode(queue_mode):
                backend = inline_backend_factory()
            else:
                backend = get_backend(tenant_id=tenant_id)
            _QUEUE_BACKENDS[key] = backend
    return backend


def reset_queue_backend() -> None:
    with _BACKEND_LOCK:
        _QUEUE_BACKENDS.clear()
