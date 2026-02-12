from __future__ import annotations

import os

from rq import Worker

from services.api.redis_clients import get_redis_client
from services.api.workers.rq_tasks import (
    scan_pending_chat_jobs,
    scan_pending_exam_jobs,
    scan_pending_upload_jobs,
)


def _truthy(value: str) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def main() -> None:
    os.environ.setdefault("JOB_QUEUE_BACKEND", "rq")
    queue_name = str(os.getenv("RQ_QUEUE_NAME", "default") or "default")
    tenant_id = str(os.getenv("TENANT_ID", "") or "").strip() or None

    if _truthy(os.getenv("RQ_SCAN_PENDING_ON_START", "")):
        scan_pending_upload_jobs(tenant_id=tenant_id)
        scan_pending_exam_jobs(tenant_id=tenant_id)
        scan_pending_chat_jobs(tenant_id=tenant_id)

    redis = get_redis_client(os.getenv("REDIS_URL", ""), decode_responses=False)
    worker = Worker([queue_name], connection=redis)
    worker.work()


if __name__ == "__main__":
    main()
