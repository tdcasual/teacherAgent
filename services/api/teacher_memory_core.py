"""Compatibility facade for teacher memory services.

This module keeps the historical public entry points stable while delegating
all default wiring to the dedicated service and deps modules.
"""
from __future__ import annotations

import importlib as _importlib
import os
from pathlib import Path
from typing import Any, Dict, Optional

from . import teacher_memory_deps as _teacher_memory_deps_module
from . import teacher_session_compaction_helpers as _compaction_helpers_module

if os.getenv("PYTEST_CURRENT_TEST"):
    _importlib.reload(_compaction_helpers_module)
    _importlib.reload(_teacher_memory_deps_module)

from .teacher_context_service import build_teacher_context as _build_teacher_context_impl
from .teacher_memory_apply_service import teacher_memory_apply as _teacher_memory_apply_impl
from .teacher_memory_auto_service import (
    teacher_memory_auto_flush_from_session as _teacher_memory_auto_flush_from_session_impl,
)
from .teacher_memory_auto_service import (
    teacher_memory_auto_propose_from_turn as _teacher_memory_auto_propose_from_turn_impl,
)
from .teacher_memory_deps import (
    _teacher_context_deps,
    _teacher_memory_apply_deps,
    _teacher_memory_auto_deps,
    _teacher_memory_insights_deps,
    _teacher_memory_propose_deps,
    _teacher_memory_search_deps,
    _teacher_memory_storage_deps,
    _teacher_session_compaction_deps,
    _teacher_workspace_deps,
)
from .teacher_memory_insights_service import (
    teacher_memory_insights as _teacher_memory_insights_impl,
)
from .teacher_memory_propose_service import teacher_memory_propose as _teacher_memory_propose_impl
from .teacher_memory_search_service import teacher_memory_search as _teacher_memory_search_impl
from .teacher_memory_storage_service import (
    teacher_memory_delete_proposal as _teacher_memory_delete_proposal_impl,
)
from .teacher_memory_storage_service import (
    teacher_memory_list_proposals as _teacher_memory_list_proposals_impl,
)
from .teacher_session_compaction_service import (
    maybe_compact_teacher_session as _maybe_compact_teacher_session_impl,
)
from .teacher_workspace_service import ensure_teacher_workspace as _ensure_teacher_workspace_impl
from .teacher_workspace_service import teacher_read_text as _teacher_read_text_impl

__all__ = [
    "ensure_teacher_workspace",
    "teacher_read_text",
    "maybe_compact_teacher_session",
    "teacher_build_context",
    "teacher_memory_search",
    "teacher_memory_list_proposals",
    "teacher_memory_insights",
    "teacher_memory_propose",
    "teacher_memory_apply",
    "teacher_memory_delete_proposal",
    "teacher_memory_auto_propose_from_turn",
    "teacher_memory_auto_flush_from_session",
]


def ensure_teacher_workspace(teacher_id: str) -> Path:
    return _ensure_teacher_workspace_impl(teacher_id, deps=_teacher_workspace_deps())


def teacher_read_text(path: Path, max_chars: int = 8000) -> str:
    return _teacher_read_text_impl(path, max_chars=max_chars)


def maybe_compact_teacher_session(teacher_id: str, session_id: str) -> Dict[str, Any]:
    return _maybe_compact_teacher_session_impl(
        teacher_id,
        session_id,
        deps=_teacher_session_compaction_deps(),
    )


def teacher_build_context(
    teacher_id: str,
    query: Optional[str] = None,
    max_chars: int = 6000,
    session_id: str = "main",
) -> str:
    return _build_teacher_context_impl(
        teacher_id,
        deps=_teacher_context_deps(),
        query=query,
        max_chars=max_chars,
        session_id=session_id,
    )


def teacher_memory_search(teacher_id: str, query: str, limit: int = 5) -> Dict[str, Any]:
    return _teacher_memory_search_impl(
        teacher_id,
        query,
        deps=_teacher_memory_search_deps(),
        limit=limit,
    )


def teacher_memory_list_proposals(
    teacher_id: str,
    status: Optional[str] = None,
    limit: int = 20,
) -> Dict[str, Any]:
    return _teacher_memory_list_proposals_impl(
        teacher_id,
        deps=_teacher_memory_storage_deps(),
        status=status,
        limit=limit,
    )


def teacher_memory_insights(teacher_id: str, days: int = 14) -> Dict[str, Any]:
    return _teacher_memory_insights_impl(
        teacher_id,
        deps=_teacher_memory_insights_deps(),
        days=days,
    )


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


def teacher_memory_delete_proposal(teacher_id: str, proposal_id: str) -> Dict[str, Any]:
    return _teacher_memory_delete_proposal_impl(
        teacher_id,
        proposal_id,
        deps=_teacher_memory_storage_deps(),
    )


def teacher_memory_auto_propose_from_turn(
    teacher_id: str,
    session_id: str,
    user_text: str,
    assistant_text: str,
    *,
    source: Optional[str] = None,
    provenance: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return _teacher_memory_auto_propose_from_turn_impl(
        teacher_id,
        session_id,
        user_text,
        assistant_text,
        source=source,
        provenance=provenance,
        deps=_teacher_memory_auto_deps(),
    )


def teacher_memory_auto_flush_from_session(
    teacher_id: str,
    session_id: str,
    *,
    source: Optional[str] = None,
    provenance: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return _teacher_memory_auto_flush_from_session_impl(
        teacher_id,
        session_id,
        source=source,
        provenance=provenance,
        deps=_teacher_memory_auto_deps(),
    )
