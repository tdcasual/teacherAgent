from __future__ import annotations

import os


def truthy(value: str) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def env_str(name: str, default: str = "") -> str:
    return str(os.getenv(name, default) or default)


def job_queue_backend() -> str:
    return env_str("JOB_QUEUE_BACKEND", "").strip().lower()


def rq_backend_enabled() -> bool:
    return truthy(env_str("RQ_BACKEND_ENABLED", ""))


def redis_url() -> str:
    return env_str("REDIS_URL", "redis://localhost:6379/0")


def rq_queue_name() -> str:
    return env_str("RQ_QUEUE_NAME", "default")


def tenant_id() -> str:
    return env_str("TENANT_ID", "").strip()
