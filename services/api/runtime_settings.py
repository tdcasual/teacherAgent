from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping


def truthy(value: str) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _env_str(env: Mapping[str, str], name: str, default: str = "") -> str:
    raw = env.get(name, default)
    return str(raw if raw is not None else default)


def _env_int(env: Mapping[str, str], name: str, default: int) -> int:
    try:
        return int(_env_str(env, name, str(default)) or default)
    except Exception:
        return int(default)


def _env_float(env: Mapping[str, str], name: str, default: float) -> float:
    try:
        return float(_env_str(env, name, str(default)) or default)
    except Exception:
        return float(default)


def _env_bool(env: Mapping[str, str], name: str, default: str = "") -> bool:
    return truthy(_env_str(env, name, default))


@dataclass(frozen=True)
class AppSettings:
    job_queue_backend: str
    rq_backend_enabled: bool
    redis_url: str
    rq_queue_name: str
    tenant_id: str
    data_dir: str
    uploads_dir: str
    diag_log_enabled: bool
    diag_log_path: str
    chat_worker_pool_size: int
    chat_lane_max_queue: int
    chat_lane_debounce_ms: int
    chat_job_claim_ttl_sec: int
    session_index_max_items: int
    teacher_session_compact_enabled: bool
    teacher_session_compact_main_only: bool
    teacher_session_compact_max_messages: int
    teacher_session_compact_keep_tail: int
    teacher_session_compact_min_interval_sec: int
    teacher_session_compact_max_source_chars: int
    teacher_session_context_include_summary: bool
    teacher_session_context_summary_max_chars: int
    teacher_memory_auto_enabled: bool
    teacher_memory_auto_min_content_chars: int
    teacher_memory_auto_max_proposals_per_day: int
    teacher_memory_flush_enabled: bool
    teacher_memory_flush_margin_messages: int
    teacher_memory_flush_max_source_chars: int
    teacher_memory_auto_apply_enabled: bool
    teacher_memory_auto_apply_targets_raw: str
    teacher_memory_auto_apply_strict: bool
    teacher_memory_auto_infer_enabled: bool
    teacher_memory_auto_infer_min_repeats: int
    teacher_memory_auto_infer_lookback_turns: int
    teacher_memory_auto_infer_min_chars: int
    teacher_memory_auto_infer_min_priority: int
    teacher_memory_decay_enabled: bool
    teacher_memory_ttl_days_memory: int
    teacher_memory_ttl_days_daily: int
    teacher_memory_context_max_entries: int
    teacher_memory_search_filter_expired: bool
    discussion_complete_marker: str
    grade_count_conf_threshold: float
    ocr_max_concurrency: int
    llm_max_concurrency: int
    llm_max_concurrency_student: int
    llm_max_concurrency_teacher: int
    chat_max_messages: int
    chat_max_messages_student: int
    chat_max_messages_teacher: int
    chat_max_message_chars: int
    chat_extra_system_max_chars: int
    chat_max_tool_rounds: int
    chat_max_tool_calls: int
    chat_student_inflight_limit: int
    profile_cache_ttl_sec: int
    assignment_detail_cache_ttl_sec: int
    profile_update_async: bool
    profile_update_queue_max: int
    default_teacher_id: str
    app_env: str
    is_pytest: bool


def load_settings(env: Mapping[str, str] | None = None) -> AppSettings:
    source = os.environ if env is None else env

    job_queue_backend = _env_str(source, "JOB_QUEUE_BACKEND", "").strip().lower()
    chat_worker_pool_size = max(1, _env_int(source, "CHAT_WORKER_POOL_SIZE", 4))
    teacher_session_compact_max_messages = max(
        4, _env_int(source, "TEACHER_SESSION_COMPACT_MAX_MESSAGES", 160)
    )
    teacher_session_compact_keep_tail = max(
        1, _env_int(source, "TEACHER_SESSION_COMPACT_KEEP_TAIL", 40)
    )
    if teacher_session_compact_keep_tail >= teacher_session_compact_max_messages:
        teacher_session_compact_keep_tail = max(
            1, int(teacher_session_compact_max_messages // 2)
        )

    llm_max_concurrency = max(1, _env_int(source, "LLM_MAX_CONCURRENCY", 8))
    chat_max_messages = max(4, _env_int(source, "CHAT_MAX_MESSAGES", 14))

    app_env = (
        _env_str(source, "APP_ENV", "").strip()
        or _env_str(source, "ENV", "development").strip()
        or "development"
    ).lower()

    return AppSettings(
        job_queue_backend=job_queue_backend,
        rq_backend_enabled=truthy(_env_str(source, "RQ_BACKEND_ENABLED", "")),
        redis_url=_env_str(source, "REDIS_URL", "redis://localhost:6379/0"),
        rq_queue_name=_env_str(source, "RQ_QUEUE_NAME", "default"),
        tenant_id=_env_str(source, "TENANT_ID", "").strip(),
        data_dir=_env_str(source, "DATA_DIR", ""),
        uploads_dir=_env_str(source, "UPLOADS_DIR", ""),
        diag_log_enabled=_env_bool(source, "DIAG_LOG", ""),
        diag_log_path=_env_str(source, "DIAG_LOG_PATH", ""),
        chat_worker_pool_size=chat_worker_pool_size,
        chat_lane_max_queue=max(1, _env_int(source, "CHAT_LANE_MAX_QUEUE", 6)),
        chat_lane_debounce_ms=max(0, _env_int(source, "CHAT_LANE_DEBOUNCE_MS", 500)),
        chat_job_claim_ttl_sec=max(10, _env_int(source, "CHAT_JOB_CLAIM_TTL_SEC", 600)),
        session_index_max_items=max(50, _env_int(source, "SESSION_INDEX_MAX_ITEMS", 500)),
        teacher_session_compact_enabled=_env_bool(source, "TEACHER_SESSION_COMPACT_ENABLED", "1"),
        teacher_session_compact_main_only=_env_bool(
            source, "TEACHER_SESSION_COMPACT_MAIN_ONLY", "1"
        ),
        teacher_session_compact_max_messages=teacher_session_compact_max_messages,
        teacher_session_compact_keep_tail=teacher_session_compact_keep_tail,
        teacher_session_compact_min_interval_sec=max(
            0, _env_int(source, "TEACHER_SESSION_COMPACT_MIN_INTERVAL_SEC", 60)
        ),
        teacher_session_compact_max_source_chars=max(
            2000, _env_int(source, "TEACHER_SESSION_COMPACT_MAX_SOURCE_CHARS", 12000)
        ),
        teacher_session_context_include_summary=_env_bool(
            source, "TEACHER_SESSION_CONTEXT_INCLUDE_SUMMARY", "1"
        ),
        teacher_session_context_summary_max_chars=max(
            0, _env_int(source, "TEACHER_SESSION_CONTEXT_SUMMARY_MAX_CHARS", 1500)
        ),
        teacher_memory_auto_enabled=_env_bool(source, "TEACHER_MEMORY_AUTO_ENABLED", "1"),
        teacher_memory_auto_min_content_chars=max(
            6, _env_int(source, "TEACHER_MEMORY_AUTO_MIN_CONTENT_CHARS", 12)
        ),
        teacher_memory_auto_max_proposals_per_day=max(
            1, _env_int(source, "TEACHER_MEMORY_AUTO_MAX_PROPOSALS_PER_DAY", 8)
        ),
        teacher_memory_flush_enabled=_env_bool(source, "TEACHER_MEMORY_FLUSH_ENABLED", "1"),
        teacher_memory_flush_margin_messages=max(
            1, _env_int(source, "TEACHER_MEMORY_FLUSH_MARGIN_MESSAGES", 24)
        ),
        teacher_memory_flush_max_source_chars=max(
            500, _env_int(source, "TEACHER_MEMORY_FLUSH_MAX_SOURCE_CHARS", 2400)
        ),
        teacher_memory_auto_apply_enabled=_env_bool(
            source, "TEACHER_MEMORY_AUTO_APPLY_ENABLED", "1"
        ),
        teacher_memory_auto_apply_targets_raw=_env_str(
            source, "TEACHER_MEMORY_AUTO_APPLY_TARGETS", "DAILY,MEMORY"
        ),
        teacher_memory_auto_apply_strict=_env_bool(
            source, "TEACHER_MEMORY_AUTO_APPLY_STRICT", "1"
        ),
        teacher_memory_auto_infer_enabled=_env_bool(
            source, "TEACHER_MEMORY_AUTO_INFER_ENABLED", "1"
        ),
        teacher_memory_auto_infer_min_repeats=max(
            2, _env_int(source, "TEACHER_MEMORY_AUTO_INFER_MIN_REPEATS", 2)
        ),
        teacher_memory_auto_infer_lookback_turns=max(
            4, min(80, _env_int(source, "TEACHER_MEMORY_AUTO_INFER_LOOKBACK_TURNS", 24))
        ),
        teacher_memory_auto_infer_min_chars=max(
            8, _env_int(source, "TEACHER_MEMORY_AUTO_INFER_MIN_CHARS", 16)
        ),
        teacher_memory_auto_infer_min_priority=max(
            0, min(100, _env_int(source, "TEACHER_MEMORY_AUTO_INFER_MIN_PRIORITY", 58))
        ),
        teacher_memory_decay_enabled=_env_bool(source, "TEACHER_MEMORY_DECAY_ENABLED", "1"),
        teacher_memory_ttl_days_memory=max(
            0, _env_int(source, "TEACHER_MEMORY_TTL_DAYS_MEMORY", 180)
        ),
        teacher_memory_ttl_days_daily=max(
            0, _env_int(source, "TEACHER_MEMORY_TTL_DAYS_DAILY", 14)
        ),
        teacher_memory_context_max_entries=max(
            4, _env_int(source, "TEACHER_MEMORY_CONTEXT_MAX_ENTRIES", 18)
        ),
        teacher_memory_search_filter_expired=_env_bool(
            source, "TEACHER_MEMORY_SEARCH_FILTER_EXPIRED", "1"
        ),
        discussion_complete_marker=_env_str(source, "DISCUSSION_COMPLETE_MARKER", "【个性化作业】"),
        grade_count_conf_threshold=_env_float(source, "GRADE_COUNT_CONF_THRESHOLD", 0.6),
        ocr_max_concurrency=max(1, _env_int(source, "OCR_MAX_CONCURRENCY", 4)),
        llm_max_concurrency=llm_max_concurrency,
        llm_max_concurrency_student=max(
            1, _env_int(source, "LLM_MAX_CONCURRENCY_STUDENT", int(llm_max_concurrency))
        ),
        llm_max_concurrency_teacher=max(
            1, _env_int(source, "LLM_MAX_CONCURRENCY_TEACHER", int(llm_max_concurrency))
        ),
        chat_max_messages=chat_max_messages,
        chat_max_messages_student=max(
            4, _env_int(source, "CHAT_MAX_MESSAGES_STUDENT", max(int(chat_max_messages), 40))
        ),
        chat_max_messages_teacher=max(
            4, _env_int(source, "CHAT_MAX_MESSAGES_TEACHER", max(int(chat_max_messages), 40))
        ),
        chat_max_message_chars=max(256, _env_int(source, "CHAT_MAX_MESSAGE_CHARS", 2000)),
        chat_extra_system_max_chars=max(
            512, _env_int(source, "CHAT_EXTRA_SYSTEM_MAX_CHARS", 6000)
        ),
        chat_max_tool_rounds=max(1, _env_int(source, "CHAT_MAX_TOOL_ROUNDS", 5)),
        chat_max_tool_calls=max(1, _env_int(source, "CHAT_MAX_TOOL_CALLS", 12)),
        chat_student_inflight_limit=max(
            1, _env_int(source, "CHAT_STUDENT_INFLIGHT_LIMIT", 1)
        ),
        profile_cache_ttl_sec=max(0, _env_int(source, "PROFILE_CACHE_TTL_SEC", 10)),
        assignment_detail_cache_ttl_sec=max(
            0, _env_int(source, "ASSIGNMENT_DETAIL_CACHE_TTL_SEC", 10)
        ),
        profile_update_async=_env_bool(source, "PROFILE_UPDATE_ASYNC", "1"),
        profile_update_queue_max=max(10, _env_int(source, "PROFILE_UPDATE_QUEUE_MAX", 500)),
        default_teacher_id=_env_str(source, "DEFAULT_TEACHER_ID", "teacher"),
        app_env=app_env,
        is_pytest=bool(_env_str(source, "PYTEST_CURRENT_TEST", "")),
    )
