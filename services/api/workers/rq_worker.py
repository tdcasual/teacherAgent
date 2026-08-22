from __future__ import annotations

import os
import threading
import time
from pathlib import Path

from rq import Worker

from services.api.redis_clients import get_redis_client
from services.api.workers.rq_tasks import (
    scan_pending_chat_jobs,
    scan_pending_exam_jobs,
    scan_pending_upload_jobs,
)

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


def _heartbeat_loop(path: str, interval_sec: float) -> None:
    while True:
        time.sleep(interval_sec)
        try:
            _refresh_heartbeat(path)
        except OSError:
            pass


def _start_heartbeat(path: str, interval_sec: float = _HEARTBEAT_INTERVAL_SEC) -> threading.Thread:
    _write_heartbeat(path)
    thread = threading.Thread(
        target=_heartbeat_loop,
        args=(path, interval_sec),
        name="rq-heartbeat",
        daemon=True,
    )
    thread.start()
    return thread


def main() -> None:
    os.environ.setdefault("JOB_QUEUE_BACKEND", "rq")
    queue_name = str(os.getenv("RQ_QUEUE_NAME", "default") or "default")
    tenant_id = str(os.getenv("TENANT_ID", "") or "").strip() or None

    _start_heartbeat(_heartbeat_path())

    if _truthy(os.getenv("RQ_SCAN_PENDING_ON_START", "")):
        scan_pending_upload_jobs(tenant_id=tenant_id)
        scan_pending_exam_jobs(tenant_id=tenant_id)
        scan_pending_chat_jobs(tenant_id=tenant_id)

    redis = get_redis_client(os.getenv("REDIS_URL", ""), decode_responses=False)
    worker = Worker([queue_name], connection=redis)
    worker.work()


if __name__ == "__main__":
    main()
