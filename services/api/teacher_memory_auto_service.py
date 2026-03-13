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


def _auto_candidate_context(
    teacher_id: str,
    session_id: str,
    text: str,
    assistant_text: str,
    *,
    source: Optional[str],
    provenance: Optional[Dict[str, Any]],
    deps: TeacherMemoryAutoDeps,
) -> Optional[Dict[str, Any]]:
    has_intent = any(p.search(text) for p in deps.durable_intent_patterns)
    inferred = None if has_intent else deps.auto_infer_candidate(teacher_id, session_id, text)
    if not has_intent and not inferred:
        return None
    if inferred:
        target = str(inferred.get("target") or "MEMORY").upper()
        content = str(inferred.get("content") or text[:1200]).strip()
        return {
            "target": target,
            "title": str(inferred.get("title") or "自动记忆：老师默认偏好"),
            "content": content,
            "source": "auto_infer",
            "dedupe_key": deps.stable_hash("auto_infer", teacher_id, target, deps.norm_text(content)),
            "meta": {
                "session_id": str(session_id or "main"),
                "trigger": str(inferred.get("trigger") or "implicit_repeated_preference"),
                "similar_hits": int(inferred.get("similar_hits") or 0),
                "user_text_preview": text[:160],
                "assistant_text_preview": str(assistant_text or "")[:160],
                "side_effect_source": str(source or "").strip(),
                "side_effect_provenance": provenance if isinstance(provenance, dict) else None,
            },
        }
    target = "DAILY" if any(p.search(text) for p in deps.temporary_hint_patterns) else "MEMORY"
    content = text[:1200].strip()
    return {
        "target": target,
        "title": "自动记忆：老师长期偏好" if target == "MEMORY" else "自动记录：老师临时偏好",
        "content": content,
        "source": "auto_intent",
        "dedupe_key": deps.stable_hash("auto_intent", teacher_id, target, deps.norm_text(content)),
        "meta": {
            "session_id": str(session_id or "main"),
            "trigger": "explicit_intent",
            "user_text_preview": text[:160],
            "assistant_text_preview": str(assistant_text or "")[:160],
            "side_effect_source": str(source or "").strip(),
            "side_effect_provenance": provenance if isinstance(provenance, dict) else None,
        },
    }


def _low_priority_inferred_result(
    teacher_id: str,
    session_id: str,
    text: str,
    *,
    target: str,
    priority_score: int,
    deps: TeacherMemoryAutoDeps,
) -> Dict[str, Any]:
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


def _load_session_dialog(path: Any) -> List[Dict[str, Any]]:
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
    return [r for r in records if str(r.get("role") or "") in {"user", "assistant"} and not bool(r.get("synthetic"))]


def _flush_cycle_no(teacher_id: str, session_id: str, *, deps: TeacherMemoryAutoDeps) -> Optional[int]:
    cycle_no = deps.session_compaction_cycle_no(teacher_id, session_id)
    idx = deps.session_index_item(teacher_id, session_id)
    try:
        flushed_cycle = int(idx.get("memory_flush_cycle") or 0)
    except Exception:
        _log.debug("numeric conversion failed", exc_info=True)
        flushed_cycle = 0
    return None if flushed_cycle >= cycle_no else cycle_no


def _flush_payload(
    teacher_id: str,
    session_id: str,
    dialog: List[Dict[str, Any]],
    cycle_no: int,
    *,
    source: Optional[str],
    provenance: Optional[Dict[str, Any]],
    deps: TeacherMemoryAutoDeps,
) -> Dict[str, Any]:
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
    return {
        "title": f"自动会话记要 {today}",
        "content": (
            f"- session_id: {session_id}\n"
            f"- trigger: near_compaction\n"
            f"- cycle: {cycle_no}\n"
            f"- dialog_messages: {len(dialog)}\n"
            f"- compact_threshold: {deps.session_compact_max_messages}\n\n"
            "### 近期对话摘录\n"
            f"{transcript}"
        )[:2400],
        "meta": {
            "session_id": str(session_id or "main"),
            "trigger": "near_compaction",
            "cycle": cycle_no,
            "dialog_messages": len(dialog),
            "compact_threshold": deps.session_compact_max_messages,
            "soft_margin_messages": deps.memory_flush_margin_messages,
            "side_effect_source": str(source or "").strip(),
            "side_effect_provenance": provenance if isinstance(provenance, dict) else None,
        },
        "dedupe_key": dedupe_key,
    }


def teacher_memory_auto_propose_from_turn(
    teacher_id: str,
    session_id: str,
    user_text: str,
    assistant_text: str,
    *,
    source: Optional[str] = None,
    provenance: Optional[Dict[str, Any]] = None,
    deps: TeacherMemoryAutoDeps,
) -> Dict[str, Any]:
    if not deps.auto_enabled:
        return {"ok": False, "reason": "disabled"}
    text = str(user_text or "").strip()
    if not text:
        return {"ok": False, "reason": "empty_user_text"}
    if len(deps.norm_text(text)) < deps.auto_min_content_chars:
        return {"ok": False, "reason": "too_short"}

    candidate = _auto_candidate_context(
        teacher_id,
        session_id,
        text,
        assistant_text,
        source=source,
        provenance=provenance,
        deps=deps,
    )
    if candidate is None:
        return {"ok": False, "reason": "no_intent"}
    if deps.auto_quota_reached(teacher_id):
        return {"ok": False, "reason": "daily_quota_reached"}

    target = str(candidate.get("target") or "MEMORY")
    title = str(candidate.get("title") or "")
    content = str(candidate.get("content") or "")
    source = str(candidate.get("source") or "")
    dedupe_key = str(candidate.get("dedupe_key") or "")
    meta = candidate.get("meta") if isinstance(candidate.get("meta"), dict) else {}
    priority_score = deps.priority_score(
        target=target,
        title=title,
        content=content,
        source=source,
        meta=meta,
    )
    if source == "auto_infer" and priority_score < deps.auto_infer_min_priority:
        return _low_priority_inferred_result(
            teacher_id,
            session_id,
            text,
            target=target,
            priority_score=priority_score,
            deps=deps,
        )

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
        "status": str(result.get("status") or "proposed"),
        "priority_score": priority_score,
    }


def teacher_memory_auto_flush_from_session(
    teacher_id: str,
    session_id: str,
    *,
    source: Optional[str] = None,
    provenance: Optional[Dict[str, Any]] = None,
    deps: TeacherMemoryAutoDeps,
) -> Dict[str, Any]:
    if not deps.auto_enabled or not deps.auto_flush_enabled:
        return {"ok": False, "reason": "disabled"}
    if not deps.session_compact_enabled:
        return {"ok": False, "reason": "compaction_disabled"}
    path = deps.teacher_session_file(teacher_id, session_id)
    if not path.exists():
        return {"ok": False, "reason": "session_not_found"}

    dialog = _load_session_dialog(path)
    threshold = max(1, deps.session_compact_max_messages - deps.memory_flush_margin_messages)
    if len(dialog) < threshold:
        return {"ok": False, "reason": "below_threshold", "messages": len(dialog), "threshold": threshold}
    if deps.auto_quota_reached(teacher_id):
        return {"ok": False, "reason": "daily_quota_reached"}

    cycle_no = _flush_cycle_no(teacher_id, session_id, deps=deps)
    if cycle_no is None:
        return {"ok": False, "reason": "already_flushed_cycle", "cycle": deps.session_compaction_cycle_no(teacher_id, session_id)}
    payload = _flush_payload(
        teacher_id,
        session_id,
        dialog,
        cycle_no,
        source=source,
        provenance=provenance,
        deps=deps,
    )
    if payload.get("reason") in {"duplicate", "empty_transcript"}:
        return payload

    result = deps.memory_propose(
        teacher_id,
        target="DAILY",
        title=str(payload.get("title") or ""),
        content=str(payload.get("content") or ""),
        source="auto_flush",
        meta=payload.get("meta") if isinstance(payload.get("meta"), dict) else {},
        dedupe_key=str(payload.get("dedupe_key") or ""),
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
        "status": str(result.get("status") or "proposed"),
        "cycle": cycle_no,
    }
