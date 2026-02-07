from __future__ import annotations

from collections import deque
from typing import Deque, Dict, Optional, Set, Tuple


def chat_lane_load(
    lanes: Dict[str, Deque[str]],
    active_lanes: Set[str],
    lane_id: str,
) -> Dict[str, int]:
    queue = lanes.get(lane_id)
    queued = len(queue) if queue else 0
    active = 1 if lane_id in active_lanes else 0
    return {"queued": queued, "active": active, "total": queued + active}


def chat_find_position(
    lanes: Dict[str, Deque[str]],
    lane_id: str,
    job_id: str,
) -> int:
    queue = lanes.get(lane_id)
    if not queue:
        return 0
    for index, queued_job_id in enumerate(queue, start=1):
        if queued_job_id == job_id:
            return index
    return 0


def chat_enqueue(
    lanes: Dict[str, Deque[str]],
    queued_jobs: Set[str],
    job_to_lane: Dict[str, str],
    job_id: str,
    lane_id: str,
) -> int:
    if job_id in queued_jobs:
        return chat_find_position(lanes, lane_id, job_id)
    queue = lanes.setdefault(lane_id, deque())
    queue.append(job_id)
    queued_jobs.add(job_id)
    job_to_lane[job_id] = lane_id
    return len(queue)


def chat_has_pending(lanes: Dict[str, Deque[str]]) -> bool:
    return any(len(queue) > 0 for queue in lanes.values())


def chat_pick_next(
    lanes: Dict[str, Deque[str]],
    active_lanes: Set[str],
    queued_jobs: Set[str],
    job_to_lane: Dict[str, str],
    lane_cursor: int,
) -> Tuple[str, str, int]:
    available_lanes = [lane_id for lane_id, queue in lanes.items() if queue]
    if not available_lanes:
        return "", "", lane_cursor
    total = len(available_lanes)
    start = lane_cursor % total
    for offset in range(total):
        lane_id = available_lanes[(start + offset) % total]
        if lane_id in active_lanes:
            continue
        queue = lanes.get(lane_id)
        if not queue:
            continue
        job_id = queue.popleft()
        queued_jobs.discard(job_id)
        active_lanes.add(lane_id)
        job_to_lane[job_id] = lane_id
        next_cursor = (start + offset + 1) % max(1, total)
        return job_id, lane_id, next_cursor
    return "", "", lane_cursor


def chat_mark_done(
    lanes: Dict[str, Deque[str]],
    active_lanes: Set[str],
    job_to_lane: Dict[str, str],
    job_id: str,
    lane_id: str,
) -> None:
    active_lanes.discard(lane_id)
    job_to_lane.pop(job_id, None)
    queue = lanes.get(lane_id)
    if queue is not None and len(queue) == 0:
        lanes.pop(lane_id, None)


def chat_register_recent(
    lane_recent: Dict[str, Tuple[float, str, str]],
    lane_id: str,
    fingerprint: str,
    job_id: str,
    *,
    now_ts: float,
) -> None:
    lane_recent[lane_id] = (now_ts, fingerprint, job_id)


def chat_recent_job(
    lane_recent: Dict[str, Tuple[float, str, str]],
    lane_id: str,
    fingerprint: str,
    *,
    debounce_ms: int,
    now_ts: float,
) -> Optional[str]:
    if debounce_ms <= 0:
        return None
    info = lane_recent.get(lane_id)
    if not info:
        return None
    ts, fp, job_id = info
    if fp != fingerprint:
        return None
    if (now_ts - ts) * 1000 > debounce_ms:
        return None
    return job_id
