from __future__ import annotations

import json
import logging
from typing import Dict, Optional, Tuple

import redis

_log = logging.getLogger(__name__)


class ChatRedisLaneStore:
    def __init__(
        self,
        redis_client: redis.Redis,
        *,
        tenant_id: str,
        claim_ttl_sec: int,
        debounce_ms: int,
    ):
        self.redis = redis_client
        safe_tenant = str(tenant_id or "default").strip() or "default"
        self.prefix = f"chat:{safe_tenant}"
        self.claim_ttl_sec = max(0, int(claim_ttl_sec or 0))
        self.debounce_ms = max(0, int(debounce_ms or 0))

        self._enqueue_script = self.redis.register_script(
            """
            local queue_key = KEYS[1]
            local active_key = KEYS[2]
            local queued_key = KEYS[3]
            local job_id = ARGV[1]
            local ttl = tonumber(ARGV[2]) or 0

            if redis.call('SISMEMBER', queued_key, job_id) == 1 then
                local pos = redis.call('LPOS', queue_key, job_id)
                if not pos then
                    pos = 0
                else
                    pos = pos + 1
                end
                local qlen = redis.call('LLEN', queue_key)
                local active = redis.call('EXISTS', active_key)
                return {pos, qlen, active, 0}
            end

            local active = redis.call('EXISTS', active_key)
            if active == 1 then
                local qlen = redis.call('RPUSH', queue_key, job_id)
                redis.call('SADD', queued_key, job_id)
                return {qlen, qlen, 1, 0}
            end

            redis.call('SADD', queued_key, job_id)
            if ttl > 0 then
                redis.call('SET', active_key, job_id, 'EX', ttl)
            else
                redis.call('SET', active_key, job_id)
            end
            local qlen = redis.call('LLEN', queue_key)
            return {0, qlen, 1, 1}
            """
        )

        self._finish_script = self.redis.register_script(
            """
            local queue_key = KEYS[1]
            local active_key = KEYS[2]
            local queued_key = KEYS[3]
            local job_id = ARGV[1]
            local ttl = tonumber(ARGV[2]) or 0

            redis.call('SREM', queued_key, job_id)

            local active = redis.call('GET', active_key)
            if active and active ~= job_id then
                return ''
            end
            if active == job_id then
                redis.call('DEL', active_key)
            end

            local next_job = redis.call('LPOP', queue_key)
            if next_job then
                if ttl > 0 then
                    redis.call('SET', active_key, next_job, 'EX', ttl)
                else
                    redis.call('SET', active_key, next_job)
                end
                return next_job
            end
            return ''
            """
        )

    def _queue_key(self, lane_id: str) -> str:
        return f"{self.prefix}:lane:{lane_id}:queue"

    def _active_key(self, lane_id: str) -> str:
        return f"{self.prefix}:lane:{lane_id}:active"

    def _recent_key(self, lane_id: str) -> str:
        return f"{self.prefix}:lane:{lane_id}:recent"

    def _queued_key(self) -> str:
        return f"{self.prefix}:queued"

    def lane_load(self, lane_id: str) -> Dict[str, int]:
        queue_key = self._queue_key(lane_id)
        active_key = self._active_key(lane_id)
        queued = int(self.redis.llen(queue_key) or 0)
        active = 1 if self.redis.exists(active_key) else 0
        return {"queued": queued, "active": active, "total": queued + active}

    def find_position(self, lane_id: str, job_id: str) -> int:
        queue_key = self._queue_key(lane_id)
        try:
            pos = self.redis.lpos(queue_key, job_id)
        except Exception:
            _log.warning("Redis LPOS failed for lane=%s job=%s", lane_id, job_id, exc_info=True)
            pos = None
        if pos is None:
            return 0
        try:
            return int(pos) + 1
        except Exception:
            _log.debug("int conversion failed for lpos result pos=%s", pos)
            return 0

    def enqueue(self, job_id: str, lane_id: str) -> Tuple[Dict[str, int], bool]:
        queue_key = self._queue_key(lane_id)
        active_key = self._active_key(lane_id)
        queued_key = self._queued_key()
        result = self._enqueue_script(
            keys=[queue_key, active_key, queued_key],
            args=[job_id, str(self.claim_ttl_sec)],
        )
        pos, queued, active, dispatch = (int(result[0]), int(result[1]), int(result[2]), int(result[3]))
        return {"lane_queue_position": pos, "lane_queue_size": queued, "lane_active": bool(active)}, bool(dispatch)

    def finish(self, job_id: str, lane_id: str) -> Optional[str]:
        queue_key = self._queue_key(lane_id)
        active_key = self._active_key(lane_id)
        queued_key = self._queued_key()
        result = self._finish_script(
            keys=[queue_key, active_key, queued_key],
            args=[job_id, str(self.claim_ttl_sec)],
        )
        if not result:
            return None
        return str(result)

    def register_recent(self, lane_id: str, fingerprint: str, job_id: str) -> None:
        if self.debounce_ms <= 0:
            return
        key = self._recent_key(lane_id)
        payload = json.dumps({"fp": fingerprint, "job_id": job_id}, ensure_ascii=False)
        try:
            self.redis.set(key, payload, px=self.debounce_ms)
        except Exception:
            _log.warning("Redis SET failed for recent key lane=%s", lane_id, exc_info=True)
            pass

    def recent_job(self, lane_id: str, fingerprint: str) -> Optional[str]:
        if self.debounce_ms <= 0:
            return None
        key = self._recent_key(lane_id)
        try:
            raw = self.redis.get(key)
        except Exception:
            _log.warning("Redis GET failed for recent key lane=%s", lane_id, exc_info=True)
            return None
        if not raw:
            return None
        try:
            data = json.loads(raw)
        except Exception:
            _log.warning("JSON parse failed for recent key lane=%s", lane_id, exc_info=True)
            return None
        if not isinstance(data, dict):
            return None
        if str(data.get("fp") or "") != fingerprint:
            return None
        job_id = str(data.get("job_id") or "").strip()
        return job_id or None


RedisLaneStore = ChatRedisLaneStore
