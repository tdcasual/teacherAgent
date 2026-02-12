from __future__ import annotations

import os
import logging
_log = logging.getLogger(__name__)



def truthy(value: str) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def env_str(name: str, default: str = "") -> str:
    return str(os.getenv(name, default) or default)


def env_int(name: str, default: int) -> int:
    try:
        return int(env_str(name, str(default)) or default)
    except Exception:
        _log.debug("numeric conversion failed", exc_info=True)
        return int(default)


def env_float(name: str, default: float) -> float:
    try:
        return float(env_str(name, str(default)) or default)
    except Exception:
        _log.debug("numeric conversion failed", exc_info=True)
        return float(default)


def env_bool(name: str, default: str = "") -> bool:
    return truthy(env_str(name, default))


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


def data_dir() -> str:
    return env_str("DATA_DIR", "")


def uploads_dir() -> str:
    return env_str("UPLOADS_DIR", "")


def llm_routing_path() -> str:
    return env_str("LLM_ROUTING_PATH", "")


def diag_log_enabled() -> bool:
    return env_bool("DIAG_LOG", "")


def diag_log_path() -> str:
    return env_str("DIAG_LOG_PATH", "")


def chat_worker_pool_size() -> int:
    return max(1, env_int("CHAT_WORKER_POOL_SIZE", 4))


def chat_lane_max_queue() -> int:
    return max(1, env_int("CHAT_LANE_MAX_QUEUE", 6))


def chat_lane_debounce_ms() -> int:
    return max(0, env_int("CHAT_LANE_DEBOUNCE_MS", 500))


def chat_job_claim_ttl_sec() -> int:
    return max(10, env_int("CHAT_JOB_CLAIM_TTL_SEC", 600))


def session_index_max_items() -> int:
    return max(50, env_int("SESSION_INDEX_MAX_ITEMS", 500))


def teacher_session_compact_enabled() -> bool:
    return env_bool("TEACHER_SESSION_COMPACT_ENABLED", "1")


def teacher_session_compact_main_only() -> bool:
    return env_bool("TEACHER_SESSION_COMPACT_MAIN_ONLY", "1")


def teacher_session_compact_max_messages() -> int:
    return max(4, env_int("TEACHER_SESSION_COMPACT_MAX_MESSAGES", 160))


def teacher_session_compact_keep_tail(max_messages: int) -> int:
    keep_tail = max(1, env_int("TEACHER_SESSION_COMPACT_KEEP_TAIL", 40))
    if keep_tail >= max_messages:
        keep_tail = max(1, int(max_messages // 2))
    return keep_tail


def teacher_session_compact_min_interval_sec() -> int:
    return max(0, env_int("TEACHER_SESSION_COMPACT_MIN_INTERVAL_SEC", 60))


def teacher_session_compact_max_source_chars() -> int:
    return max(2000, env_int("TEACHER_SESSION_COMPACT_MAX_SOURCE_CHARS", 12000))


def teacher_session_context_include_summary() -> bool:
    return env_bool("TEACHER_SESSION_CONTEXT_INCLUDE_SUMMARY", "1")


def teacher_session_context_summary_max_chars() -> int:
    return max(0, env_int("TEACHER_SESSION_CONTEXT_SUMMARY_MAX_CHARS", 1500))


def teacher_memory_auto_enabled() -> bool:
    return env_bool("TEACHER_MEMORY_AUTO_ENABLED", "1")


def teacher_memory_auto_min_content_chars() -> int:
    return max(6, env_int("TEACHER_MEMORY_AUTO_MIN_CONTENT_CHARS", 12))


def teacher_memory_auto_max_proposals_per_day() -> int:
    return max(1, env_int("TEACHER_MEMORY_AUTO_MAX_PROPOSALS_PER_DAY", 8))


def teacher_memory_flush_enabled() -> bool:
    return env_bool("TEACHER_MEMORY_FLUSH_ENABLED", "1")


def teacher_memory_flush_margin_messages() -> int:
    return max(1, env_int("TEACHER_MEMORY_FLUSH_MARGIN_MESSAGES", 24))


def teacher_memory_flush_max_source_chars() -> int:
    return max(500, env_int("TEACHER_MEMORY_FLUSH_MAX_SOURCE_CHARS", 2400))


def teacher_memory_auto_apply_enabled() -> bool:
    return env_bool("TEACHER_MEMORY_AUTO_APPLY_ENABLED", "1")


def teacher_memory_auto_apply_targets_raw() -> str:
    return env_str("TEACHER_MEMORY_AUTO_APPLY_TARGETS", "DAILY,MEMORY")


def teacher_memory_auto_apply_strict() -> bool:
    return env_bool("TEACHER_MEMORY_AUTO_APPLY_STRICT", "1")


def teacher_memory_auto_infer_enabled() -> bool:
    return env_bool("TEACHER_MEMORY_AUTO_INFER_ENABLED", "1")


def teacher_memory_auto_infer_min_repeats() -> int:
    return max(2, env_int("TEACHER_MEMORY_AUTO_INFER_MIN_REPEATS", 2))


def teacher_memory_auto_infer_lookback_turns() -> int:
    return max(4, min(80, env_int("TEACHER_MEMORY_AUTO_INFER_LOOKBACK_TURNS", 24)))


def teacher_memory_auto_infer_min_chars() -> int:
    return max(8, env_int("TEACHER_MEMORY_AUTO_INFER_MIN_CHARS", 16))


def teacher_memory_auto_infer_min_priority() -> int:
    return max(0, min(100, env_int("TEACHER_MEMORY_AUTO_INFER_MIN_PRIORITY", 58)))


def teacher_memory_decay_enabled() -> bool:
    return env_bool("TEACHER_MEMORY_DECAY_ENABLED", "1")


def teacher_memory_ttl_days_memory() -> int:
    return max(0, env_int("TEACHER_MEMORY_TTL_DAYS_MEMORY", 180))


def teacher_memory_ttl_days_daily() -> int:
    return max(0, env_int("TEACHER_MEMORY_TTL_DAYS_DAILY", 14))


def teacher_memory_context_max_entries() -> int:
    return max(4, env_int("TEACHER_MEMORY_CONTEXT_MAX_ENTRIES", 18))


def teacher_memory_search_filter_expired() -> bool:
    return env_bool("TEACHER_MEMORY_SEARCH_FILTER_EXPIRED", "1")


def discussion_complete_marker() -> str:
    return env_str("DISCUSSION_COMPLETE_MARKER", "\u3010\u4e2a\u6027\u5316\u4f5c\u4e1a\u3011")


def grade_count_conf_threshold() -> float:
    return env_float("GRADE_COUNT_CONF_THRESHOLD", 0.6)


def ocr_max_concurrency() -> int:
    return max(1, env_int("OCR_MAX_CONCURRENCY", 4))


def llm_max_concurrency() -> int:
    return max(1, env_int("LLM_MAX_CONCURRENCY", 8))


def llm_max_concurrency_student(total: int) -> int:
    return max(1, env_int("LLM_MAX_CONCURRENCY_STUDENT", int(total)))


def llm_max_concurrency_teacher(total: int) -> int:
    return max(1, env_int("LLM_MAX_CONCURRENCY_TEACHER", int(total)))


def chat_max_messages() -> int:
    return max(4, env_int("CHAT_MAX_MESSAGES", 14))


def chat_max_messages_student(base: int) -> int:
    return max(4, env_int("CHAT_MAX_MESSAGES_STUDENT", max(int(base), 40)))


def chat_max_messages_teacher(base: int) -> int:
    return max(4, env_int("CHAT_MAX_MESSAGES_TEACHER", max(int(base), 40)))


def chat_max_message_chars() -> int:
    return max(256, env_int("CHAT_MAX_MESSAGE_CHARS", 2000))


def chat_extra_system_max_chars() -> int:
    return max(512, env_int("CHAT_EXTRA_SYSTEM_MAX_CHARS", 6000))


def chat_max_tool_rounds() -> int:
    return max(1, env_int("CHAT_MAX_TOOL_ROUNDS", 5))


def chat_max_tool_calls() -> int:
    return max(1, env_int("CHAT_MAX_TOOL_CALLS", 12))


def chat_student_inflight_limit() -> int:
    return max(1, env_int("CHAT_STUDENT_INFLIGHT_LIMIT", 1))


def profile_cache_ttl_sec() -> int:
    return max(0, env_int("PROFILE_CACHE_TTL_SEC", 10))


def assignment_detail_cache_ttl_sec() -> int:
    return max(0, env_int("ASSIGNMENT_DETAIL_CACHE_TTL_SEC", 10))


def profile_update_async() -> bool:
    return env_bool("PROFILE_UPDATE_ASYNC", "1")


def profile_update_queue_max() -> int:
    return max(10, env_int("PROFILE_UPDATE_QUEUE_MAX", 500))


def default_teacher_id() -> str:
    return env_str("DEFAULT_TEACHER_ID", "teacher")


def app_env() -> str:
    env = env_str("APP_ENV", "").strip() or env_str("ENV", "development").strip() or "development"
    return env.lower()


def is_production() -> bool:
    return app_env() in {"prod", "production"}


def allow_inline_fallback_in_prod() -> bool:
    return env_bool("ALLOW_INLINE_FALLBACK_IN_PROD", "0")


def is_pytest() -> bool:
    return bool(os.getenv("PYTEST_CURRENT_TEST"))
