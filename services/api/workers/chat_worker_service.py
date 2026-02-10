from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


CHAT_PENDING_RESCAN_INTERVAL_SEC = 15.0

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
    stop_event: Any = field(default_factory=threading.Event)


def enqueue_chat_job(job_id: str, *, deps: ChatWorkerDeps, lane_id: Optional[str] = None) -> Dict[str, Any]:
    lane_final = lane_id or ""
    if not lane_final:
        try:
            job = deps.load_chat_job(job_id)
            lane_final = deps.resolve_chat_lane_id_from_job(job)
        except Exception:
            lane_final = "unknown:session_main:req_unknown"
    with deps.chat_job_lock:
        lane_position = deps.chat_enqueue_locked(job_id, lane_final)
        lane_load = deps.chat_lane_load_locked(lane_final)
    deps.chat_job_event.set()
    return {
        "lane_id": lane_final,
        "lane_queue_position": lane_position,
        "lane_queue_size": lane_load["queued"],
        "lane_active": bool(lane_load["active"]),
    }


def scan_pending_chat_jobs(*, deps: ChatWorkerDeps) -> None:
    deps.chat_job_dir.mkdir(parents=True, exist_ok=True)
    for job_path in deps.chat_job_dir.glob("*/job.json"):
        try:
            data = json.loads(job_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        status = str(data.get("status") or "")
        job_id = str(data.get("job_id") or "")
        if status in {"queued", "processing"} and job_id:
            enqueue_chat_job(job_id, lane_id=deps.resolve_chat_lane_id_from_job(data), deps=deps)


def chat_job_worker_loop(*, deps: ChatWorkerDeps) -> None:
    next_rescan_at = 0.0
    while not deps.stop_event.is_set():
        now = time.monotonic()
        if now >= next_rescan_at:
            try:
                scan_pending_chat_jobs(deps=deps)
            except Exception as exc:
                deps.diag_log("chat.pending_scan.failed", {"error": str(exc)[:200]})
            next_rescan_at = now + CHAT_PENDING_RESCAN_INTERVAL_SEC

        deps.chat_job_event.wait(timeout=0.1)
        if deps.stop_event.is_set():
            break
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
        except Exception as exc:  # pragma: no cover - covered by integration tests
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
        finally:
            with deps.chat_job_lock:
                deps.chat_mark_done_locked(job_id, lane_id)
                if deps.chat_has_pending_locked():
                    deps.chat_job_event.set()
                else:
                    deps.chat_job_event.clear()


def start_chat_worker(*, deps: ChatWorkerDeps) -> None:
    if deps.worker_started_get():
        return
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
    except Exception:
        return
    try:
        deps.chat_job_event.set()
    except Exception:
        pass

    deadline = time.monotonic() + max(0.0, float(timeout_sec or 0.0))
    for thread in list(deps.chat_worker_threads):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        try:
            thread.join(remaining)
        except Exception:
            pass
    deps.worker_started_set(False)
