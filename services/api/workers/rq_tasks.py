from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from rq import Queue

from services.api.chat_redis_lane_store import ChatRedisLaneStore
from services.api.redis_clients import get_redis_client
from services.api.workers.rq_tenant_runtime import load_tenant_module

_log = logging.getLogger(__name__)



def _queue_name() -> str:
    return str(os.getenv("RQ_QUEUE_NAME", "default") or "default")


def _require_redis_client(*, decode_responses: bool) -> Any:
    redis_url = str(os.getenv("REDIS_URL", "") or "").strip()
    if not redis_url:
        raise RuntimeError("Redis required: REDIS_URL not set")
    client = get_redis_client(redis_url, decode_responses=decode_responses)
    try:
        client.ping()
    except Exception as exc:
        raise RuntimeError("Redis required: unable to connect") from exc
    return client


def require_redis() -> None:
    _require_redis_client(decode_responses=False)


def _get_queue() -> Queue:
    redis = _require_redis_client(decode_responses=False)
    return Queue(_queue_name(), connection=redis)


def _lane_store(mod: Any, tenant_id: Optional[str]) -> ChatRedisLaneStore:
    tenant_key = str(tenant_id or getattr(mod, "TENANT_ID", "") or "").strip() or "default"
    return ChatRedisLaneStore(
        redis_client=_require_redis_client(decode_responses=True),
        tenant_id=tenant_key,
        claim_ttl_sec=int(getattr(mod, "CHAT_JOB_CLAIM_TTL_SEC", 600) or 600),
        debounce_ms=int(getattr(mod, "CHAT_LANE_DEBOUNCE_MS", 500) or 500),
    )


def enqueue_upload_job(job_id: str, *, tenant_id: Optional[str] = None) -> None:
    queue = _get_queue()
    queue.enqueue(run_upload_job, job_id, tenant_id=tenant_id)


def enqueue_exam_job(job_id: str, *, tenant_id: Optional[str] = None) -> None:
    queue = _get_queue()
    queue.enqueue(run_exam_job, job_id, tenant_id=tenant_id)


def enqueue_profile_update(payload: Dict[str, Any], *, tenant_id: Optional[str] = None) -> None:
    queue = _get_queue()
    queue.enqueue(run_profile_update, payload=payload, tenant_id=tenant_id)


def enqueue_chat_job(job_id: str, lane_id: Optional[str] = None, *, tenant_id: Optional[str] = None) -> Dict[str, Any]:
    mod = load_tenant_module(tenant_id)
    lane_final = str(lane_id or "").strip()
    if not lane_final:
        try:
            job = mod.load_chat_job(job_id)
            lane_final = mod.resolve_chat_lane_id_from_job(job)
        except Exception:
            _log.warning("operation failed", exc_info=True)
            lane_final = "unknown:session_main:req_unknown"

    store = _lane_store(mod, tenant_id)
    info, dispatch = store.enqueue(job_id, lane_final)
    if dispatch:
        queue = _get_queue()
        queue.enqueue(run_chat_job, job_id, lane_final, tenant_id=tenant_id)
    return {"lane_id": lane_final, **info}


def _scan_pending_jobs(
    job_dir: Path,
    *,
    enqueue_fn: Callable[[Dict[str, Any]], Any],
) -> int:
    job_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for job_path in job_dir.glob("*/job.json"):
        try:
            data = json.loads(job_path.read_text(encoding="utf-8"))
        except Exception:
            _log.warning("directory creation failed", exc_info=True)
            continue
        status = str(data.get("status") or "")
        job_id = str(data.get("job_id") or "")
        if status not in {"queued", "processing"} or not job_id:
            continue
        enqueue_fn(data)
        count += 1
    return count


def scan_pending_upload_jobs(*, tenant_id: Optional[str] = None) -> int:
    mod = load_tenant_module(tenant_id)
    return _scan_pending_jobs(
        mod.UPLOAD_JOB_DIR,
        enqueue_fn=lambda data: enqueue_upload_job(str(data.get("job_id") or ""), tenant_id=tenant_id),
    )


def scan_pending_exam_jobs(*, tenant_id: Optional[str] = None) -> int:
    mod = load_tenant_module(tenant_id)
    return _scan_pending_jobs(
        mod.EXAM_UPLOAD_JOB_DIR,
        enqueue_fn=lambda data: enqueue_exam_job(str(data.get("job_id") or ""), tenant_id=tenant_id),
    )


def scan_pending_chat_jobs(*, tenant_id: Optional[str] = None) -> int:
    mod = load_tenant_module(tenant_id)
    return _scan_pending_jobs(
        mod.CHAT_JOB_DIR,
        enqueue_fn=lambda data: enqueue_chat_job(
            str(data.get("job_id") or ""),
            mod.resolve_chat_lane_id_from_job(data),
            tenant_id=tenant_id,
        ),
    )


def run_upload_job(job_id: str, *, tenant_id: Optional[str] = None) -> None:
    mod = load_tenant_module(tenant_id)
    mod.process_upload_job(job_id)


def run_exam_job(job_id: str, *, tenant_id: Optional[str] = None) -> None:
    mod = load_tenant_module(tenant_id)
    mod.process_exam_upload_job(job_id)


def run_profile_update(payload: Dict[str, Any], *, tenant_id: Optional[str] = None) -> None:
    mod = load_tenant_module(tenant_id)
    mod.student_profile_update(payload)


def run_chat_job(job_id: str, lane_id: str, *, tenant_id: Optional[str] = None) -> None:
    mod = load_tenant_module(tenant_id)
    store = _lane_store(mod, tenant_id)
    try:
        mod.process_chat_job(job_id)
    finally:
        next_job_id = store.finish(job_id, lane_id)
        if next_job_id:
            queue = _get_queue()
            queue.enqueue(run_chat_job, next_job_id, lane_id, tenant_id=tenant_id)
