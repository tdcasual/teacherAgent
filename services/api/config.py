from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, FrozenSet, List, Tuple

from .runtime_settings import AppSettings, load_settings


@dataclass(frozen=True)
class RuntimePaths:
    APP_ROOT: Path
    DATA_DIR: Path
    UPLOADS_DIR: Path
    OCR_UTILS_DIR: Path
    DIAG_LOG_PATH: Path
    UPLOAD_JOB_DIR: Path
    EXAM_UPLOAD_JOB_DIR: Path
    CHAT_JOB_DIR: Path
    STUDENT_SESSIONS_DIR: Path
    TEACHER_WORKSPACES_DIR: Path
    TEACHER_SESSIONS_DIR: Path
    STUDENT_SUBMISSIONS_DIR: Path


@dataclass(frozen=True)
class ConfigValues:
    APP_ROOT: Path
    DATA_DIR: Path
    UPLOADS_DIR: Path
    OCR_UTILS_DIR: Path
    TENANT_ID: str
    JOB_QUEUE_BACKEND: str
    RQ_BACKEND_ENABLED: bool
    REDIS_URL: str
    RQ_QUEUE_NAME: str
    DIAG_LOG_ENABLED: bool
    DIAG_LOG_PATH: Path
    UPLOAD_JOB_DIR: Path
    EXAM_UPLOAD_JOB_DIR: Path
    CHAT_JOB_DIR: Path
    CHAT_WORKER_POOL_SIZE: int
    CHAT_LANE_MAX_QUEUE: int
    CHAT_LANE_DEBOUNCE_MS: int
    CHAT_JOB_CLAIM_TTL_SEC: int
    STUDENT_SESSIONS_DIR: Path
    TEACHER_WORKSPACES_DIR: Path
    TEACHER_SESSIONS_DIR: Path
    STUDENT_SUBMISSIONS_DIR: Path
    SESSION_INDEX_MAX_ITEMS: int
    TEACHER_SESSION_COMPACT_ENABLED: bool
    TEACHER_SESSION_COMPACT_MAIN_ONLY: bool
    TEACHER_SESSION_COMPACT_MAX_MESSAGES: int
    TEACHER_SESSION_COMPACT_KEEP_TAIL: int
    TEACHER_SESSION_COMPACT_MIN_INTERVAL_SEC: int
    TEACHER_SESSION_COMPACT_MAX_SOURCE_CHARS: int
    TEACHER_SESSION_CONTEXT_INCLUDE_SUMMARY: bool
    TEACHER_SESSION_CONTEXT_SUMMARY_MAX_CHARS: int
    TEACHER_MEMORY_AUTO_ENABLED: bool
    TEACHER_MEMORY_AUTO_MIN_CONTENT_CHARS: int
    TEACHER_MEMORY_AUTO_MAX_PROPOSALS_PER_DAY: int
    TEACHER_MEMORY_FLUSH_ENABLED: bool
    TEACHER_MEMORY_FLUSH_MARGIN_MESSAGES: int
    TEACHER_MEMORY_FLUSH_MAX_SOURCE_CHARS: int
    TEACHER_MEMORY_AUTO_APPLY_ENABLED: bool
    TEACHER_MEMORY_AUTO_APPLY_TARGETS: FrozenSet[str]
    TEACHER_MEMORY_AUTO_APPLY_STRICT: bool
    TEACHER_MEMORY_AUTO_INFER_ENABLED: bool
    TEACHER_MEMORY_AUTO_INFER_MIN_REPEATS: int
    TEACHER_MEMORY_AUTO_INFER_LOOKBACK_TURNS: int
    TEACHER_MEMORY_AUTO_INFER_MIN_CHARS: int
    TEACHER_MEMORY_AUTO_INFER_MIN_PRIORITY: int
    TEACHER_MEMORY_DECAY_ENABLED: bool
    TEACHER_MEMORY_TTL_DAYS_MEMORY: int
    TEACHER_MEMORY_TTL_DAYS_DAILY: int
    TEACHER_MEMORY_CONTEXT_MAX_ENTRIES: int
    TEACHER_MEMORY_SEARCH_FILTER_EXPIRED: bool
    STUDENT_MEMORY_ASSIGNMENT_EVIDENCE_HIGH_MASTERY_RATIO: float
    STUDENT_MEMORY_ASSIGNMENT_EVIDENCE_LOW_MASTERY_RATIO: float
    DISCUSSION_COMPLETE_MARKER: str
    GRADE_COUNT_CONF_THRESHOLD: float
    OCR_MAX_CONCURRENCY: int
    LLM_MAX_CONCURRENCY: int
    LLM_MAX_CONCURRENCY_STUDENT: int
    LLM_MAX_CONCURRENCY_TEACHER: int
    CHAT_MAX_MESSAGES: int
    CHAT_MAX_MESSAGES_STUDENT: int
    CHAT_MAX_MESSAGES_TEACHER: int
    CHAT_MAX_MESSAGE_CHARS: int
    CHAT_EXTRA_SYSTEM_MAX_CHARS: int
    CHAT_MAX_TOOL_ROUNDS: int
    CHAT_MAX_TOOL_CALLS: int
    CHAT_STUDENT_INFLIGHT_LIMIT: int
    PROFILE_CACHE_TTL_SEC: int
    ASSIGNMENT_DETAIL_CACHE_TTL_SEC: int
    PROFILE_UPDATE_ASYNC: bool
    PROFILE_UPDATE_QUEUE_MAX: int
    _settings: AppSettings


def _teacher_memory_auto_apply_targets(raw: str) -> FrozenSet[str]:
    targets = frozenset(
        p.strip().upper() for p in str(raw or "").split(",") if str(p or "").strip()
    )
    return targets or frozenset({"DAILY", "MEMORY"})


def build_paths(
    settings: AppSettings,
    *,
    app_root: Path | None = None,
) -> RuntimePaths:
    root = (app_root or Path(__file__).resolve().parents[2]).resolve()
    data_dir = Path(settings.data_dir).expanduser() if settings.data_dir else (root / "data")
    uploads_dir = (
        Path(settings.uploads_dir).expanduser() if settings.uploads_dir else (root / "uploads")
    )
    ocr_utils_dir = root / "skills" / "physics-lesson-capture" / "scripts"
    diag_log_path = (
        Path(settings.diag_log_path).expanduser()
        if settings.diag_log_path
        else (root / "tmp" / "diagnostics.log")
    )
    return RuntimePaths(
        APP_ROOT=root,
        DATA_DIR=data_dir,
        UPLOADS_DIR=uploads_dir,
        OCR_UTILS_DIR=ocr_utils_dir,
        DIAG_LOG_PATH=diag_log_path,
        UPLOAD_JOB_DIR=uploads_dir / "assignment_jobs",
        EXAM_UPLOAD_JOB_DIR=uploads_dir / "exam_jobs",
        CHAT_JOB_DIR=uploads_dir / "chat_jobs",
        STUDENT_SESSIONS_DIR=data_dir / "student_chat_sessions",
        TEACHER_WORKSPACES_DIR=data_dir / "teacher_workspaces",
        TEACHER_SESSIONS_DIR=data_dir / "teacher_chat_sessions",
        STUDENT_SUBMISSIONS_DIR=data_dir / "student_submissions",
    )


def build_config(
    settings: AppSettings,
    *,
    app_root: Path | None = None,
) -> ConfigValues:
    paths = build_paths(settings, app_root=app_root)
    return ConfigValues(
        APP_ROOT=paths.APP_ROOT,
        DATA_DIR=paths.DATA_DIR,
        UPLOADS_DIR=paths.UPLOADS_DIR,
        OCR_UTILS_DIR=paths.OCR_UTILS_DIR,
        TENANT_ID=settings.tenant_id,
        JOB_QUEUE_BACKEND=settings.job_queue_backend,
        RQ_BACKEND_ENABLED=settings.rq_backend_enabled,
        REDIS_URL=settings.redis_url,
        RQ_QUEUE_NAME=settings.rq_queue_name,
        DIAG_LOG_ENABLED=settings.diag_log_enabled,
        DIAG_LOG_PATH=paths.DIAG_LOG_PATH,
        UPLOAD_JOB_DIR=paths.UPLOAD_JOB_DIR,
        EXAM_UPLOAD_JOB_DIR=paths.EXAM_UPLOAD_JOB_DIR,
        CHAT_JOB_DIR=paths.CHAT_JOB_DIR,
        CHAT_WORKER_POOL_SIZE=settings.chat_worker_pool_size,
        CHAT_LANE_MAX_QUEUE=settings.chat_lane_max_queue,
        CHAT_LANE_DEBOUNCE_MS=settings.chat_lane_debounce_ms,
        CHAT_JOB_CLAIM_TTL_SEC=settings.chat_job_claim_ttl_sec,
        STUDENT_SESSIONS_DIR=paths.STUDENT_SESSIONS_DIR,
        TEACHER_WORKSPACES_DIR=paths.TEACHER_WORKSPACES_DIR,
        TEACHER_SESSIONS_DIR=paths.TEACHER_SESSIONS_DIR,
        STUDENT_SUBMISSIONS_DIR=paths.STUDENT_SUBMISSIONS_DIR,
        SESSION_INDEX_MAX_ITEMS=settings.session_index_max_items,
        TEACHER_SESSION_COMPACT_ENABLED=settings.teacher_session_compact_enabled,
        TEACHER_SESSION_COMPACT_MAIN_ONLY=settings.teacher_session_compact_main_only,
        TEACHER_SESSION_COMPACT_MAX_MESSAGES=settings.teacher_session_compact_max_messages,
        TEACHER_SESSION_COMPACT_KEEP_TAIL=settings.teacher_session_compact_keep_tail,
        TEACHER_SESSION_COMPACT_MIN_INTERVAL_SEC=settings.teacher_session_compact_min_interval_sec,
        TEACHER_SESSION_COMPACT_MAX_SOURCE_CHARS=settings.teacher_session_compact_max_source_chars,
        TEACHER_SESSION_CONTEXT_INCLUDE_SUMMARY=settings.teacher_session_context_include_summary,
        TEACHER_SESSION_CONTEXT_SUMMARY_MAX_CHARS=settings.teacher_session_context_summary_max_chars,
        TEACHER_MEMORY_AUTO_ENABLED=settings.teacher_memory_auto_enabled,
        TEACHER_MEMORY_AUTO_MIN_CONTENT_CHARS=settings.teacher_memory_auto_min_content_chars,
        TEACHER_MEMORY_AUTO_MAX_PROPOSALS_PER_DAY=settings.teacher_memory_auto_max_proposals_per_day,
        TEACHER_MEMORY_FLUSH_ENABLED=settings.teacher_memory_flush_enabled,
        TEACHER_MEMORY_FLUSH_MARGIN_MESSAGES=settings.teacher_memory_flush_margin_messages,
        TEACHER_MEMORY_FLUSH_MAX_SOURCE_CHARS=settings.teacher_memory_flush_max_source_chars,
        TEACHER_MEMORY_AUTO_APPLY_ENABLED=settings.teacher_memory_auto_apply_enabled,
        TEACHER_MEMORY_AUTO_APPLY_TARGETS=_teacher_memory_auto_apply_targets(
            settings.teacher_memory_auto_apply_targets_raw
        ),
        TEACHER_MEMORY_AUTO_APPLY_STRICT=settings.teacher_memory_auto_apply_strict,
        TEACHER_MEMORY_AUTO_INFER_ENABLED=settings.teacher_memory_auto_infer_enabled,
        TEACHER_MEMORY_AUTO_INFER_MIN_REPEATS=settings.teacher_memory_auto_infer_min_repeats,
        TEACHER_MEMORY_AUTO_INFER_LOOKBACK_TURNS=settings.teacher_memory_auto_infer_lookback_turns,
        TEACHER_MEMORY_AUTO_INFER_MIN_CHARS=settings.teacher_memory_auto_infer_min_chars,
        TEACHER_MEMORY_AUTO_INFER_MIN_PRIORITY=settings.teacher_memory_auto_infer_min_priority,
        TEACHER_MEMORY_DECAY_ENABLED=settings.teacher_memory_decay_enabled,
        TEACHER_MEMORY_TTL_DAYS_MEMORY=settings.teacher_memory_ttl_days_memory,
        TEACHER_MEMORY_TTL_DAYS_DAILY=settings.teacher_memory_ttl_days_daily,
        TEACHER_MEMORY_CONTEXT_MAX_ENTRIES=settings.teacher_memory_context_max_entries,
        TEACHER_MEMORY_SEARCH_FILTER_EXPIRED=settings.teacher_memory_search_filter_expired,
        STUDENT_MEMORY_ASSIGNMENT_EVIDENCE_HIGH_MASTERY_RATIO=settings.student_memory_assignment_evidence_high_mastery_ratio,
        STUDENT_MEMORY_ASSIGNMENT_EVIDENCE_LOW_MASTERY_RATIO=settings.student_memory_assignment_evidence_low_mastery_ratio,
        DISCUSSION_COMPLETE_MARKER=settings.discussion_complete_marker,
        GRADE_COUNT_CONF_THRESHOLD=settings.grade_count_conf_threshold,
        OCR_MAX_CONCURRENCY=settings.ocr_max_concurrency,
        LLM_MAX_CONCURRENCY=settings.llm_max_concurrency,
        LLM_MAX_CONCURRENCY_STUDENT=settings.llm_max_concurrency_student,
        LLM_MAX_CONCURRENCY_TEACHER=settings.llm_max_concurrency_teacher,
        CHAT_MAX_MESSAGES=settings.chat_max_messages,
        CHAT_MAX_MESSAGES_STUDENT=settings.chat_max_messages_student,
        CHAT_MAX_MESSAGES_TEACHER=settings.chat_max_messages_teacher,
        CHAT_MAX_MESSAGE_CHARS=settings.chat_max_message_chars,
        CHAT_EXTRA_SYSTEM_MAX_CHARS=settings.chat_extra_system_max_chars,
        CHAT_MAX_TOOL_ROUNDS=settings.chat_max_tool_rounds,
        CHAT_MAX_TOOL_CALLS=settings.chat_max_tool_calls,
        CHAT_STUDENT_INFLIGHT_LIMIT=settings.chat_student_inflight_limit,
        PROFILE_CACHE_TTL_SEC=settings.profile_cache_ttl_sec,
        ASSIGNMENT_DETAIL_CACHE_TTL_SEC=settings.assignment_detail_cache_ttl_sec,
        PROFILE_UPDATE_ASYNC=settings.profile_update_async,
        PROFILE_UPDATE_QUEUE_MAX=settings.profile_update_queue_max,
        _settings=settings,
    )


def _ensure_ocr_utils_path(path: Path) -> None:
    if path.exists() and str(path) not in sys.path:
        sys.path.insert(0, str(path))


_CONFIG_EXPORTS = tuple(ConfigValues.__dataclass_fields__.keys())
_DEFAULT_CONFIG: ConfigValues | None = None


def get_default_config() -> ConfigValues:
    global _DEFAULT_CONFIG
    if _DEFAULT_CONFIG is None:
        _DEFAULT_CONFIG = build_config(load_settings())
        _ensure_ocr_utils_path(_DEFAULT_CONFIG.OCR_UTILS_DIR)
    return _DEFAULT_CONFIG


def reset_default_config() -> None:
    global _DEFAULT_CONFIG
    _DEFAULT_CONFIG = None


# ---------------------------------------------------------------------------
# Teacher memory pattern constants
# ---------------------------------------------------------------------------

_TEACHER_MEMORY_DURABLE_INTENT_PATTERNS = [
    re.compile(p, re.I)
    for p in (
        r"(?:请|帮我)?记住",
        r"以后(?:都|默认|统一|请)",
        r"默认(?:按|用|采用|是)",
        r"长期(?:按|使用|采用)",
        r"固定(?:格式|风格|模板|流程|做法)",
        r"偏好(?:是|为|改为)",
        r"今后(?:都|统一|默认)",
    )
]
_TEACHER_MEMORY_TEMPORARY_HINT_PATTERNS = [
    re.compile(p, re.I)
    for p in (
        r"今天",
        r"本周",
        r"这次",
        r"临时",
        r"暂时",
        r"先按",
    )
]
_TEACHER_MEMORY_AUTO_INFER_STABLE_PATTERNS = [
    re.compile(p, re.I)
    for p in (
        r"(?:输出|回复|讲解|批改|反馈|总结)",
        r"(?:格式|结构|风格|模板|语气)",
        r"(?:结论|行动项|先.+再.+|条目|分点|markdown)",
        r"(?:难度|题量|时长|作业要求)",
    )
]
_TEACHER_MEMORY_AUTO_INFER_BLOCK_PATTERNS = [
    re.compile(p, re.I)
    for p in (
        r"(?:这道题|这题|本题|这个题)",
        r"(?:这次|本次|今天|临时|暂时)",
        r"(?:帮我解|请解答|算一下)",
    )
]

_TEACHER_MEMORY_SENSITIVE_PATTERNS = [
    re.compile(p, re.I)
    for p in (
        r"sk-[A-Za-z0-9]{16,}",
        r"AIza[0-9A-Za-z\\-_]{20,}",
        r"AKIA[0-9A-Z]{12,}",
        r"(?:api|access|secret|refresh)[-_ ]?(?:key|token)\s*[:=]\s*\S{6,}",
        r"password\s*[:=]\s*\S{4,}",
    )
]
_TEACHER_MEMORY_CONFLICT_GROUPS: List[Tuple[Tuple[str, ...], Tuple[str, ...]]] = [
    (("简洁", "精简", "简短"), ("详细", "展开", "长文")),
    (("中文", "汉语"), ("英文", "英语", "english")),
    (("先结论", "先总结"), ("先过程", "先推导", "先分析")),
    (("条目", "要点", "bullet"), ("段落", "叙述")),
]


def __getattr__(name: str) -> Any:
    if name in _CONFIG_EXPORTS:
        return getattr(get_default_config(), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "RuntimePaths",
    "ConfigValues",
    "build_paths",
    "build_config",
    "get_default_config",
    "reset_default_config",
    *_CONFIG_EXPORTS,
]
