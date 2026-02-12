from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Deque, Dict, List
import logging
_log = logging.getLogger(__name__)



@dataclass(frozen=True)
class ProfileUpdateWorkerDeps:
    update_queue: Deque[Dict[str, Any]]
    update_lock: Any
    update_event: Any
    stop_event: Any
    worker_started_get: Callable[[], bool]
    worker_started_set: Callable[[bool], None]
    worker_thread_get: Callable[[], Any]
    worker_thread_set: Callable[[Any], None]
    queue_max: int
    student_profile_update: Callable[[Dict[str, Any]], Dict[str, Any]]
    diag_log: Callable[[str, Dict[str, Any]], None]
    sleep: Callable[[float], None]
    thread_factory: Callable[..., Any]
    rq_enabled: Callable[[], bool]
    monotonic: Callable[[], float]


def enqueue_profile_update_inline(payload: Dict[str, Any], *, deps: ProfileUpdateWorkerDeps) -> None:
    with deps.update_lock:
        if len(deps.update_queue) >= int(deps.queue_max or 0):
            deps.diag_log("profile_update.queue_full", {"size": len(deps.update_queue)})
            return
        deps.update_queue.append(payload)
        deps.update_event.set()


def profile_update_worker_loop(*, deps: ProfileUpdateWorkerDeps) -> None:
    while not deps.stop_event.is_set():
        deps.update_event.wait(timeout=0.1)
        if deps.stop_event.is_set():
            break
        batch: List[Dict[str, Any]] = []
        with deps.update_lock:
            while deps.update_queue:
                batch.append(deps.update_queue.popleft())
            deps.update_event.clear()
        if not batch:
            deps.sleep(0.05)
            continue

        merged: Dict[str, Dict[str, Any]] = {}
        for item in batch:
            student_id = str(item.get("student_id") or "").strip()
            if not student_id:
                continue
            cur = merged.get(student_id) or {"student_id": student_id, "interaction_note": ""}
            note = str(item.get("interaction_note") or "").strip()
            if note:
                if cur.get("interaction_note"):
                    cur["interaction_note"] = str(cur["interaction_note"]) + "\n" + note
                else:
                    cur["interaction_note"] = note
            merged[student_id] = cur

        for student_id, payload in merged.items():
            try:
                t0 = deps.monotonic()
                deps.student_profile_update(payload)
                deps.diag_log(
                    "profile_update.async.done",
                    {"student_id": student_id, "duration_ms": int((deps.monotonic() - t0) * 1000)},
                )
            except Exception as exc:
                _log.debug("numeric conversion failed", exc_info=True)
                deps.diag_log("profile_update.async.failed", {"student_id": student_id, "error": str(exc)[:200]})


def start_profile_update_worker(*, deps: ProfileUpdateWorkerDeps) -> None:
    if deps.rq_enabled():
        return
    if deps.worker_started_get():
        return
    deps.stop_event.clear()
    thread = deps.thread_factory(target=lambda: profile_update_worker_loop(deps=deps), daemon=True, name="profile-update-worker")
    thread.start()
    deps.worker_thread_set(thread)
    deps.worker_started_set(True)


def stop_profile_update_worker(*, deps: ProfileUpdateWorkerDeps, timeout_sec: float = 1.5) -> None:
    if deps.rq_enabled():
        return
    deps.stop_event.set()
    deps.update_event.set()
    thread = deps.worker_thread_get()
    if thread is not None:
        try:
            thread.join(max(0.0, float(timeout_sec or 0.0)))
        except Exception:
            _log.debug("numeric conversion failed", exc_info=True)
            pass
    deps.worker_thread_set(None)
    deps.worker_started_set(False)
