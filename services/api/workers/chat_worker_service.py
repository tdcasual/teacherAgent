from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .lifecycle_state import compute_stop_result

_log = logging.getLogger(__name__)


CHAT_PENDING_RESCAN_INTERVAL_SEC = 15.0


def _noop_append_chat_event(_job_id: str, _event_type: str, _payload: Dict[str, Any]) -> Dict[str, Any]:
    return {}


def _thread_is_alive(thread: Any) -> bool:
    try:
        is_alive_method = getattr(thread, "is_alive", None)
        return bool(is_alive_method()) if callable(is_alive_method) else False
    except Exception:  # policy: allowed-broad-except
        _log.warning("operation failed", exc_info=True)
        return False


def _prune_dead_chat_worker_threads(threads: List[Any]) -> List[Any]:
    alive_threads = [thread for thread in list(threads) if _thread_is_alive(thread)]
    threads[:] = alive_threads
    return alive_threads

@dataclass(frozen=True)
class ChatWorkerDeps:
    chat_job_dir: Path
    chat_job_lock: Any
    chat_job_event: Any
    chat_worker_threads: List[Any]
    chat_worker_pool_size: int
    worker_started_get: Callable[[], bool]
    worker_started_set: Callable[[bool], None]
    load_chat_job: Callable[[str], Dict[str, Any]]
    write_chat_job: Callable[[str, Dict[str, Any]], Dict[str, Any]]
    resolve_chat_lane_id_from_job: Callable[[Dict[str, Any]], str]
    chat_enqueue_locked: Callable[[str, str], int]
    chat_lane_load_locked: Callable[[str], Dict[str, int]]
    chat_pick_next_locked: Callable[[], Tuple[str, str]]
    chat_mark_done_locked: Callable[[str, str], None]
    chat_has_pending_locked: Callable[[], bool]
    process_chat_job: Callable[[str], None]
    diag_log: Callable[[str, Dict[str, Any]], None]
    sleep: Callable[[float], None]
    thread_factory: Callable[..., Any]
    append_chat_event: Callable[[str, str, Dict[str, Any]], Dict[str, Any]] = _noop_append_chat_event
    stop_event: Any = field(default_factory=threading.Event)


def enqueue_chat_job(job_id: str, *, deps: ChatWorkerDeps, lane_id: Optional[str] = None) -> Dict[str, Any]:
    lane_final = lane_id or ""
    if not lane_final:
        try:
            job = deps.load_chat_job(job_id)
            lane_final = deps.resolve_chat_lane_id_from_job(job)
        except Exception:  # policy: allowed-broad-except
            _log.warning("lane resolution failed for chat job %s, using fallback", job_id, exc_info=True)
            lane_final = "unknown:session_main:req_unknown"
    with deps.chat_job_lock:
        lane_load_before = deps.chat_lane_load_locked(lane_final)
        lane_position = deps.chat_enqueue_locked(job_id, lane_final)
        lane_load = deps.chat_lane_load_locked(lane_final)
        enqueued = int(lane_load.get("queued", 0) or 0) > int(lane_load_before.get("queued", 0) or 0)
    deps.chat_job_event.set()
    return {
        "lane_id": lane_final,
        "lane_queue_position": lane_position,
        "lane_queue_size": lane_load["queued"],
        "lane_active": bool(lane_load["active"]),
        "enqueued": bool(enqueued),
    }


def scan_pending_chat_jobs(*, deps: ChatWorkerDeps) -> int:
    deps.chat_job_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for job_path in deps.chat_job_dir.glob("*/job.json"):
        try:
            data = json.loads(job_path.read_text(encoding="utf-8"))
        except Exception:  # policy: allowed-broad-except
            _log.warning("corrupt chat job.json at %s, skipping", job_path, exc_info=True)
            continue
        status = str(data.get("status") or "")
        job_id = str(data.get("job_id") or "")
        if status in {"queued", "processing"} and job_id:
            queue_info: Dict[str, Any]
            try:
                lane_id = str(deps.resolve_chat_lane_id_from_job(data) or "").strip() or None
                queue_info = enqueue_chat_job(job_id, lane_id=lane_id, deps=deps)
            except Exception:  # policy: allowed-broad-except
                _log.warning(
                    "lane resolution failed for pending chat job %s, deferring to enqueue fallback",
                    job_id,
                    exc_info=True,
                )
                queue_info = enqueue_chat_job(job_id, deps=deps)
            if bool((queue_info or {}).get("enqueued", True)):
                count += 1
    return count


def chat_job_worker_loop(*, deps: ChatWorkerDeps) -> None:
    next_rescan_at = 0.0
    while not deps.stop_event.is_set():
        now = time.monotonic()
        if now >= next_rescan_at:
            try:
                scan_pending_chat_jobs(deps=deps)
            except Exception as exc:  # policy: allowed-broad-except
                _log.warning("operation failed", exc_info=True)
                deps.diag_log("chat.pending_scan.failed", {"error": str(exc)[:200]})
            next_rescan_at = now + CHAT_PENDING_RESCAN_INTERVAL_SEC

        event_set = deps.chat_job_event.wait(timeout=0.1)
        if deps.stop_event.is_set():
            break
        if not event_set:
            continue
        job_id = ""
        lane_id = ""
        with deps.chat_job_lock:
            job_id, lane_id = deps.chat_pick_next_locked()
            if not job_id:
                deps.chat_job_event.clear()
        if not job_id:
            deps.sleep(0.05)
            continue
        try:
            deps.process_chat_job(job_id)
        except Exception as exc:  # pragma: no cover - covered by integration tests  # policy: allowed-broad-except
            _log.warning("operation failed", exc_info=True)
            detail = str(exc)[:200]
            deps.diag_log("chat.job.failed", {"job_id": job_id, "error": detail})
            deps.write_chat_job(
                job_id,
                {
                    "status": "failed",
                    "error": "chat_job_failed",
                    "error_detail": detail,
                },
            )
            try:
                deps.append_chat_event(
                    job_id,
                    "job.failed",
                    {
                        "status": "failed",
                        "error": "chat_job_failed",
                        "error_detail": detail,
                    },
                )
            except Exception:  # policy: allowed-broad-except
                _log.warning("failed to append job.failed event for chat job %s", job_id, exc_info=True)
        finally:
            with deps.chat_job_lock:
                deps.chat_mark_done_locked(job_id, lane_id)
                if deps.chat_has_pending_locked():
                    deps.chat_job_event.set()
                else:
                    deps.chat_job_event.clear()


def start_chat_worker(*, deps: ChatWorkerDeps) -> None:
    if deps.worker_started_get():
        # Preserve explicit "started" overrides (used by tests and controlled runtimes)
        # when no worker thread is being tracked.
        if not deps.chat_worker_threads:
            return
        alive_threads = _prune_dead_chat_worker_threads(deps.chat_worker_threads)
        if alive_threads:
            return
        deps.worker_started_set(False)
    deps.stop_event.clear()
    scan_pending_chat_jobs(deps=deps)
    for idx in range(max(1, int(deps.chat_worker_pool_size or 1))):
        thread = deps.thread_factory(
            target=lambda: chat_job_worker_loop(deps=deps),
            daemon=True,
            name=f"chat-worker-{idx + 1}",
        )
        thread.start()
        deps.chat_worker_threads.append(thread)
    deps.worker_started_set(True)


def stop_chat_worker(*, deps: ChatWorkerDeps, timeout_sec: float = 1.5) -> None:
    """
    Best-effort stop for in-process multi-tenant unloading.

    Threads exit when `stop_event` is set and are joined up to `timeout_sec` total.
    """
    try:
        deps.stop_event.set()
    except Exception:  # policy: allowed-broad-except
        _log.warning("operation failed", exc_info=True)
        return
    try:
        deps.chat_job_event.set()
    except Exception:  # policy: allowed-broad-except
        _log.warning("operation failed", exc_info=True)
        pass  # policy: allowed-broad-except

    effective_timeout = max(0.0, float(timeout_sec or 0.0))
    if str(os.getenv("PYTEST_CURRENT_TEST", "") or "").strip():
        effective_timeout = max(effective_timeout, 5.0)
    deadline = time.monotonic() + effective_timeout
    for thread in list(deps.chat_worker_threads):
        remaining = max(0.0, deadline - time.monotonic())
        try:
            thread.join(remaining)
        except Exception:  # policy: allowed-broad-except
            _log.warning("operation failed", exc_info=True)
            pass  # policy: allowed-broad-except
    alive_threads = _prune_dead_chat_worker_threads(deps.chat_worker_threads)
    stop_state = compute_stop_result(thread_alive=bool(alive_threads))
    deps.worker_started_set(stop_state.worker_started)
