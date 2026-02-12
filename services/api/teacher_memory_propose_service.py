from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Set

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class TeacherMemoryProposeDeps:
    ensure_teacher_workspace: Callable[[str], Any]
    proposal_path: Callable[[str, str], Any]
    atomic_write_json: Callable[[Any, Any], None]
    uuid_hex: Callable[[], str]
    now_iso: Callable[[], str]
    priority_score: Callable[..., int]
    record_ttl_days: Callable[[Dict[str, Any]], int]
    record_expire_at: Callable[[Dict[str, Any]], Any]
    auto_apply_enabled: bool
    auto_apply_targets: Set[str]
    apply: Callable[[str, str, bool], Dict[str, Any]]


def teacher_memory_propose(
    teacher_id: str,
    target: str,
    title: str,
    content: str,
    *,
    deps: TeacherMemoryProposeDeps,
    source: str = "manual",
    meta: Optional[Dict[str, Any]] = None,
    dedupe_key: Optional[str] = None,
) -> Dict[str, Any]:
    deps.ensure_teacher_workspace(teacher_id)
    proposal_id = f"tmem_{deps.uuid_hex()[:12]}"
    source_norm = str(source or "manual").strip().lower() or "manual"
    target_norm = str(target or "MEMORY").upper()
    created_at = deps.now_iso()
    priority_score = deps.priority_score(
        target=target_norm,
        title=(title or "").strip(),
        content=(content or "").strip(),
        source=source_norm,
        meta=meta if isinstance(meta, dict) else None,
    )
    ttl_days = deps.record_ttl_days({"target": target_norm, "source": source_norm, "meta": meta})
    record = {
        "proposal_id": proposal_id,
        "teacher_id": teacher_id,
        "target": target_norm,
        "title": (title or "").strip(),
        "content": (content or "").strip(),
        "source": source_norm,
        "priority_score": priority_score,
        "ttl_days": ttl_days,
        "status": "proposed",
        "created_at": created_at,
    }
    expire_at = deps.record_expire_at(record)
    if expire_at is not None:
        record["expires_at"] = expire_at.isoformat(timespec="seconds")
    if isinstance(meta, dict) and meta:
        record["meta"] = meta
    if dedupe_key:
        record["dedupe_key"] = str(dedupe_key).strip()[:120]
    path = deps.proposal_path(teacher_id, proposal_id)
    deps.atomic_write_json(path, record)

    if not deps.auto_apply_enabled:
        return {"ok": True, "proposal_id": proposal_id, "proposal": record}

    if target_norm not in deps.auto_apply_targets:
        stamp = deps.now_iso()
        record["status"] = "rejected"
        record["rejected_at"] = stamp
        record["reject_reason"] = "target_not_allowed_for_auto_apply"
        deps.atomic_write_json(path, record)
        return {
            "ok": False,
            "proposal_id": proposal_id,
            "status": "rejected",
            "error": "target_not_allowed_for_auto_apply",
            "proposal": record,
        }

    applied = deps.apply(teacher_id, proposal_id, True)
    if applied.get("error"):
        stamp = deps.now_iso()
        try:
            latest = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            _log.warning("failed to re-read proposal file for teacher=%s proposal=%s", teacher_id, proposal_id, exc_info=True)
            latest = record
        if not isinstance(latest, dict):
            latest = record
        latest["status"] = "rejected"
        latest["rejected_at"] = stamp
        latest["reject_reason"] = str(applied.get("error") or "auto_apply_failed")
        deps.atomic_write_json(path, latest)
        return {
            "ok": False,
            "proposal_id": proposal_id,
            "status": "rejected",
            "error": str(applied.get("error") or "auto_apply_failed"),
            "proposal": latest,
        }

    try:
        final_record = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        _log.warning("failed to re-read final proposal file for teacher=%s proposal=%s", teacher_id, proposal_id, exc_info=True)
        final_record = record
    return {
        "ok": True,
        "proposal_id": proposal_id,
        "status": str(applied.get("status") or "applied"),
        "auto_applied": True,
        "proposal": final_record if isinstance(final_record, dict) else record,
    }
