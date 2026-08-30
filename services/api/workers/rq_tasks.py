from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from rq import Queue, Retry

from services.api.chat_redis_lane_store import ChatRedisLaneStore
from services.api.redis_clients import get_redis_client
from services.api.workers.rq_tenant_runtime import load_tenant_module

_log = logging.getLogger(__name__)

RETRY = Retry(max=3, interval=[10, 30, 90])
JOB_TIMEOUT = 600
RESULT_TTL = 86400



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


def _enqueue_retry_job(func: Any, *args: Any, **kwargs: Any) -> Any:
    queue = _get_queue()
    return queue.enqueue(
        func,
        *args,
        **kwargs,
        retry=RETRY,
        job_timeout=JOB_TIMEOUT,
        result_ttl=RESULT_TTL,
    )


def _enqueue_chat_rq_job(func: Any, *args: Any, **kwargs: Any) -> Any:
    # run_chat_job always finish()es the lane; Retry would double-run without try_claim_running.
    queue = _get_queue()
    return queue.enqueue(
        func,
        *args,
        **kwargs,
        job_timeout=JOB_TIMEOUT,
        result_ttl=RESULT_TTL,
    )


def _lane_store(mod: Any, tenant_id: Optional[str]) -> ChatRedisLaneStore:
    tenant_key = str(tenant_id or getattr(mod, "TENANT_ID", "") or "").strip() or "default"
    return ChatRedisLaneStore(
        redis_client=_require_redis_client(decode_responses=True),
        tenant_id=tenant_key,
        claim_ttl_sec=int(getattr(mod, "CHAT_JOB_CLAIM_TTL_SEC", 600) or 600),
        debounce_ms=int(getattr(mod, "CHAT_LANE_DEBOUNCE_MS", 500) or 500),
    )


def enqueue_upload_job(job_id: str, *, tenant_id: Optional[str] = None) -> None:
    _enqueue_retry_job(run_upload_job, job_id, tenant_id=tenant_id)


def enqueue_survey_job(job_id: str, *, tenant_id: Optional[str] = None) -> None:
    _enqueue_retry_job(run_survey_job, job_id, tenant_id=tenant_id)


def enqueue_profile_update(payload: Dict[str, Any], *, tenant_id: Optional[str] = None) -> None:
    _enqueue_retry_job(run_profile_update, payload=payload, tenant_id=tenant_id)


PROCESS_ARCHIVE_JOB_TIMEOUT = 60


def enqueue_process_archive(payload: Dict[str, Any], *, tenant_id: Optional[str] = None) -> None:
    queue = _get_queue()
    queue.enqueue(
        run_process_archive,
        payload=payload,
        tenant_id=tenant_id,
        job_timeout=PROCESS_ARCHIVE_JOB_TIMEOUT,
        result_ttl=RESULT_TTL,
    )


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
        _enqueue_chat_rq_job(run_chat_job, job_id, lane_final, tenant_id=tenant_id)
    return {"lane_id": lane_final, **info}


def _scan_pending_jobs(
    job_dir: Path,
    *,
    enqueue_fn: Callable[[Dict[str, Any]], Any],
) -> int:
    job_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for job_path in sorted(job_dir.glob("*/job.json")):
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


def scan_pending_survey_jobs(*, tenant_id: Optional[str] = None) -> int:
    mod = load_tenant_module(tenant_id)
    return _scan_pending_jobs(
        mod.SURVEY_JOB_DIR,
        enqueue_fn=lambda data: enqueue_survey_job(str(data.get("job_id") or ""), tenant_id=tenant_id),
    )


def run_upload_job(job_id: str, *, tenant_id: Optional[str] = None) -> None:
    mod = load_tenant_module(tenant_id)
    mod.process_upload_job(job_id)


def run_survey_job(job_id: str, *, tenant_id: Optional[str] = None) -> None:
    mod = load_tenant_module(tenant_id)
    process_job = getattr(mod, "process_survey_job", None)
    if callable(process_job):
        process_job(job_id)


def run_profile_update(payload: Dict[str, Any], *, tenant_id: Optional[str] = None) -> None:
    mod = load_tenant_module(tenant_id)
    mod.student_profile_update(payload)


def run_process_archive(payload: Dict[str, Any], *, tenant_id: Optional[str] = None) -> None:
    from services.api.workers.process_archive_worker_service import run_process_archive_job

    mod = load_tenant_module(tenant_id)
    deps = mod.process_archive_worker_deps()
    run_process_archive_job(payload if isinstance(payload, dict) else {}, deps=deps)


def _chat_job_confirm_pending_active(mod: Any, job_id: str) -> bool:
    load = getattr(mod, "load_chat_job", None)
    if not callable(load):
        return False
    try:
        job = load(job_id)
    except Exception:  # policy: allowed-broad-except
        _log.debug("failed to load chat job %s for confirm pending", job_id, exc_info=True)
        return False
    if not isinstance(job, dict):
        return False
    from services.api.tool_confirm_service import confirm_pending_is_live

    return confirm_pending_is_live(job.get("confirm_pending"))


def resume_chat_job_after_confirm(
    job_id: str,
    lane_id: str,
    *,
    tenant_id: Optional[str] = None,
) -> Dict[str, Any]:
    mod = load_tenant_module(tenant_id)
    store = _lane_store(mod, tenant_id)
    active = store.get_active(lane_id)
    if active == job_id:
        _enqueue_chat_rq_job(run_chat_job, job_id, lane_id, tenant_id=tenant_id)
        return {"ok": True, "mode": "active"}
    if not active:
        if store.reacquire_active(job_id, lane_id):
            _enqueue_chat_rq_job(run_chat_job, job_id, lane_id, tenant_id=tenant_id)
            return {"ok": True, "mode": "reacquire"}
        store.park_behind_active(job_id, lane_id)
        return {"ok": True, "mode": "park"}
    store.park_behind_active(job_id, lane_id)
    return {"ok": True, "mode": "park"}


def run_chat_job(job_id: str, lane_id: str, *, tenant_id: Optional[str] = None) -> None:
    mod = load_tenant_module(tenant_id)
    store = _lane_store(mod, tenant_id)
    finish_lane = True
    try:
        try:
            mod.process_chat_job(job_id)
        except Exception as exc:
            detail = str(exc)[:200]
            if callable(getattr(mod, "write_chat_job", None)):
                try:
                    mod.write_chat_job(
                        job_id,
                        {
                            "status": "failed",
                            "error": "chat_job_failed",
                            "error_detail": detail,
                        },
                    )
                except Exception:
                    _log.warning(
                        "failed to persist chat failure status for job %s",
                        job_id,
                        exc_info=True,
                    )
            if callable(getattr(mod, "append_chat_event", None)):
                try:
                    mod.append_chat_event(
                        job_id,
                        "job.failed",
                        {
                            "status": "failed",
                            "error": "chat_job_failed",
                            "error_detail": detail,
                        },
                    )
                except Exception:
                    _log.warning(
                        "failed to append chat failure event for job %s",
                        job_id,
                        exc_info=True,
                    )
            raise
        if _chat_job_confirm_pending_active(mod, job_id):
            store.refresh_claim(job_id, lane_id)
            finish_lane = False
    finally:
        if finish_lane:
            next_job_id = store.finish(job_id, lane_id)
            if next_job_id:
                _enqueue_chat_rq_job(run_chat_job, next_job_id, lane_id, tenant_id=tenant_id)
