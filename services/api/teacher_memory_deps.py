"""Teacher memory deps builders extracted from teacher_memory_core.py.

All _*_deps() functions that wire service implementations to their
dependency containers.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from . import mem0_adapter
from .config import (
    _TEACHER_MEMORY_AUTO_INFER_BLOCK_PATTERNS,
    _TEACHER_MEMORY_AUTO_INFER_STABLE_PATTERNS,
    _TEACHER_MEMORY_CONFLICT_GROUPS,
    _TEACHER_MEMORY_DURABLE_INTENT_PATTERNS,
    _TEACHER_MEMORY_SENSITIVE_PATTERNS,
    _TEACHER_MEMORY_TEMPORARY_HINT_PATTERNS,
    CHAT_MAX_MESSAGES_TEACHER,
    SESSION_INDEX_MAX_ITEMS,
    TEACHER_MEMORY_AUTO_APPLY_ENABLED,
    TEACHER_MEMORY_AUTO_APPLY_STRICT,
    TEACHER_MEMORY_AUTO_APPLY_TARGETS,
    TEACHER_MEMORY_AUTO_ENABLED,
    TEACHER_MEMORY_AUTO_INFER_ENABLED,
    TEACHER_MEMORY_AUTO_INFER_LOOKBACK_TURNS,
    TEACHER_MEMORY_AUTO_INFER_MIN_CHARS,
    TEACHER_MEMORY_AUTO_INFER_MIN_PRIORITY,
    TEACHER_MEMORY_AUTO_INFER_MIN_REPEATS,
    TEACHER_MEMORY_AUTO_MAX_PROPOSALS_PER_DAY,
    TEACHER_MEMORY_AUTO_MIN_CONTENT_CHARS,
    TEACHER_MEMORY_CONTEXT_MAX_ENTRIES,
    TEACHER_MEMORY_DECAY_ENABLED,
    TEACHER_MEMORY_FLUSH_ENABLED,
    TEACHER_MEMORY_FLUSH_MARGIN_MESSAGES,
    TEACHER_MEMORY_FLUSH_MAX_SOURCE_CHARS,
    TEACHER_MEMORY_SEARCH_FILTER_EXPIRED,
    TEACHER_MEMORY_TTL_DAYS_DAILY,
    TEACHER_MEMORY_TTL_DAYS_MEMORY,
    TEACHER_SESSION_COMPACT_ENABLED,
    TEACHER_SESSION_COMPACT_KEEP_TAIL,
    TEACHER_SESSION_COMPACT_MAIN_ONLY,
    TEACHER_SESSION_COMPACT_MAX_MESSAGES,
    TEACHER_SESSION_CONTEXT_INCLUDE_SUMMARY,
    TEACHER_SESSION_CONTEXT_SUMMARY_MAX_CHARS,
)
from .job_repository import _atomic_write_json
from .paths import (
    safe_fs_id,
    teacher_daily_memory_dir,
    teacher_daily_memory_path,
    teacher_session_file,
    teacher_workspace_dir,
    teacher_workspace_file,
)
from .session_store import (
    load_teacher_sessions_index,
    save_teacher_sessions_index,
)
from .teacher_context_service import (
    TeacherContextDeps,
    build_teacher_memory_context_reader,
    build_teacher_session_summary_reader,
)
from .teacher_memory_apply_service import TeacherMemoryApplyDeps
from .teacher_memory_apply_service import teacher_memory_apply as teacher_memory_apply_impl
from .teacher_memory_auto_service import TeacherMemoryAutoDeps
from .teacher_memory_governance_service import TeacherMemoryGovernanceDeps
from .teacher_memory_insights_service import TeacherMemoryInsightsDeps
from .teacher_memory_propose_service import TeacherMemoryProposeDeps
from .teacher_memory_propose_service import teacher_memory_propose as teacher_memory_propose_impl
from .teacher_memory_record_service import (
    TeacherMemoryRecordDeps,
    teacher_memory_auto_infer_candidate,
    teacher_memory_auto_quota_reached,
    teacher_memory_find_conflicting_applied,
    teacher_memory_find_duplicate,
    teacher_memory_recent_proposals,
    teacher_session_compaction_cycle_no,
    teacher_session_index_item,
)
from .teacher_memory_record_service import (
    mark_teacher_session_memory_flush as teacher_memory_mark_session_flush,
)
from .teacher_memory_rules_service import (
    teacher_memory_age_days,
    teacher_memory_conflicts,
    teacher_memory_is_expired_record,
    teacher_memory_is_sensitive,
    teacher_memory_loose_match,
    teacher_memory_norm_text,
    teacher_memory_parse_dt,
    teacher_memory_priority_score,
    teacher_memory_rank_score,
    teacher_memory_record_expire_at,
    teacher_memory_record_ttl_days,
    teacher_memory_stable_hash,
)
from .teacher_memory_search_service import TeacherMemorySearchDeps
from .teacher_memory_storage_service import (
    TeacherMemoryStorageDeps,
    teacher_proposal_path,
)
from .teacher_memory_store_service import (
    TeacherMemoryStoreDeps,
    teacher_memory_active_applied_records,
    teacher_memory_load_events,
    teacher_memory_load_record,
    teacher_memory_log_event,
)
from .teacher_session_compaction_helpers import (
    _mark_teacher_session_compacted,
    _teacher_compact_allowed,
    _teacher_compact_summary,
    _teacher_compact_transcript,
    write_teacher_session_records,
)
from .teacher_session_compaction_service import TeacherSessionCompactionDeps
from .teacher_workspace_service import (
    TeacherWorkspaceDeps,
)
from .teacher_workspace_service import (
    ensure_teacher_workspace as ensure_teacher_workspace_impl,
)
from .teacher_workspace_service import (
    teacher_read_text as teacher_read_text_impl,
)

__all__ = [
    "_teacher_workspace_deps",
    "_teacher_memory_search_deps",
    "_teacher_memory_insights_deps",
    "_teacher_memory_apply_deps",
    "_teacher_memory_propose_deps",
    "_teacher_memory_record_deps",
    "_teacher_memory_governance_deps",
    "_teacher_memory_storage_deps",
    "_teacher_memory_store_deps",
    "_teacher_memory_auto_deps",
    "_teacher_context_deps",
    "_teacher_session_compaction_deps",
]


def _app_core():
    from .wiring import get_app_core
    return get_app_core()


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _teacher_memory_norm_text(text: str) -> str:
    return teacher_memory_norm_text(text)


def _teacher_memory_parse_dt(raw):
    return teacher_memory_parse_dt(raw)


def _teacher_memory_is_sensitive(text: str) -> bool:
    return teacher_memory_is_sensitive(text, patterns=_TEACHER_MEMORY_SENSITIVE_PATTERNS)


def _teacher_memory_record_ttl_days(rec):
    return teacher_memory_record_ttl_days(
        rec,
        ttl_days_daily=TEACHER_MEMORY_TTL_DAYS_DAILY,
        ttl_days_memory=TEACHER_MEMORY_TTL_DAYS_MEMORY,
    )


def _teacher_memory_record_expire_at(rec):
    return teacher_memory_record_expire_at(
        rec,
        parse_dt=_teacher_memory_parse_dt,
        record_ttl_days=_teacher_memory_record_ttl_days,
    )


def _teacher_memory_is_expired_record(rec, now=None):
    return teacher_memory_is_expired_record(
        rec,
        decay_enabled=TEACHER_MEMORY_DECAY_ENABLED,
        record_expire_at=_teacher_memory_record_expire_at,
        now=now,
    )


def _teacher_memory_age_days(rec, now=None):
    return teacher_memory_age_days(rec, parse_dt=_teacher_memory_parse_dt, now=now)


def _teacher_memory_priority_score(*, target, title, content, source, meta=None):
    return teacher_memory_priority_score(
        target=target,
        title=title,
        content=content,
        source=source,
        meta=meta,
        durable_intent_patterns=_TEACHER_MEMORY_DURABLE_INTENT_PATTERNS,
        auto_infer_stable_patterns=_TEACHER_MEMORY_AUTO_INFER_STABLE_PATTERNS,
        temporary_hint_patterns=_TEACHER_MEMORY_TEMPORARY_HINT_PATTERNS,
        is_sensitive=_teacher_memory_is_sensitive,
        norm_text=_teacher_memory_norm_text,
    )


def _teacher_memory_rank_score(rec):
    return teacher_memory_rank_score(
        rec,
        decay_enabled=TEACHER_MEMORY_DECAY_ENABLED,
        priority_score=_teacher_memory_priority_score,
        age_days=_teacher_memory_age_days,
        record_ttl_days=_teacher_memory_record_ttl_days,
    )


def _teacher_memory_loose_match(a: str, b: str) -> bool:
    return teacher_memory_loose_match(a, b, norm_text=_teacher_memory_norm_text)


def _teacher_memory_conflicts(new_text: str, old_text: str) -> bool:
    return teacher_memory_conflicts(
        new_text,
        old_text,
        norm_text=_teacher_memory_norm_text,
        conflict_groups=_TEACHER_MEMORY_CONFLICT_GROUPS,
    )


def _teacher_memory_stable_hash(*parts: str) -> str:
    return teacher_memory_stable_hash(*parts)


def _teacher_memory_log_event_bridge(
    teacher_id: str,
    event: str,
    payload: Optional[Dict[str, Any]] = None,
) -> None:
    teacher_memory_log_event(teacher_id, event, payload=payload, deps=_teacher_memory_store_deps())


def _teacher_proposal_path(teacher_id: str, proposal_id: str) -> Any:
    return teacher_proposal_path(teacher_id, proposal_id, deps=_teacher_memory_storage_deps())


def _teacher_memory_load_record(teacher_id: str, proposal_id: str) -> Optional[Dict[str, Any]]:
    return teacher_memory_load_record(teacher_id, proposal_id, deps=_teacher_memory_store_deps())


def _teacher_memory_load_events(teacher_id: str, limit: int = 5000) -> List[Dict[str, Any]]:
    return teacher_memory_load_events(teacher_id, deps=_teacher_memory_store_deps(), limit=limit)


def _teacher_memory_active_applied_records(
    teacher_id: str,
    *,
    target: Optional[str] = None,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    return teacher_memory_active_applied_records(teacher_id, deps=_teacher_memory_store_deps(), target=target, limit=limit)


def _teacher_memory_recent_proposals(teacher_id: str, limit: int = 200) -> List[Dict[str, Any]]:
    return teacher_memory_recent_proposals(teacher_id, deps=_teacher_memory_record_deps(), limit=limit)


def _teacher_memory_find_conflicting_applied(
    teacher_id: str,
    *,
    proposal_id: str,
    target: str,
    content: str,
) -> List[str]:
    return teacher_memory_find_conflicting_applied(
        teacher_id,
        proposal_id=proposal_id,
        target=target,
        content=content,
        deps=_teacher_memory_record_deps(),
    )


def _teacher_memory_mark_superseded(teacher_id: str, proposal_ids: List[str], by_proposal_id: str) -> None:
    from .teacher_memory_record_service import teacher_memory_mark_superseded

    teacher_memory_mark_superseded(teacher_id, proposal_ids, by_proposal_id, deps=_teacher_memory_record_deps())


def _teacher_memory_auto_quota_reached(teacher_id: str) -> bool:
    return teacher_memory_auto_quota_reached(teacher_id, deps=_teacher_memory_record_deps())


def _teacher_memory_find_duplicate(
    teacher_id: str,
    *,
    target: str,
    content: str,
    dedupe_key: str,
) -> Optional[Dict[str, Any]]:
    return teacher_memory_find_duplicate(
        teacher_id,
        target=target,
        content=content,
        dedupe_key=dedupe_key,
        deps=_teacher_memory_record_deps(),
    )


def _teacher_memory_auto_infer_candidate(
    teacher_id: str,
    session_id: str,
    user_text: str,
) -> Optional[Dict[str, Any]]:
    return teacher_memory_auto_infer_candidate(teacher_id, session_id, user_text, deps=_teacher_memory_record_deps())


def _teacher_session_index_item(teacher_id: str, session_id: str) -> Dict[str, Any]:
    return teacher_session_index_item(teacher_id, session_id, deps=_teacher_memory_record_deps())


def _mark_teacher_session_memory_flush(teacher_id: str, session_id: str, cycle_no: int) -> None:
    teacher_memory_mark_session_flush(teacher_id, session_id, cycle_no, deps=_teacher_memory_record_deps())


def _teacher_session_compaction_cycle_no(teacher_id: str, session_id: str) -> int:
    return teacher_session_compaction_cycle_no(teacher_id, session_id, deps=_teacher_memory_record_deps())


def _teacher_workspace_deps() -> TeacherWorkspaceDeps:
    return TeacherWorkspaceDeps(
        teacher_workspace_dir=teacher_workspace_dir,
        teacher_daily_memory_dir=teacher_daily_memory_dir,
    )


def _ensure_teacher_workspace(teacher_id: str) -> Any:
    return ensure_teacher_workspace_impl(teacher_id, deps=_teacher_workspace_deps())


def _teacher_memory_search_deps():
    return TeacherMemorySearchDeps(
        ensure_teacher_workspace=_ensure_teacher_workspace,
        mem0_search=mem0_adapter.teacher_mem0_search,
        search_filter_expired=TEACHER_MEMORY_SEARCH_FILTER_EXPIRED,
        load_record=_teacher_memory_load_record,
        is_expired_record=lambda rec: _teacher_memory_is_expired_record(rec),
        diag_log=_app_core().diag_log,
        log_event=_teacher_memory_log_event_bridge,
        teacher_workspace_file=teacher_workspace_file,
        teacher_daily_memory_dir=teacher_daily_memory_dir,
    )


def _teacher_memory_insights_deps():
    return TeacherMemoryInsightsDeps(
        ensure_teacher_workspace=_ensure_teacher_workspace,
        recent_proposals=lambda teacher_id, limit: _teacher_memory_recent_proposals(teacher_id, limit=limit),
        is_expired_record=lambda rec, now: _teacher_memory_is_expired_record(rec, now=now),
        priority_score=_teacher_memory_priority_score,
        rank_score=_teacher_memory_rank_score,
        age_days=lambda rec, now: _teacher_memory_age_days(rec, now=now),
        load_events=lambda teacher_id, limit: _teacher_memory_load_events(teacher_id, limit=limit),
        parse_dt=_teacher_memory_parse_dt,
    )


def _teacher_memory_apply_deps():
    return TeacherMemoryApplyDeps(
        proposal_path=_teacher_proposal_path,
        atomic_write_json=_atomic_write_json,
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
        log_event=_teacher_memory_log_event_bridge,
        is_sensitive=_teacher_memory_is_sensitive,
        auto_apply_strict=TEACHER_MEMORY_AUTO_APPLY_STRICT,
        teacher_daily_memory_path=teacher_daily_memory_path,
        teacher_workspace_file=teacher_workspace_file,
        find_conflicting_applied=lambda teacher_id, proposal_id, target, content: _teacher_memory_find_conflicting_applied(
            teacher_id,
            proposal_id=proposal_id,
            target=target,
            content=content,
        ),
        record_ttl_days=_teacher_memory_record_ttl_days,
        record_expire_at=_teacher_memory_record_expire_at,
        is_expired_record=_teacher_memory_is_expired_record,
        mark_superseded=lambda teacher_id, proposal_ids, by_proposal_id: _teacher_memory_mark_superseded(
            teacher_id,
            proposal_ids,
            by_proposal_id=by_proposal_id,
        ),
        diag_log=_app_core().diag_log,
        mem0_should_index_target=mem0_adapter.teacher_mem0_should_index_target,
        mem0_index_entry=mem0_adapter.teacher_mem0_index_entry,
    )


def _teacher_memory_propose_deps():
    return TeacherMemoryProposeDeps(
        ensure_teacher_workspace=_ensure_teacher_workspace,
        proposal_path=_teacher_proposal_path,
        atomic_write_json=_atomic_write_json,
        uuid_hex=lambda: uuid.uuid4().hex,
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
        priority_score=_teacher_memory_priority_score,
        record_ttl_days=_teacher_memory_record_ttl_days,
        record_expire_at=_teacher_memory_record_expire_at,
        auto_apply_enabled=TEACHER_MEMORY_AUTO_APPLY_ENABLED,
        auto_apply_targets=TEACHER_MEMORY_AUTO_APPLY_TARGETS,
        apply=lambda teacher_id, proposal_id, approve: teacher_memory_apply_impl(
            teacher_id,
            proposal_id,
            deps=_teacher_memory_apply_deps(),
            approve=approve,
        ),
    )


def _teacher_memory_record_deps():
    return TeacherMemoryRecordDeps(
        ensure_teacher_workspace=_ensure_teacher_workspace,
        teacher_workspace_dir=teacher_workspace_dir,
        teacher_session_file=teacher_session_file,
        load_teacher_sessions_index=load_teacher_sessions_index,
        save_teacher_sessions_index=save_teacher_sessions_index,
        session_index_max_items=SESSION_INDEX_MAX_ITEMS,
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
        norm_text=_teacher_memory_norm_text,
        loose_match=_teacher_memory_loose_match,
        conflicts=_teacher_memory_conflicts,
        auto_infer_enabled=TEACHER_MEMORY_AUTO_INFER_ENABLED,
        auto_infer_min_chars=TEACHER_MEMORY_AUTO_INFER_MIN_CHARS,
        auto_infer_block_patterns=_TEACHER_MEMORY_AUTO_INFER_BLOCK_PATTERNS,
        temporary_hint_patterns=_TEACHER_MEMORY_TEMPORARY_HINT_PATTERNS,
        auto_infer_stable_patterns=_TEACHER_MEMORY_AUTO_INFER_STABLE_PATTERNS,
        auto_infer_lookback_turns=TEACHER_MEMORY_AUTO_INFER_LOOKBACK_TURNS,
        auto_infer_min_repeats=TEACHER_MEMORY_AUTO_INFER_MIN_REPEATS,
        auto_max_proposals_per_day=TEACHER_MEMORY_AUTO_MAX_PROPOSALS_PER_DAY,
        proposal_path=_teacher_proposal_path,
        atomic_write_json=_atomic_write_json,
    )


def _teacher_memory_store_deps():
    return TeacherMemoryStoreDeps(
        teacher_workspace_dir=teacher_workspace_dir,
        proposal_path=_teacher_proposal_path,
        recent_proposals=lambda teacher_id, limit: _teacher_memory_recent_proposals(teacher_id, limit=limit),
        is_expired_record=lambda rec, now: _teacher_memory_is_expired_record(rec, now=now),
        rank_score=_teacher_memory_rank_score,
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
    )


def _teacher_memory_governance_deps():
    return TeacherMemoryGovernanceDeps(
        recent_proposals=lambda teacher_id, limit: _teacher_memory_recent_proposals(teacher_id, limit=limit),
        norm_text=_teacher_memory_norm_text,
        conflicts=_teacher_memory_conflicts,
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
        proposal_path=_teacher_proposal_path,
        atomic_write_json=_atomic_write_json,
        auto_max_proposals_per_day=TEACHER_MEMORY_AUTO_MAX_PROPOSALS_PER_DAY,
    )


def _teacher_memory_storage_deps():
    return TeacherMemoryStorageDeps(
        ensure_teacher_workspace=_ensure_teacher_workspace,
        teacher_workspace_dir=teacher_workspace_dir,
        safe_fs_id=safe_fs_id,
        atomic_write_json=_atomic_write_json,
        now_iso=lambda: datetime.now().isoformat(timespec="seconds"),
        teacher_daily_memory_path=teacher_daily_memory_path,
        teacher_workspace_file=teacher_workspace_file,
        log_event=_teacher_memory_log_event_bridge,
    )


def _teacher_memory_auto_deps():
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
        norm_text=_teacher_memory_norm_text,
        auto_infer_candidate=_teacher_memory_auto_infer_candidate,
        auto_quota_reached=_teacher_memory_auto_quota_reached,
        stable_hash=_teacher_memory_stable_hash,
        priority_score=_teacher_memory_priority_score,
        log_event=_teacher_memory_log_event_bridge,
        find_duplicate=_teacher_memory_find_duplicate,
        memory_propose=lambda teacher_id, target, title, content, source="manual", meta=None, dedupe_key=None: teacher_memory_propose_impl(
            teacher_id,
            target,
            title,
            content,
            deps=_teacher_memory_propose_deps(),
            source=source,
            meta=meta,
            dedupe_key=dedupe_key,
        ),
        session_compaction_cycle_no=_teacher_session_compaction_cycle_no,
        session_index_item=_teacher_session_index_item,
        teacher_session_file=teacher_session_file,
        compact_transcript=_teacher_compact_transcript,
        mark_session_memory_flush=_mark_teacher_session_memory_flush,
    )


def _teacher_context_deps():
    return TeacherContextDeps(
        ensure_teacher_workspace=_ensure_teacher_workspace,
        teacher_read_text=teacher_read_text_impl,
        teacher_workspace_file=teacher_workspace_file,
        teacher_memory_context_text=build_teacher_memory_context_reader(
            teacher_memory_active_applied_records=_teacher_memory_active_applied_records,
            teacher_read_text=teacher_read_text_impl,
            teacher_workspace_file=teacher_workspace_file,
            teacher_memory_rank_score=_teacher_memory_rank_score,
            teacher_memory_context_max_entries=TEACHER_MEMORY_CONTEXT_MAX_ENTRIES,
        ),
        include_session_summary=TEACHER_SESSION_CONTEXT_INCLUDE_SUMMARY,
        session_summary_max_chars=TEACHER_SESSION_CONTEXT_SUMMARY_MAX_CHARS,
        teacher_session_summary_text=build_teacher_session_summary_reader(
            teacher_session_file=teacher_session_file,
        ),
        teacher_memory_log_event=_teacher_memory_log_event_bridge,
    )


def _teacher_session_compaction_deps():
    return TeacherSessionCompactionDeps(
        compact_enabled=TEACHER_SESSION_COMPACT_ENABLED,
        compact_main_only=TEACHER_SESSION_COMPACT_MAIN_ONLY,
        compact_max_messages=TEACHER_SESSION_COMPACT_MAX_MESSAGES,
        compact_keep_tail=TEACHER_SESSION_COMPACT_KEEP_TAIL,
        chat_max_messages_teacher=CHAT_MAX_MESSAGES_TEACHER,
        teacher_compact_allowed=_teacher_compact_allowed,
        teacher_session_file=teacher_session_file,
        teacher_compact_summary=_teacher_compact_summary,
        write_teacher_session_records=write_teacher_session_records,
        mark_teacher_session_compacted=_mark_teacher_session_compacted,
        diag_log=_app_core().diag_log,
    )
