from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict


@dataclass(frozen=True)
class ChatStatusDeps:
    load_chat_job: Callable[[str], Dict[str, Any]]
    enqueue_chat_job: Callable[[str, str], Dict[str, Any]]
    resolve_chat_lane_id_from_job: Callable[[Dict[str, Any]], str]
    chat_job_lock: Any
    chat_lane_load_locked: Callable[[str], Dict[str, int]]
    chat_find_position_locked: Callable[[str, str], int]


def get_chat_status(job_id: str, *, deps: ChatStatusDeps) -> Dict[str, Any]:
    job = deps.load_chat_job(job_id)
    try:
        status = str(job.get("status") or "")
        lane_hint = str(job.get("lane_id") or "").strip()
        if status in {"queued", "processing"}:
            deps.enqueue_chat_job(job_id, lane_hint or deps.resolve_chat_lane_id_from_job(job))
    except Exception:
        pass
    lane_id = str(job.get("lane_id") or "").strip()
    if lane_id:
        with deps.chat_job_lock:
            lane_load = deps.chat_lane_load_locked(lane_id)
            lane_pos = deps.chat_find_position_locked(lane_id, job_id)
        job["lane_queue_position"] = lane_pos
        job["lane_queue_size"] = lane_load["queued"]
        job["lane_active"] = bool(lane_load["active"])
    return job
