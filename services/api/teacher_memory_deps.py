"""Teacher memory deps builders extracted from teacher_memory_core.py.

All _*_deps() functions that wire service implementations to their
dependency containers.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from .config import (
    TEACHER_MEMORY_CONTEXT_MAX_ENTRIES,
    TEACHER_MEMORY_TTL_DAYS_DAILY,
    TEACHER_MEMORY_TTL_DAYS_MEMORY,
    TEACHER_MEMORY_DECAY_ENABLED,
    TEACHER_MEMORY_SEARCH_FILTER_EXPIRED,
    TEACHER_MEMORY_AUTO_APPLY_STRICT,
    TEACHER_MEMORY_AUTO_APPLY_ENABLED,
    TEACHER_MEMORY_AUTO_APPLY_TARGETS,
    TEACHER_MEMORY_AUTO_INFER_ENABLED,
    TEACHER_MEMORY_AUTO_INFER_MIN_CHARS,
    TEACHER_MEMORY_AUTO_INFER_LOOKBACK_TURNS,
    TEACHER_MEMORY_AUTO_INFER_MIN_REPEATS,
    TEACHER_MEMORY_AUTO_MAX_PROPOSALS_PER_DAY,
    TEACHER_MEMORY_AUTO_ENABLED,
    TEACHER_MEMORY_AUTO_MIN_CONTENT_CHARS,
    TEACHER_MEMORY_AUTO_INFER_MIN_PRIORITY,
    TEACHER_MEMORY_FLUSH_ENABLED,
    TEACHER_SESSION_COMPACT_ENABLED,
    TEACHER_SESSION_COMPACT_MAX_MESSAGES,
    TEACHER_MEMORY_FLUSH_MARGIN_MESSAGES,
    TEACHER_MEMORY_FLUSH_MAX_SOURCE_CHARS,
    TEACHER_SESSION_COMPACT_MAIN_ONLY,
    TEACHER_SESSION_COMPACT_KEEP_TAIL,
    CHAT_MAX_MESSAGES_TEACHER,
    SESSION_INDEX_MAX_ITEMS,
    _TEACHER_MEMORY_DURABLE_INTENT_PATTERNS,
    _TEACHER_MEMORY_TEMPORARY_HINT_PATTERNS,
    _TEACHER_MEMORY_AUTO_INFER_STABLE_PATTERNS,
    _TEACHER_MEMORY_AUTO_INFER_BLOCK_PATTERNS,
    _TEACHER_MEMORY_CONFLICT_GROUPS,
    TEACHER_SESSION_CONTEXT_INCLUDE_SUMMARY,
    TEACHER_SESSION_CONTEXT_SUMMARY_MAX_CHARS,
)
from .paths import (
    teacher_workspace_dir,
    teacher_workspace_file,
    teacher_session_file,
    teacher_daily_memory_dir,
    teacher_daily_memory_path,
)
from .session_store import (
    load_teacher_sessions_index,
    save_teacher_sessions_index,
)
from .job_repository import _atomic_write_json

from .teacher_session_compaction_service import TeacherSessionCompactionDeps
from .teacher_context_service import TeacherContextDeps
from .teacher_workspace_service import TeacherWorkspaceDeps
from .teacher_memory_api_service import TeacherMemoryApiDeps
from .teacher_memory_auto_service import TeacherMemoryAutoDeps
from .teacher_memory_apply_service import TeacherMemoryApplyDeps
from .teacher_memory_insights_service import TeacherMemoryInsightsDeps
from .teacher_memory_record_service import TeacherMemoryRecordDeps
from .teacher_memory_propose_service import TeacherMemoryProposeDeps
from .teacher_memory_search_service import TeacherMemorySearchDeps
from .teacher_memory_store_service import TeacherMemoryStoreDeps

__all__ = [
    "_teacher_workspace_deps",
    "_teacher_memory_search_deps",
    "_teacher_memory_insights_deps",
    "_teacher_memory_apply_deps",
    "_teacher_memory_propose_deps",
    "_teacher_memory_record_deps",
    "_teacher_memory_store_deps",
    "_teacher_memory_auto_deps",
    "_teacher_context_deps",
    "_teacher_session_compaction_deps",
    "_teacher_memory_api_deps",
]


def _app_core():
    from services.api import app_core as _mod
    return _mod


def _tmc():
    from . import teacher_memory_core as _mod
    return _mod


def _teacher_workspace_deps():
    return TeacherWorkspaceDeps(
        teacher_workspace_dir=teacher_workspace_dir,
        teacher_daily_memory_dir=teacher_daily_memory_dir,
    )


def _teacher_memory_search_deps():
    tmc = _tmc()
    return TeacherMemorySearchDeps(
        ensure_teacher_workspace=tmc.ensure_teacher_workspace,
        mem0_search=tmc._teacher_mem0_search,
        search_filter_expired=TEACHER_MEMORY_SEARCH_FILTER_EXPIRED,
        load_record=tmc._teacher_memory_load_record,
        is_expired_record=lambda rec: tmc._teacher_memory_is_expired_record(rec),
        diag_log=_app_core().diag_log,
        log_event=tmc._teacher_memory_log_event,
        teacher_workspace_file=teacher_workspace_file,
        teacher_daily_memory_dir=teacher_daily_memory_dir,
    )


def _teacher_memory_insights_deps():
    tmc = _tmc()
    return TeacherMemoryInsightsDeps(
        ensure_teacher_workspace=tmc.ensure_teacher_workspace,
        recent_proposals=lambda teacher_id, limit: tmc._teacher_memory_recent_proposals(teacher_id, limit=limit),
        is_expired_record=lambda rec, now: tmc._teacher_memory_is_expired_record(rec, now=now),
        priority_score=tmc._teacher_memory_priority_score,
        rank_score=tmc._teacher_memory_rank_score,
        age_days=lambda rec, now: tmc._teacher_memory_age_days(rec, now=now),
        load_events=lambda teacher_id, limit: tmc._teacher_memory_load_events(teacher_id, limit=limit),
        parse_dt=tmc._teacher_memory_parse_dt,
    )


def _teacher_memory_apply_deps():
    tmc = _tmc()
    return TeacherMemoryApplyDeps(
        proposal_path=tmc._teacher_proposal_path,
        atomic_write_json=_atomic_write_json,
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
        log_event=tmc._teacher_memory_log_event,
        is_sensitive=tmc._teacher_memory_is_sensitive,
        auto_apply_strict=TEACHER_MEMORY_AUTO_APPLY_STRICT,
        teacher_daily_memory_path=teacher_daily_memory_path,
        teacher_workspace_file=teacher_workspace_file,
        find_conflicting_applied=lambda teacher_id, proposal_id, target, content: tmc._teacher_memory_find_conflicting_applied(
            teacher_id,
            proposal_id=proposal_id,
            target=target,
            content=content,
        ),
        record_ttl_days=tmc._teacher_memory_record_ttl_days,
        record_expire_at=tmc._teacher_memory_record_expire_at,
        is_expired_record=tmc._teacher_memory_is_expired_record,
        mark_superseded=lambda teacher_id, proposal_ids, by_proposal_id: tmc._teacher_memory_mark_superseded(
            teacher_id,
            proposal_ids,
            by_proposal_id=by_proposal_id,
        ),
        diag_log=_app_core().diag_log,
        mem0_should_index_target=tmc._teacher_mem0_should_index_target,
        mem0_index_entry=tmc._teacher_mem0_index_entry,
    )


def _teacher_memory_propose_deps():
    tmc = _tmc()
    return TeacherMemoryProposeDeps(
        ensure_teacher_workspace=tmc.ensure_teacher_workspace,
        proposal_path=tmc._teacher_proposal_path,
        atomic_write_json=_atomic_write_json,
        uuid_hex=lambda: uuid.uuid4().hex,
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
        priority_score=tmc._teacher_memory_priority_score,
        record_ttl_days=tmc._teacher_memory_record_ttl_days,
        record_expire_at=tmc._teacher_memory_record_expire_at,
        auto_apply_enabled=TEACHER_MEMORY_AUTO_APPLY_ENABLED,
        auto_apply_targets=TEACHER_MEMORY_AUTO_APPLY_TARGETS,
        apply=lambda teacher_id, proposal_id, approve: tmc.teacher_memory_apply(
            teacher_id,
            proposal_id,
            approve=approve,
        ),
    )


def _teacher_memory_record_deps():
    tmc = _tmc()
    return TeacherMemoryRecordDeps(
        ensure_teacher_workspace=tmc.ensure_teacher_workspace,
        teacher_workspace_dir=teacher_workspace_dir,
        teacher_session_file=teacher_session_file,
        load_teacher_sessions_index=load_teacher_sessions_index,
        save_teacher_sessions_index=save_teacher_sessions_index,
        session_index_max_items=SESSION_INDEX_MAX_ITEMS,
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
        norm_text=tmc._teacher_memory_norm_text,
        loose_match=tmc._teacher_memory_loose_match,
        conflicts=tmc._teacher_memory_conflicts,
        auto_infer_enabled=TEACHER_MEMORY_AUTO_INFER_ENABLED,
        auto_infer_min_chars=TEACHER_MEMORY_AUTO_INFER_MIN_CHARS,
        auto_infer_block_patterns=_TEACHER_MEMORY_AUTO_INFER_BLOCK_PATTERNS,
        temporary_hint_patterns=_TEACHER_MEMORY_TEMPORARY_HINT_PATTERNS,
        auto_infer_stable_patterns=_TEACHER_MEMORY_AUTO_INFER_STABLE_PATTERNS,
        auto_infer_lookback_turns=TEACHER_MEMORY_AUTO_INFER_LOOKBACK_TURNS,
        auto_infer_min_repeats=TEACHER_MEMORY_AUTO_INFER_MIN_REPEATS,
        auto_max_proposals_per_day=TEACHER_MEMORY_AUTO_MAX_PROPOSALS_PER_DAY,
        proposal_path=tmc._teacher_proposal_path,
        atomic_write_json=_atomic_write_json,
    )


def _teacher_memory_store_deps():
    tmc = _tmc()
    return TeacherMemoryStoreDeps(
        teacher_workspace_dir=teacher_workspace_dir,
        proposal_path=tmc._teacher_proposal_path,
        recent_proposals=lambda teacher_id, limit: tmc._teacher_memory_recent_proposals(teacher_id, limit=limit),
        is_expired_record=lambda rec, now: tmc._teacher_memory_is_expired_record(rec, now=now),
        rank_score=tmc._teacher_memory_rank_score,
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
    )


def _teacher_memory_auto_deps():
    tmc = _tmc()
    return TeacherMemoryAutoDeps(
        auto_enabled=TEACHER_MEMORY_AUTO_ENABLED,
        auto_min_content_chars=TEACHER_MEMORY_AUTO_MIN_CONTENT_CHARS,
        auto_infer_min_priority=TEACHER_MEMORY_AUTO_INFER_MIN_PRIORITY,
        auto_flush_enabled=TEACHER_MEMORY_FLUSH_ENABLED,
        session_compact_enabled=TEACHER_SESSION_COMPACT_ENABLED,
        session_compact_max_messages=TEACHER_SESSION_COMPACT_MAX_MESSAGES,
        memory_flush_margin_messages=TEACHER_MEMORY_FLUSH_MARGIN_MESSAGES,
        memory_flush_max_source_chars=TEACHER_MEMORY_FLUSH_MAX_SOURCE_CHARS,
        durable_intent_patterns=_TEACHER_MEMORY_DURABLE_INTENT_PATTERNS,
        temporary_hint_patterns=_TEACHER_MEMORY_TEMPORARY_HINT_PATTERNS,
        norm_text=tmc._teacher_memory_norm_text,
        auto_infer_candidate=tmc._teacher_memory_auto_infer_candidate,
        auto_quota_reached=tmc._teacher_memory_auto_quota_reached,
        stable_hash=tmc._teacher_memory_stable_hash,
        priority_score=tmc._teacher_memory_priority_score,
        log_event=tmc._teacher_memory_log_event,
        find_duplicate=tmc._teacher_memory_find_duplicate,
        memory_propose=tmc.teacher_memory_propose,
        session_compaction_cycle_no=tmc._teacher_session_compaction_cycle_no,
        session_index_item=tmc._teacher_session_index_item,
        teacher_session_file=teacher_session_file,
        compact_transcript=tmc._teacher_compact_transcript,
        mark_session_memory_flush=tmc._mark_teacher_session_memory_flush,
    )


def _teacher_context_deps():
    tmc = _tmc()
    return TeacherContextDeps(
        ensure_teacher_workspace=tmc.ensure_teacher_workspace,
        teacher_read_text=tmc.teacher_read_text,
        teacher_workspace_file=teacher_workspace_file,
        teacher_memory_context_text=tmc._teacher_memory_context_text,
        include_session_summary=TEACHER_SESSION_CONTEXT_INCLUDE_SUMMARY,
        session_summary_max_chars=TEACHER_SESSION_CONTEXT_SUMMARY_MAX_CHARS,
        teacher_session_summary_text=tmc._teacher_session_summary_text,
        teacher_memory_log_event=tmc._teacher_memory_log_event,
    )


def _teacher_session_compaction_deps():
    tmc = _tmc()
    return TeacherSessionCompactionDeps(
        compact_enabled=TEACHER_SESSION_COMPACT_ENABLED,
        compact_main_only=TEACHER_SESSION_COMPACT_MAIN_ONLY,
        compact_max_messages=TEACHER_SESSION_COMPACT_MAX_MESSAGES,
        compact_keep_tail=TEACHER_SESSION_COMPACT_KEEP_TAIL,
        chat_max_messages_teacher=CHAT_MAX_MESSAGES_TEACHER,
        teacher_compact_allowed=tmc._teacher_compact_allowed,
        teacher_session_file=teacher_session_file,
        teacher_compact_summary=tmc._teacher_compact_summary,
        write_teacher_session_records=tmc._write_teacher_session_records,
        mark_teacher_session_compacted=tmc._mark_teacher_session_compacted,
        diag_log=_app_core().diag_log,
    )


def _teacher_memory_api_deps():
    tmc = _tmc()
    return TeacherMemoryApiDeps(
        resolve_teacher_id=_app_core().resolve_teacher_id,
        teacher_memory_list_proposals=tmc.teacher_memory_list_proposals,
        teacher_memory_apply=tmc.teacher_memory_apply,
    )
