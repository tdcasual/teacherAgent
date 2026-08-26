from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Optional

from rq import Worker

from services.api.redis_clients import get_redis_client
from services.api.workers.rq_tasks import (
    scan_pending_chat_jobs,
    scan_pending_exam_jobs,
    scan_pending_upload_jobs,
)

_log = logging.getLogger(__name__)

_HEARTBEAT_INTERVAL_SEC = 10
_DEFAULT_HEARTBEAT_PATH = "/tmp/rq_worker_heartbeat"


def _truthy(value: str) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _heartbeat_path() -> str:
    return str(os.getenv("RQ_HEARTBEAT_PATH", _DEFAULT_HEARTBEAT_PATH) or _DEFAULT_HEARTBEAT_PATH)


def _write_heartbeat(path: str) -> None:
    heartbeat = Path(path)
    if heartbeat.parent.as_posix() not in {"", "."}:
        heartbeat.parent.mkdir(parents=True, exist_ok=True)
    heartbeat.touch()


def _refresh_heartbeat(path: str) -> None:
    try:
        os.utime(path, None)
    except OSError:
        _write_heartbeat(path)


class FileHeartbeatWorker(Worker):
    """RQ forks work-horses; a pre-fork daemon thread can deadlock after os.fork()."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("job_monitoring_interval", _HEARTBEAT_INTERVAL_SEC)
        super().__init__(*args, **kwargs)

    @property
    def dequeue_timeout(self) -> int:
        # Idle BLPOP must return inside the compose mtime window (<30s).
        return min(_HEARTBEAT_INTERVAL_SEC, max(1, int(self.worker_ttl) - 15))

    def heartbeat(self, timeout: Optional[int] = None, pipeline: Any = None) -> None:
        try:
            _refresh_heartbeat(_heartbeat_path())
        except OSError as exc:
            _log.warning("rq heartbeat file refresh failed: %s", exc)
        super().heartbeat(timeout=timeout, pipeline=pipeline)


def main() -> None:
    os.environ.setdefault("JOB_QUEUE_BACKEND", "rq")
    queue_name = str(os.getenv("RQ_QUEUE_NAME", "default") or "default")
    tenant_id = str(os.getenv("TENANT_ID", "") or "").strip() or None

    _write_heartbeat(_heartbeat_path())

    if _truthy(os.getenv("RQ_SCAN_PENDING_ON_START", "")):
        scan_pending_upload_jobs(tenant_id=tenant_id)
        scan_pending_exam_jobs(tenant_id=tenant_id)
        scan_pending_chat_jobs(tenant_id=tenant_id)

    redis = get_redis_client(os.getenv("REDIS_URL", ""), decode_responses=False)
    worker = FileHeartbeatWorker([queue_name], connection=redis)
    # Retry(interval=...) parks jobs in ScheduledJobRegistry until the scheduler drains them.
    worker.work(with_scheduler=True)


if __name__ == "__main__":
    main()
