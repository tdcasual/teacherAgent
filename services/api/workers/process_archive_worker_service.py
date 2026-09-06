from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Callable, Deque, Dict, List

from .lifecycle_state import compute_stop_result

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProcessArchiveWorkerDeps:
    update_queue: Deque[Dict[str, Any]]
    update_lock: Any
    update_event: Any
    stop_event: Any
    worker_started_get: Callable[[], bool]
    worker_started_set: Callable[[bool], None]
    worker_thread_get: Callable[[], Any]
    worker_thread_set: Callable[[Any], None]
    queue_max: int
    freeze_process_archive: Callable[[Dict[str, Any]], Dict[str, Any]]
    diag_log: Callable[[str, Dict[str, Any]], None]
    sleep: Callable[[float], None]
    thread_factory: Callable[..., Any]
    rq_enabled: Callable[[], bool]
    monotonic: Callable[[], float]


def _thread_is_alive(thread: Any) -> bool:
    if thread is None:
        return False
    try:
        is_alive_method = getattr(thread, "is_alive", None)
        return bool(is_alive_method()) if callable(is_alive_method) else False
    except Exception:  # policy: allowed-broad-except
        _log.debug("operation failed", exc_info=True)
        return False


def enqueue_process_archive_inline(payload: Dict[str, Any], *, deps: ProcessArchiveWorkerDeps) -> None:
    with deps.update_lock:
        if len(deps.update_queue) >= int(deps.queue_max or 0):
            deps.diag_log(
                "process_archive.queue_full",
                {
                    "size": len(deps.update_queue),
                    "assignment_id": str((payload or {}).get("assignment_id") or ""),
                    "student_id": str((payload or {}).get("student_id") or ""),
                },
            )
            return
        deps.update_queue.append(payload)
        deps.update_event.set()


def _drain_process_archive_batch(*, deps: ProcessArchiveWorkerDeps) -> List[Dict[str, Any]]:
    batch: List[Dict[str, Any]] = []
    with deps.update_lock:
        while deps.update_queue:
            batch.append(deps.update_queue.popleft())
        deps.update_event.clear()
    return batch


def run_process_archive_job(payload: Dict[str, Any], *, deps: ProcessArchiveWorkerDeps) -> None:
    try:
        deps.freeze_process_archive(payload if isinstance(payload, dict) else {})
    except Exception as exc:  # policy: allowed-broad-except
        _log.debug("process archive worker execution failed", exc_info=True)
        item = payload if isinstance(payload, dict) else {}
        deps.diag_log(
            "process_archive.partial",
            {
                "assignment_id": str(item.get("assignment_id") or ""),
                "student_id": str(item.get("student_id") or ""),
                "error": str(exc)[:200],
            },
        )


def process_archive_worker_loop(*, deps: ProcessArchiveWorkerDeps) -> None:
    while not deps.stop_event.is_set():
        deps.update_event.wait(timeout=0.1)
        if deps.stop_event.is_set():
            break
        batch = _drain_process_archive_batch(deps=deps)
        if not batch:
            deps.sleep(0.05)
            continue
        for item in batch:
            run_process_archive_job(item, deps=deps)


def start_process_archive_worker(*, deps: ProcessArchiveWorkerDeps) -> None:
    if deps.rq_enabled():
        return
    if deps.worker_started_get():
        if _thread_is_alive(deps.worker_thread_get()):
            return
        deps.worker_thread_set(None)
        deps.worker_started_set(False)
    deps.stop_event.clear()
    thread = deps.thread_factory(
        target=lambda: process_archive_worker_loop(deps=deps),
        daemon=True,
        name="process-archive-worker",
    )
    thread.start()
    deps.worker_thread_set(thread)
    deps.worker_started_set(True)


def stop_process_archive_worker(*, deps: ProcessArchiveWorkerDeps, timeout_sec: float = 1.5) -> None:
    if deps.rq_enabled():
        return
    deps.stop_event.set()
    deps.update_event.set()
    thread = deps.worker_thread_get()
    effective_timeout = max(0.0, float(timeout_sec or 0.0))
    if str(os.getenv("PYTEST_CURRENT_TEST", "") or "").strip():
        effective_timeout = max(effective_timeout, 5.0)
    if thread is not None:
        try:
            thread.join(effective_timeout)
        except Exception:  # policy: allowed-broad-except
            _log.debug("process archive worker thread join failed", exc_info=True)
    stop_state = compute_stop_result(thread_alive=_thread_is_alive(thread))
    next_thread = None if stop_state.clear_thread_ref else thread
    deps.worker_thread_set(next_thread)
    deps.worker_started_set(stop_state.worker_started)
