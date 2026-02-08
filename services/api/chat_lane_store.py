from __future__ import annotations

import time
from collections import deque
from typing import Dict, Optional, Protocol, Tuple


class ChatLaneStore(Protocol):
    def lane_load(self, lane_id: str) -> Dict[str, int]: ...
    def find_position(self, lane_id: str, job_id: str) -> int: ...
    def enqueue(self, job_id: str, lane_id: str) -> Tuple[Dict[str, int], bool]: ...
    def finish(self, job_id: str, lane_id: str) -> Optional[str]: ...
    def register_recent(self, lane_id: str, fingerprint: str, job_id: str) -> None: ...
    def recent_job(self, lane_id: str, fingerprint: str) -> Optional[str]: ...


class MemoryLaneStore:
    def __init__(self, *, debounce_ms: int = 0, claim_ttl_sec: int = 0):
        self._lanes: Dict[str, deque[str]] = {}
        self._active: Dict[str, str] = {}
        self._queued: set[str] = set()
        self._recent: Dict[str, Tuple[float, str, str]] = {}
        self._debounce_ms = max(0, int(debounce_ms or 0))
        self._claim_ttl_sec = max(0, int(claim_ttl_sec or 0))

    def lane_load(self, lane_id: str) -> Dict[str, int]:
        queued = len(self._lanes.get(lane_id) or [])
        active = 1 if lane_id in self._active else 0
        return {"queued": queued, "active": active, "total": queued + active}

    def find_position(self, lane_id: str, job_id: str) -> int:
        q = self._lanes.get(lane_id)
        if not q:
            return 0
        for i, jid in enumerate(q, start=1):
            if jid == job_id:
                return i
        return 0

    def enqueue(self, job_id: str, lane_id: str) -> Tuple[Dict[str, int], bool]:
        if job_id in self._queued:
            info = self.lane_load(lane_id)
            return {
                "lane_queue_position": self.find_position(lane_id, job_id),
                "lane_queue_size": info["queued"],
                "lane_active": bool(info["active"]),
            }, False

        if lane_id in self._active:
            q = self._lanes.setdefault(lane_id, deque())
            q.append(job_id)
            self._queued.add(job_id)
            info = self.lane_load(lane_id)
            return {
                "lane_queue_position": len(q),
                "lane_queue_size": info["queued"],
                "lane_active": True,
            }, False

        self._active[lane_id] = job_id
        info = self.lane_load(lane_id)
        return {
            "lane_queue_position": 0,
            "lane_queue_size": info["queued"],
            "lane_active": True,
        }, True

    def finish(self, job_id: str, lane_id: str) -> Optional[str]:
        self._queued.discard(job_id)
        current = self._active.get(lane_id)
        if current and current != job_id:
            return None
        if current == job_id:
            self._active.pop(lane_id, None)

        q = self._lanes.get(lane_id)
        if not q:
            return None
        next_job = q.popleft()
        if not q:
            self._lanes.pop(lane_id, None)
        self._active[lane_id] = next_job
        return next_job

    def register_recent(self, lane_id: str, fingerprint: str, job_id: str) -> None:
        if self._debounce_ms <= 0:
            return
        self._recent[lane_id] = (time.time(), fingerprint, job_id)

    def recent_job(self, lane_id: str, fingerprint: str) -> Optional[str]:
        if self._debounce_ms <= 0:
            return None
        info = self._recent.get(lane_id)
        if not info:
            return None
        ts, fp, job_id = info
        if fp != fingerprint:
            return None
        if (time.time() - ts) * 1000 > self._debounce_ms:
            return None
        return job_id
