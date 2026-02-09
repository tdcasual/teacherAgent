from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import List, Tuple

from . import settings as _settings

APP_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(_settings.data_dir() or (APP_ROOT / "data"))
UPLOADS_DIR = Path(_settings.uploads_dir() or (APP_ROOT / "uploads"))
LLM_ROUTING_PATH = Path(_settings.llm_routing_path() or (DATA_DIR / "llm_routing.json"))
TENANT_ID = _settings.tenant_id()
JOB_QUEUE_BACKEND = _settings.job_queue_backend()
RQ_BACKEND_ENABLED = _settings.rq_backend_enabled()
REDIS_URL = _settings.redis_url()
RQ_QUEUE_NAME = _settings.rq_queue_name()

OCR_UTILS_DIR = APP_ROOT / "skills" / "physics-lesson-capture" / "scripts"
if OCR_UTILS_DIR.exists() and str(OCR_UTILS_DIR) not in sys.path:
    sys.path.insert(0, str(OCR_UTILS_DIR))

DIAG_LOG_ENABLED = _settings.diag_log_enabled()
DIAG_LOG_PATH = Path(_settings.diag_log_path() or (APP_ROOT / "tmp" / "diagnostics.log"))
UPLOAD_JOB_DIR = UPLOADS_DIR / "assignment_jobs"
EXAM_UPLOAD_JOB_DIR = UPLOADS_DIR / "exam_jobs"
CHAT_JOB_DIR = UPLOADS_DIR / "chat_jobs"
CHAT_WORKER_POOL_SIZE = _settings.chat_worker_pool_size()
CHAT_LANE_MAX_QUEUE = _settings.chat_lane_max_queue()
CHAT_LANE_DEBOUNCE_MS = _settings.chat_lane_debounce_ms()
CHAT_JOB_CLAIM_TTL_SEC = _settings.chat_job_claim_ttl_sec()
STUDENT_SESSIONS_DIR = DATA_DIR / "student_chat_sessions"
TEACHER_WORKSPACES_DIR = DATA_DIR / "teacher_workspaces"
TEACHER_SESSIONS_DIR = DATA_DIR / "teacher_chat_sessions"
STUDENT_SUBMISSIONS_DIR = DATA_DIR / "student_submissions"
SESSION_INDEX_MAX_ITEMS = _settings.session_index_max_items()
TEACHER_SESSION_COMPACT_ENABLED = _settings.teacher_session_compact_enabled()
TEACHER_SESSION_COMPACT_MAIN_ONLY = _settings.teacher_session_compact_main_only()
TEACHER_SESSION_COMPACT_MAX_MESSAGES = _settings.teacher_session_compact_max_messages()
TEACHER_SESSION_COMPACT_KEEP_TAIL = _settings.teacher_session_compact_keep_tail(
    TEACHER_SESSION_COMPACT_MAX_MESSAGES
)
TEACHER_SESSION_COMPACT_MIN_INTERVAL_SEC = _settings.teacher_session_compact_min_interval_sec()
TEACHER_SESSION_COMPACT_MAX_SOURCE_CHARS = _settings.teacher_session_compact_max_source_chars()
TEACHER_SESSION_CONTEXT_INCLUDE_SUMMARY = _settings.teacher_session_context_include_summary()
TEACHER_SESSION_CONTEXT_SUMMARY_MAX_CHARS = _settings.teacher_session_context_summary_max_chars()
TEACHER_MEMORY_AUTO_ENABLED = _settings.teacher_memory_auto_enabled()
TEACHER_MEMORY_AUTO_MIN_CONTENT_CHARS = _settings.teacher_memory_auto_min_content_chars()
TEACHER_MEMORY_AUTO_MAX_PROPOSALS_PER_DAY = _settings.teacher_memory_auto_max_proposals_per_day()
TEACHER_MEMORY_FLUSH_ENABLED = _settings.teacher_memory_flush_enabled()
TEACHER_MEMORY_FLUSH_MARGIN_MESSAGES = _settings.teacher_memory_flush_margin_messages()
TEACHER_MEMORY_FLUSH_MAX_SOURCE_CHARS = _settings.teacher_memory_flush_max_source_chars()
TEACHER_MEMORY_AUTO_APPLY_ENABLED = _settings.teacher_memory_auto_apply_enabled()
_TEACHER_MEMORY_AUTO_APPLY_TARGETS_RAW = _settings.teacher_memory_auto_apply_targets_raw()
TEACHER_MEMORY_AUTO_APPLY_TARGETS = {
    p.strip().upper()
    for p in _TEACHER_MEMORY_AUTO_APPLY_TARGETS_RAW.split(",")
    if str(p or "").strip()
}
if not TEACHER_MEMORY_AUTO_APPLY_TARGETS:
    TEACHER_MEMORY_AUTO_APPLY_TARGETS = {"DAILY", "MEMORY"}
TEACHER_MEMORY_AUTO_APPLY_STRICT = _settings.teacher_memory_auto_apply_strict()
TEACHER_MEMORY_AUTO_INFER_ENABLED = _settings.teacher_memory_auto_infer_enabled()
TEACHER_MEMORY_AUTO_INFER_MIN_REPEATS = _settings.teacher_memory_auto_infer_min_repeats()
TEACHER_MEMORY_AUTO_INFER_LOOKBACK_TURNS = _settings.teacher_memory_auto_infer_lookback_turns()
TEACHER_MEMORY_AUTO_INFER_MIN_CHARS = _settings.teacher_memory_auto_infer_min_chars()
TEACHER_MEMORY_AUTO_INFER_MIN_PRIORITY = _settings.teacher_memory_auto_infer_min_priority()
TEACHER_MEMORY_DECAY_ENABLED = _settings.teacher_memory_decay_enabled()
TEACHER_MEMORY_TTL_DAYS_MEMORY = _settings.teacher_memory_ttl_days_memory()
TEACHER_MEMORY_TTL_DAYS_DAILY = _settings.teacher_memory_ttl_days_daily()
TEACHER_MEMORY_CONTEXT_MAX_ENTRIES = _settings.teacher_memory_context_max_entries()
TEACHER_MEMORY_SEARCH_FILTER_EXPIRED = _settings.teacher_memory_search_filter_expired()
DISCUSSION_COMPLETE_MARKER = _settings.discussion_complete_marker()
GRADE_COUNT_CONF_THRESHOLD = _settings.grade_count_conf_threshold()
OCR_MAX_CONCURRENCY = _settings.ocr_max_concurrency()
LLM_MAX_CONCURRENCY = _settings.llm_max_concurrency()
LLM_MAX_CONCURRENCY_STUDENT = _settings.llm_max_concurrency_student(LLM_MAX_CONCURRENCY)
LLM_MAX_CONCURRENCY_TEACHER = _settings.llm_max_concurrency_teacher(LLM_MAX_CONCURRENCY)

CHAT_MAX_MESSAGES = _settings.chat_max_messages()
CHAT_MAX_MESSAGES_STUDENT = _settings.chat_max_messages_student(CHAT_MAX_MESSAGES)
CHAT_MAX_MESSAGES_TEACHER = _settings.chat_max_messages_teacher(CHAT_MAX_MESSAGES)
CHAT_MAX_MESSAGE_CHARS = _settings.chat_max_message_chars()
CHAT_EXTRA_SYSTEM_MAX_CHARS = _settings.chat_extra_system_max_chars()
CHAT_MAX_TOOL_ROUNDS = _settings.chat_max_tool_rounds()
CHAT_MAX_TOOL_CALLS = _settings.chat_max_tool_calls()
CHAT_STUDENT_INFLIGHT_LIMIT = _settings.chat_student_inflight_limit()

PROFILE_CACHE_TTL_SEC = _settings.profile_cache_ttl_sec()
ASSIGNMENT_DETAIL_CACHE_TTL_SEC = _settings.assignment_detail_cache_ttl_sec()

PROFILE_UPDATE_ASYNC = _settings.profile_update_async()
PROFILE_UPDATE_QUEUE_MAX = _settings.profile_update_queue_max()

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
