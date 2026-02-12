"""Teacher memory and session compaction functions.

Extracted from app_core.py to reduce module size.
All public and underscore-prefixed names are re-exported by app_core.
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
import uuid
import importlib as _importlib
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Imports from already-extracted sibling modules
# ---------------------------------------------------------------------------
from .config import (
    TEACHER_SESSION_COMPACT_MIN_INTERVAL_SEC,
    TEACHER_SESSION_COMPACT_MAX_SOURCE_CHARS,
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
    _TEACHER_MEMORY_SENSITIVE_PATTERNS,
    _TEACHER_MEMORY_CONFLICT_GROUPS,
    TEACHER_SESSION_CONTEXT_INCLUDE_SUMMARY,
    TEACHER_SESSION_CONTEXT_SUMMARY_MAX_CHARS,
    DIAG_LOG_ENABLED,
)
from .paths import (
    safe_fs_id,
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

# ---------------------------------------------------------------------------
# Re-exports from extracted compaction helpers
# ---------------------------------------------------------------------------
from . import teacher_session_compaction_helpers as _compaction_helpers_module
if os.getenv("PYTEST_CURRENT_TEST"):
    _importlib.reload(_compaction_helpers_module)
from .teacher_session_compaction_helpers import *  # noqa: F401,F403
from .teacher_session_compaction_helpers import (
    _teacher_compact_key,
    _teacher_compact_allowed,
    _teacher_compact_transcript,
    _teacher_compact_summary,
    _write_teacher_session_records,
    _mark_teacher_session_compacted,
)

# ---------------------------------------------------------------------------
# Re-exports from extracted deps builders
# ---------------------------------------------------------------------------
from . import teacher_memory_deps as _teacher_memory_deps_module
if os.getenv("PYTEST_CURRENT_TEST"):
    _importlib.reload(_teacher_memory_deps_module)
from .teacher_memory_deps import *  # noqa: F401,F403
from .teacher_memory_deps import (
    _teacher_workspace_deps,
    _teacher_memory_search_deps,
    _teacher_memory_insights_deps,
    _teacher_memory_apply_deps,
    _teacher_memory_propose_deps,
    _teacher_memory_record_deps,
    _teacher_memory_store_deps,
    _teacher_memory_auto_deps,
    _teacher_context_deps,
    _teacher_session_compaction_deps,
    _teacher_memory_api_deps,
)

# ---------------------------------------------------------------------------
# Imports from service modules (implementation delegates)
# ---------------------------------------------------------------------------
from .teacher_session_compaction_service import (
    TeacherSessionCompactionDeps,
    maybe_compact_teacher_session as _maybe_compact_teacher_session_impl,
)
from .teacher_context_service import (
    TeacherContextDeps,
    build_teacher_context as _build_teacher_context_impl,
)
from .teacher_workspace_service import (
    TeacherWorkspaceDeps,
    ensure_teacher_workspace as _ensure_teacher_workspace_impl,
    teacher_read_text as _teacher_read_text_impl,
)
from .teacher_memory_api_service import (
    TeacherMemoryApiDeps,
    list_proposals_api as _list_teacher_memory_proposals_api_impl,
    review_proposal_api as _review_teacher_memory_proposal_api_impl,
)
from .teacher_memory_auto_service import (
    TeacherMemoryAutoDeps,
    teacher_memory_auto_flush_from_session as _teacher_memory_auto_flush_from_session_impl,
    teacher_memory_auto_propose_from_turn as _teacher_memory_auto_propose_from_turn_impl,
)
from .teacher_memory_apply_service import (
    TeacherMemoryApplyDeps,
    teacher_memory_apply as _teacher_memory_apply_impl,
)
from .teacher_memory_insights_service import (
    TeacherMemoryInsightsDeps,
    teacher_memory_insights as _teacher_memory_insights_impl,
)
from .teacher_memory_record_service import (
    TeacherMemoryRecordDeps,
    mark_teacher_session_memory_flush as _mark_teacher_session_memory_flush_impl,
    teacher_memory_auto_infer_candidate as _teacher_memory_auto_infer_candidate_impl,
    teacher_memory_auto_quota_reached as _teacher_memory_auto_quota_reached_impl,
    teacher_memory_find_conflicting_applied as _teacher_memory_find_conflicting_applied_impl,
    teacher_memory_find_duplicate as _teacher_memory_find_duplicate_impl,
    teacher_memory_mark_superseded as _teacher_memory_mark_superseded_impl,
    teacher_memory_recent_proposals as _teacher_memory_recent_proposals_impl,
    teacher_memory_recent_user_turns as _teacher_memory_recent_user_turns_impl,
    teacher_session_compaction_cycle_no as _teacher_session_compaction_cycle_no_impl,
    teacher_session_index_item as _teacher_session_index_item_impl,
)
from .teacher_memory_rules_service import (
    teacher_memory_age_days as _teacher_memory_age_days_impl,
    teacher_memory_conflicts as _teacher_memory_conflicts_impl,
    teacher_memory_has_term as _teacher_memory_has_term_impl,
    teacher_memory_is_expired_record as _teacher_memory_is_expired_record_impl,
    teacher_memory_is_sensitive as _teacher_memory_is_sensitive_impl,
    teacher_memory_loose_match as _teacher_memory_loose_match_impl,
    teacher_memory_norm_text as _teacher_memory_norm_text_impl,
    teacher_memory_parse_dt as _teacher_memory_parse_dt_impl,
    teacher_memory_priority_score as _teacher_memory_priority_score_impl,
    teacher_memory_rank_score as _teacher_memory_rank_score_impl,
    teacher_memory_record_expire_at as _teacher_memory_record_expire_at_impl,
    teacher_memory_record_ttl_days as _teacher_memory_record_ttl_days_impl,
    teacher_memory_stable_hash as _teacher_memory_stable_hash_impl,
)
from .teacher_memory_propose_service import (
    TeacherMemoryProposeDeps,
    teacher_memory_propose as _teacher_memory_propose_impl,
)
from .teacher_memory_search_service import (
    TeacherMemorySearchDeps,
    teacher_memory_search as _teacher_memory_search_impl,
)
from .teacher_memory_store_service import (
    TeacherMemoryStoreDeps,
    teacher_memory_active_applied_records as _teacher_memory_active_applied_records_impl,
    teacher_memory_event_log_path as _teacher_memory_event_log_path_impl,
    teacher_memory_load_events as _teacher_memory_load_events_impl,
    teacher_memory_load_record as _teacher_memory_load_record_impl,
    teacher_memory_log_event as _teacher_memory_log_event_impl,
)

# ---------------------------------------------------------------------------
# Lazy accessor for app_core functions that would cause circular imports
# ---------------------------------------------------------------------------
def _app_core():
    """Lazy import of app_core to avoid circular dependency (tenant-aware)."""
    from .wiring import get_app_core
    return get_app_core()


# ---------------------------------------------------------------------------
# Helper: ensure_teacher_workspace / teacher_read_text
# ---------------------------------------------------------------------------
def ensure_teacher_workspace(teacher_id: str) -> Path:
    return _ensure_teacher_workspace_impl(teacher_id, deps=_teacher_workspace_deps())


def teacher_read_text(path: Path, max_chars: int = 8000) -> str:
    return _teacher_read_text_impl(path, max_chars=max_chars)


# ===================================================================
# Teacher session compaction functions
# ===================================================================

def maybe_compact_teacher_session(teacher_id: str, session_id: str) -> Dict[str, Any]:
    return _maybe_compact_teacher_session_impl(
        teacher_id,
        session_id,
        deps=_teacher_session_compaction_deps(),
    )


# ===================================================================
# Teacher memory context functions
# ===================================================================

def _teacher_session_summary_text(teacher_id: str, session_id: str, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    try:
        path = teacher_session_file(teacher_id, session_id)
    except Exception:
        _log.debug("Failed to resolve session file path for teacher=%s session=%s", teacher_id, session_id)
        return ""
    try:
        with path.open("r", encoding="utf-8") as f:
            for _idx, line in zip(range(5), f):
                line = (line or "").strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    _log.debug("Skipping non-JSON line in session file %s", path)
                    continue
                if isinstance(obj, dict) and obj.get("kind") == "session_summary":
                    text = str(obj.get("content") or "").strip()
                    return (text[:max_chars] + "\u2026") if max_chars and len(text) > max_chars else text
                # If the first meaningful record isn't summary, don't scan the whole file.
                break
    except Exception:
        _log.warning("Failed to read session file %s for summary", path, exc_info=True)
        return ""
    return ""


def _teacher_memory_context_text(teacher_id: str, max_chars: int = 4000) -> str:
    if max_chars <= 0:
        return ""
    active = _teacher_memory_active_applied_records(
        teacher_id,
        target="MEMORY",
        limit=TEACHER_MEMORY_CONTEXT_MAX_ENTRIES,
    )
    if not active:
        return teacher_read_text(teacher_workspace_file(teacher_id, "MEMORY.md"), max_chars=max_chars).strip()

    lines: List[str] = []
    used = 0
    for rec in active:
        text = str(rec.get("content") or "").strip()
        if not text:
            continue
        brief = re.sub(r"\s+", " ", text).strip()[:240]
        score = int(round(_teacher_memory_rank_score(rec)))
        source = str(rec.get("source") or "manual")
        line = f"- [{source}|{score}] {brief}"
        if used + len(line) > max_chars:
            break
        lines.append(line)
        used += len(line) + 1
    return "\n".join(lines).strip()


def teacher_build_context(teacher_id: str, query: Optional[str] = None, max_chars: int = 6000, session_id: str = "main") -> str:
    return _build_teacher_context_impl(
        teacher_id,
        deps=_teacher_context_deps(),
        query=query,
        max_chars=max_chars,
        session_id=session_id,
    )


# ===================================================================
# Teacher memory search / list / insights
# ===================================================================

def teacher_memory_search(teacher_id: str, query: str, limit: int = 5) -> Dict[str, Any]:
    return _teacher_memory_search_impl(
        teacher_id,
        query,
        deps=_teacher_memory_search_deps(),
        limit=limit,
    )


def _teacher_proposal_path(teacher_id: str, proposal_id: str) -> Path:
    ensure_teacher_workspace(teacher_id)
    base = teacher_workspace_dir(teacher_id) / "proposals"
    return base / f"{safe_fs_id(proposal_id, prefix='proposal')}.json"


def teacher_memory_list_proposals(
    teacher_id: str,
    status: Optional[str] = None,
    limit: int = 20,
) -> Dict[str, Any]:
    ensure_teacher_workspace(teacher_id)
    proposals_dir = teacher_workspace_dir(teacher_id) / "proposals"
    proposals_dir.mkdir(parents=True, exist_ok=True)
    status_norm = (status or "").strip().lower() or None
    if status_norm and status_norm not in {"proposed", "applied", "rejected"}:
        return {"ok": False, "error": "invalid_status", "teacher_id": teacher_id}

    take = max(1, min(int(limit or 20), 200))

    def _safe_mtime(p: Path) -> float:
        try:
            return p.stat().st_mtime
        except OSError:
            return 0.0

    files = sorted(
        proposals_dir.glob("*.json"),
        key=_safe_mtime,
        reverse=True,
    )
    items: List[Dict[str, Any]] = []
    for path in files:
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            _log.warning("Failed to read proposal file %s", path, exc_info=True)
            continue
        if not isinstance(rec, dict):
            continue
        rec_status = str(rec.get("status") or "").strip().lower()
        if status_norm and rec_status != status_norm:
            continue
        if "proposal_id" not in rec:
            rec["proposal_id"] = path.stem
        items.append(rec)
        if len(items) >= take:
            break
    return {"ok": True, "teacher_id": teacher_id, "proposals": items}


def _teacher_memory_load_events(teacher_id: str, limit: int = 5000) -> List[Dict[str, Any]]:
    return _teacher_memory_load_events_impl(teacher_id, deps=_teacher_memory_store_deps(), limit=limit)


def teacher_memory_insights(teacher_id: str, days: int = 14) -> Dict[str, Any]:
    return _teacher_memory_insights_impl(
        teacher_id,
        deps=_teacher_memory_insights_deps(),
        days=days,
    )


# ===================================================================
# Teacher memory rules / utility functions
# ===================================================================

def _teacher_memory_is_sensitive(content: str) -> bool:
    return _teacher_memory_is_sensitive_impl(content, patterns=_TEACHER_MEMORY_SENSITIVE_PATTERNS)


def _teacher_memory_event_log_path(teacher_id: str) -> Path:
    return _teacher_memory_event_log_path_impl(teacher_id, deps=_teacher_memory_store_deps())


def _teacher_memory_log_event(teacher_id: str, event: str, payload: Optional[Dict[str, Any]] = None) -> None:
    _teacher_memory_log_event_impl(teacher_id, event, payload=payload, deps=_teacher_memory_store_deps())


def _teacher_memory_parse_dt(raw: Any) -> Optional[datetime]:
    return _teacher_memory_parse_dt_impl(raw)


def _teacher_memory_record_ttl_days(rec: Dict[str, Any]) -> int:
    return _teacher_memory_record_ttl_days_impl(
        rec,
        ttl_days_daily=TEACHER_MEMORY_TTL_DAYS_DAILY,
        ttl_days_memory=TEACHER_MEMORY_TTL_DAYS_MEMORY,
    )


def _teacher_memory_record_expire_at(rec: Dict[str, Any]) -> Optional[datetime]:
    return _teacher_memory_record_expire_at_impl(
        rec,
        parse_dt=_teacher_memory_parse_dt,
        record_ttl_days=_teacher_memory_record_ttl_days,
    )


def _teacher_memory_is_expired_record(rec: Dict[str, Any], now: Optional[datetime] = None) -> bool:
    return _teacher_memory_is_expired_record_impl(
        rec,
        decay_enabled=TEACHER_MEMORY_DECAY_ENABLED,
        record_expire_at=_teacher_memory_record_expire_at,
        now=now,
    )


def _teacher_memory_age_days(rec: Dict[str, Any], now: Optional[datetime] = None) -> int:
    return _teacher_memory_age_days_impl(rec, parse_dt=_teacher_memory_parse_dt, now=now)


def _teacher_memory_priority_score(
    *,
    target: str,
    title: str,
    content: str,
    source: str,
    meta: Optional[Dict[str, Any]] = None,
) -> int:
    return _teacher_memory_priority_score_impl(
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


def _teacher_memory_rank_score(rec: Dict[str, Any]) -> float:
    return _teacher_memory_rank_score_impl(
        rec,
        decay_enabled=TEACHER_MEMORY_DECAY_ENABLED,
        priority_score=_teacher_memory_priority_score,
        age_days=_teacher_memory_age_days,
        record_ttl_days=_teacher_memory_record_ttl_days,
    )


# ===================================================================
# Teacher memory record functions
# ===================================================================

def _teacher_memory_load_record(teacher_id: str, proposal_id: str) -> Optional[Dict[str, Any]]:
    return _teacher_memory_load_record_impl(teacher_id, proposal_id, deps=_teacher_memory_store_deps())


def _teacher_memory_active_applied_records(
    teacher_id: str,
    *,
    target: Optional[str] = None,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    return _teacher_memory_active_applied_records_impl(
        teacher_id,
        deps=_teacher_memory_store_deps(),
        target=target,
        limit=limit,
    )


def _teacher_memory_recent_user_turns(teacher_id: str, session_id: str, limit: int = 24) -> List[str]:
    return _teacher_memory_recent_user_turns_impl(teacher_id, session_id, deps=_teacher_memory_record_deps(), limit=limit)


def _teacher_memory_loose_match(a: str, b: str) -> bool:
    return _teacher_memory_loose_match_impl(a, b, norm_text=_teacher_memory_norm_text)


def _teacher_memory_auto_infer_candidate(teacher_id: str, session_id: str, user_text: str) -> Optional[Dict[str, Any]]:
    return _teacher_memory_auto_infer_candidate_impl(teacher_id, session_id, user_text, deps=_teacher_memory_record_deps())


def _teacher_session_index_item(teacher_id: str, session_id: str) -> Dict[str, Any]:
    return _teacher_session_index_item_impl(teacher_id, session_id, deps=_teacher_memory_record_deps())


def _mark_teacher_session_memory_flush(teacher_id: str, session_id: str, cycle_no: int) -> None:
    _mark_teacher_session_memory_flush_impl(teacher_id, session_id, cycle_no, deps=_teacher_memory_record_deps())


def _teacher_memory_has_term(text: str, terms: Tuple[str, ...]) -> bool:
    return _teacher_memory_has_term_impl(text, terms)


def _teacher_memory_conflicts(new_text: str, old_text: str) -> bool:
    return _teacher_memory_conflicts_impl(
        new_text,
        old_text,
        norm_text=_teacher_memory_norm_text,
        conflict_groups=_TEACHER_MEMORY_CONFLICT_GROUPS,
    )


def _teacher_memory_find_conflicting_applied(
    teacher_id: str,
    *,
    proposal_id: str,
    target: str,
    content: str,
) -> List[str]:
    return _teacher_memory_find_conflicting_applied_impl(
        teacher_id,
        proposal_id=proposal_id,
        target=target,
        content=content,
        deps=_teacher_memory_record_deps(),
    )


def _teacher_memory_mark_superseded(teacher_id: str, proposal_ids: List[str], by_proposal_id: str) -> None:
    _teacher_memory_mark_superseded_impl(teacher_id, proposal_ids, by_proposal_id, deps=_teacher_memory_record_deps())


# ===================================================================
# Teacher memory propose / apply
# ===================================================================

def teacher_memory_propose(
    teacher_id: str,
    target: str,
    title: str,
    content: str,
    *,
    source: str = "manual",
    meta: Optional[Dict[str, Any]] = None,
    dedupe_key: Optional[str] = None,
) -> Dict[str, Any]:
    return _teacher_memory_propose_impl(
        teacher_id,
        target,
        title,
        content,
        deps=_teacher_memory_propose_deps(),
        source=source,
        meta=meta,
        dedupe_key=dedupe_key,
    )


def teacher_memory_apply(teacher_id: str, proposal_id: str, approve: bool = True) -> Dict[str, Any]:
    return _teacher_memory_apply_impl(
        teacher_id,
        proposal_id,
        deps=_teacher_memory_apply_deps(),
        approve=approve,
    )


def _teacher_memory_norm_text(text: str) -> str:
    return _teacher_memory_norm_text_impl(text)


def _teacher_memory_stable_hash(*parts: str) -> str:
    return _teacher_memory_stable_hash_impl(*parts)


def _teacher_memory_recent_proposals(teacher_id: str, limit: int = 200) -> List[Dict[str, Any]]:
    return _teacher_memory_recent_proposals_impl(teacher_id, deps=_teacher_memory_record_deps(), limit=limit)


def _teacher_memory_auto_quota_reached(teacher_id: str) -> bool:
    return _teacher_memory_auto_quota_reached_impl(teacher_id, deps=_teacher_memory_record_deps())


def _teacher_memory_find_duplicate(
    teacher_id: str,
    *,
    target: str,
    content: str,
    dedupe_key: str,
) -> Optional[Dict[str, Any]]:
    return _teacher_memory_find_duplicate_impl(
        teacher_id,
        target=target,
        content=content,
        dedupe_key=dedupe_key,
        deps=_teacher_memory_record_deps(),
    )


def _teacher_session_compaction_cycle_no(teacher_id: str, session_id: str) -> int:
    return _teacher_session_compaction_cycle_no_impl(teacher_id, session_id, deps=_teacher_memory_record_deps())


# ===================================================================
# Teacher memory auto-propose / auto-flush
# ===================================================================

def teacher_memory_auto_propose_from_turn(
    teacher_id: str,
    session_id: str,
    user_text: str,
    assistant_text: str,
) -> Dict[str, Any]:
    return _teacher_memory_auto_propose_from_turn_impl(
        teacher_id,
        session_id,
        user_text,
        assistant_text,
        deps=_teacher_memory_auto_deps(),
    )


def teacher_memory_auto_flush_from_session(teacher_id: str, session_id: str) -> Dict[str, Any]:
    return _teacher_memory_auto_flush_from_session_impl(
        teacher_id,
        session_id,
        deps=_teacher_memory_auto_deps(),
    )


# ===================================================================
# Mem0 integration functions
# ===================================================================

def _teacher_mem0_search(teacher_id: str, query: str, limit: int) -> Dict[str, Any]:
    try:
        from .mem0_adapter import teacher_mem0_search
    except Exception:
        _log.warning("Failed to import mem0_adapter for search", exc_info=True)
        return {"ok": False, "matches": []}
    return teacher_mem0_search(teacher_id, query, limit=limit)


def _teacher_mem0_should_index_target(target: str) -> bool:
    try:
        from .mem0_adapter import teacher_mem0_should_index_target
    except Exception:
        _log.warning("Failed to import mem0_adapter for index target check", exc_info=True)
        return False
    try:
        return bool(teacher_mem0_should_index_target(target))
    except Exception:
        _log.warning("mem0 should_index_target call failed for target=%s", target, exc_info=True)
        return False


def _teacher_mem0_index_entry(teacher_id: str, text: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
    try:
        from .mem0_adapter import teacher_mem0_index_entry
    except Exception:
        _log.warning("Failed to import mem0_adapter for index entry", exc_info=True)
        return {"ok": False, "error": "mem0_unavailable"}
    return teacher_mem0_index_entry(teacher_id, text, metadata=metadata)
