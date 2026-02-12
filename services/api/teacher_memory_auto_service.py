from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Sequence

_log = logging.getLogger(__name__)



@dataclass(frozen=True)
class TeacherMemoryAutoDeps:
    auto_enabled: bool
    auto_min_content_chars: int
    auto_infer_min_priority: int
    auto_flush_enabled: bool
    session_compact_enabled: bool
    session_compact_max_messages: int
    memory_flush_margin_messages: int
    memory_flush_max_source_chars: int
    durable_intent_patterns: Sequence[Any]
    temporary_hint_patterns: Sequence[Any]
    norm_text: Callable[[str], str]
    auto_infer_candidate: Callable[[str, str, str], Optional[Dict[str, Any]]]
    auto_quota_reached: Callable[[str], bool]
    stable_hash: Callable[..., str]
    priority_score: Callable[..., int]
    log_event: Callable[[str, str, Dict[str, Any]], None]
    find_duplicate: Callable[..., Optional[Dict[str, Any]]]
    memory_propose: Callable[..., Dict[str, Any]]
    session_compaction_cycle_no: Callable[[str, str], int]
    session_index_item: Callable[[str, str], Dict[str, Any]]
    teacher_session_file: Callable[[str, str], Any]
    compact_transcript: Callable[[List[Dict[str, Any]], int], str]
    mark_session_memory_flush: Callable[[str, str, int], None]


def teacher_memory_auto_propose_from_turn(
    teacher_id: str,
    session_id: str,
    user_text: str,
    assistant_text: str,
    *,
    deps: TeacherMemoryAutoDeps,
) -> Dict[str, Any]:
    if not deps.auto_enabled:
        return {"ok": False, "reason": "disabled"}
    text = str(user_text or "").strip()
    if not text:
        return {"ok": False, "reason": "empty_user_text"}
    if len(deps.norm_text(text)) < deps.auto_min_content_chars:
        return {"ok": False, "reason": "too_short"}

    has_intent = any(p.search(text) for p in deps.durable_intent_patterns)
    inferred = None
    if not has_intent:
        inferred = deps.auto_infer_candidate(teacher_id, session_id, text)
        if not inferred:
            return {"ok": False, "reason": "no_intent"}
    if deps.auto_quota_reached(teacher_id):
        return {"ok": False, "reason": "daily_quota_reached"}

    if inferred:
        target = str(inferred.get("target") or "MEMORY").upper()
        title = str(inferred.get("title") or "自动记忆：老师默认偏好")
        content = str(inferred.get("content") or text[:1200]).strip()
        trigger = str(inferred.get("trigger") or "implicit_repeated_preference")
        source = "auto_infer"
        dedupe_key = deps.stable_hash("auto_infer", teacher_id, target, deps.norm_text(content))
        meta = {
            "session_id": str(session_id or "main"),
            "trigger": trigger,
            "similar_hits": int(inferred.get("similar_hits") or 0),
            "user_text_preview": text[:160],
            "assistant_text_preview": str(assistant_text or "")[:160],
        }
    else:
        target = "DAILY" if any(p.search(text) for p in deps.temporary_hint_patterns) else "MEMORY"
        content = text[:1200].strip()
        source = "auto_intent"
        title = "自动记忆：老师长期偏好" if target == "MEMORY" else "自动记录：老师临时偏好"
        dedupe_key = deps.stable_hash("auto_intent", teacher_id, target, deps.norm_text(content))
        meta = {
            "session_id": str(session_id or "main"),
            "trigger": "explicit_intent",
            "user_text_preview": text[:160],
            "assistant_text_preview": str(assistant_text or "")[:160],
        }
    priority_score = deps.priority_score(
        target=target,
        title=title,
        content=content,
        source=source,
        meta=meta,
    )
    if source == "auto_infer" and priority_score < deps.auto_infer_min_priority:
        deps.log_event(
            teacher_id,
            "auto_infer_skipped",
            {
                "session_id": str(session_id or "main"),
                "priority_score": priority_score,
                "min_priority": deps.auto_infer_min_priority,
                "query_preview": text[:120],
            },
        )
        return {
            "ok": False,
            "created": False,
            "target": target,
            "reason": "low_priority",
            "priority_score": priority_score,
            "min_priority": deps.auto_infer_min_priority,
        }

    dup = deps.find_duplicate(teacher_id, target=target, content=content, dedupe_key=dedupe_key)
    if dup:
        return {"ok": True, "created": False, "reason": "duplicate", "proposal_id": dup.get("proposal_id")}

    result = deps.memory_propose(
        teacher_id,
        target=target,
        title=title,
        content=content,
        source=source,
        meta=meta,
        dedupe_key=dedupe_key,
    )
    if not result.get("ok"):
        return {
            "ok": False,
            "created": False,
            "target": target,
            "proposal_id": result.get("proposal_id"),
            "reason": str(result.get("error") or "auto_apply_failed"),
        }
    return {
        "ok": True,
        "created": True,
        "target": target,
        "proposal_id": result.get("proposal_id"),
        "status": str(result.get("status") or "applied"),
        "priority_score": priority_score,
    }


def teacher_memory_auto_flush_from_session(
    teacher_id: str,
    session_id: str,
    *,
    deps: TeacherMemoryAutoDeps,
) -> Dict[str, Any]:
    if not deps.auto_enabled or not deps.auto_flush_enabled:
        return {"ok": False, "reason": "disabled"}
    if not deps.session_compact_enabled:
        return {"ok": False, "reason": "compaction_disabled"}
    path = deps.teacher_session_file(teacher_id, session_id)
    if not path.exists():
        return {"ok": False, "reason": "session_not_found"}

    records: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        text = (line or "").strip()
        if not text:
            continue
        try:
            rec = json.loads(text)
        except Exception:
            _log.debug("JSON parse failed", exc_info=True)
            continue
        if isinstance(rec, dict):
            records.append(rec)

    dialog = [r for r in records if str(r.get("role") or "") in {"user", "assistant"} and not bool(r.get("synthetic"))]
    threshold = max(1, deps.session_compact_max_messages - deps.memory_flush_margin_messages)
    if len(dialog) < threshold:
        return {"ok": False, "reason": "below_threshold", "messages": len(dialog), "threshold": threshold}
    if deps.auto_quota_reached(teacher_id):
        return {"ok": False, "reason": "daily_quota_reached"}

    cycle_no = deps.session_compaction_cycle_no(teacher_id, session_id)
    idx = deps.session_index_item(teacher_id, session_id)
    try:
        flushed_cycle = int(idx.get("memory_flush_cycle") or 0)
    except Exception:
        _log.debug("numeric conversion failed", exc_info=True)
        flushed_cycle = 0
    if flushed_cycle >= cycle_no:
        return {"ok": False, "reason": "already_flushed_cycle", "cycle": cycle_no}

    dedupe_key = deps.stable_hash("auto_flush", teacher_id, session_id, f"cycle_{cycle_no}")
    dup = deps.find_duplicate(
        teacher_id,
        target="DAILY",
        content=f"auto_flush:{session_id}:cycle_{cycle_no}",
        dedupe_key=dedupe_key,
    )
    if dup:
        return {"ok": True, "created": False, "reason": "duplicate", "proposal_id": dup.get("proposal_id")}

    tail = dialog[-min(12, len(dialog)) :]
    transcript = deps.compact_transcript(tail, deps.memory_flush_max_source_chars).strip()
    if not transcript:
        return {"ok": False, "reason": "empty_transcript"}

    today = datetime.now().date().isoformat()
    title = f"自动会话记要 {today}"
    content = (
        f"- session_id: {session_id}\n"
        f"- trigger: near_compaction\n"
        f"- cycle: {cycle_no}\n"
        f"- dialog_messages: {len(dialog)}\n"
        f"- compact_threshold: {deps.session_compact_max_messages}\n\n"
        "### 近期对话摘录\n"
        f"{transcript}"
    )
    result = deps.memory_propose(
        teacher_id,
        target="DAILY",
        title=title,
        content=content[:2400],
        source="auto_flush",
        meta={
            "session_id": str(session_id or "main"),
            "trigger": "near_compaction",
            "cycle": cycle_no,
            "dialog_messages": len(dialog),
            "compact_threshold": deps.session_compact_max_messages,
            "soft_margin_messages": deps.memory_flush_margin_messages,
        },
        dedupe_key=dedupe_key,
    )
    if not result.get("ok"):
        return {
            "ok": False,
            "created": False,
            "target": "DAILY",
            "proposal_id": result.get("proposal_id"),
            "reason": str(result.get("error") or "auto_apply_failed"),
        }
    deps.mark_session_memory_flush(teacher_id, session_id, cycle_no)
    return {
        "ok": True,
        "created": True,
        "target": "DAILY",
        "proposal_id": result.get("proposal_id"),
        "status": str(result.get("status") or "applied"),
        "cycle": cycle_no,
    }
