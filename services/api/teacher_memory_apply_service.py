from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class TeacherMemoryApplyDeps:
    proposal_path: Callable[[str, str], Any]
    atomic_write_json: Callable[[Any, Any], None]
    now_iso: Callable[[], str]
    log_event: Callable[[str, str, Dict[str, Any]], None]
    is_sensitive: Callable[[str], bool]
    auto_apply_strict: bool
    teacher_daily_memory_path: Callable[[str], Any]
    teacher_workspace_file: Callable[[str, str], Any]
    find_conflicting_applied: Callable[[str, str, str, str], List[str]]
    record_ttl_days: Callable[[Dict[str, Any]], int]
    record_expire_at: Callable[[Dict[str, Any]], Any]
    is_expired_record: Callable[[Dict[str, Any]], bool]
    mark_superseded: Callable[[str, List[str], str], None]
    diag_log: Callable[[str, Dict[str, Any]], None]
    mem0_should_index_target: Callable[[str], bool]
    mem0_index_entry: Callable[[str, str, Dict[str, Any]], Dict[str, Any]]


@dataclass(frozen=True)
class _ApplyPayload:
    target: str
    title: str
    content: str
    source: str
    provenance: Dict[str, Any]


def _load_apply_record(path: Any) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        _log.warning("failed to read proposal file at %s", path, exc_info=True)
        return {}


def _proposal_payload(record: Dict[str, Any]) -> _ApplyPayload:
    source = str(record.get("source") or "manual").strip().lower() or "manual"
    provenance = record.get("provenance")
    if not isinstance(provenance, dict):
        provenance = {"layer": "memory_proposal", "source": source, "origin": "manual_input"}
    return _ApplyPayload(
        target=str(record.get("target") or "MEMORY").upper(),
        title=str(record.get("title") or "").strip(),
        content=str(record.get("content") or "").strip(),
        source=source,
        provenance=provenance,
    )


def _reject_record(
    *,
    teacher_id: str,
    proposal_id: str,
    path: Any,
    record: Dict[str, Any],
    deps: TeacherMemoryApplyDeps,
    target: str,
    source: str,
    reason: str,
    error: str | None = None,
) -> Dict[str, Any]:
    record["status"] = "rejected"
    record["rejected_at"] = deps.now_iso()
    if error:
        record["reject_reason"] = error
    deps.atomic_write_json(path, record)
    deps.log_event(
        teacher_id,
        "proposal_rejected",
        {
            "proposal_id": proposal_id,
            "target": target,
            "source": source,
            "reason": reason,
        },
    )
    if error:
        return {"error": error, "proposal_id": proposal_id}
    return {"ok": True, "proposal_id": proposal_id, "status": "rejected"}


def _resolve_apply_target_path(
    teacher_id: str,
    target: str,
    deps: TeacherMemoryApplyDeps,
) -> Any:
    if target == "DAILY":
        return deps.teacher_daily_memory_path(teacher_id)
    if target in {"MEMORY", "USER", "AGENTS", "SOUL", "HEARTBEAT"}:
        filename = f"{target}.md" if target != "MEMORY" else "MEMORY.md"
        return deps.teacher_workspace_file(teacher_id, filename)
    return deps.teacher_workspace_file(teacher_id, "MEMORY.md")


def _build_memory_entry(
    *,
    proposal_id: str,
    stamp: str,
    title: str,
    content: str,
    source: str,
    provenance: Dict[str, Any],
    supersedes: List[str],
) -> str:
    entry_lines = [f"## {title}".strip() if title else "## Memory Update"]
    entry_lines.append(f"- ts: {stamp}")
    entry_lines.append(f"- entry_id: {proposal_id}")
    entry_lines.append(f"- source: {source}")
    entry_lines.append(
        f"- provenance: {str(provenance.get('origin') or 'unknown')}:{str(provenance.get('source') or source)}"
    )
    if supersedes:
        entry_lines.append(f"- supersedes: {', '.join(supersedes)}")
    entry_lines.append("")
    entry_lines.append(content)
    return "\n".join(entry_lines).strip() + "\n\n"


def _append_memory_entry(out_path: Any, entry: str) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("a", encoding="utf-8") as file_handle:
        file_handle.write(entry)


def _maybe_index_mem0(
    *,
    teacher_id: str,
    proposal_id: str,
    out_path: Any,
    payload: _ApplyPayload,
    stamp: str,
    deps: TeacherMemoryApplyDeps,
) -> Optional[Dict[str, Any]]:
    try:
        if not deps.mem0_should_index_target(payload.target):
            return None
        index_text = f"{payload.title or 'Memory Update'}\n{payload.content}".strip()
        mem0_info = deps.mem0_index_entry(
            teacher_id,
            index_text,
            {
                "file": str(out_path),
                "proposal_id": proposal_id,
                "target": payload.target,
                "title": payload.title or "Memory Update",
                "source": payload.source,
                "ts": stamp,
            },
        )
        deps.diag_log(
            "teacher.mem0.index.done",
            {
                "teacher_id": teacher_id,
                "proposal_id": proposal_id,
                "ok": bool(mem0_info.get("ok") if isinstance(mem0_info, dict) else False),
            },
        )
        return mem0_info
    except Exception as exc:
        _log.debug("operation failed", exc_info=True)
        error = str(exc)[:200]
        deps.diag_log("teacher.mem0.index.crash", {"teacher_id": teacher_id, "proposal_id": proposal_id, "error": error})
        return {"ok": False, "error": error}


def _mark_record_applied(
    record: Dict[str, Any],
    *,
    out_path: Any,
    stamp: str,
    supersedes: List[str],
    deps: TeacherMemoryApplyDeps,
) -> int:
    record["status"] = "applied"
    record["applied_at"] = stamp
    record["applied_to"] = str(out_path)
    ttl_days = deps.record_ttl_days(record)
    record["ttl_days"] = ttl_days
    expire_at = deps.record_expire_at(record)
    if expire_at is not None:
        record["expires_at"] = expire_at.isoformat(timespec="seconds")
    else:
        record.pop("expires_at", None)
    if supersedes:
        record["supersedes"] = supersedes
    return ttl_days


def teacher_memory_apply(
    teacher_id: str,
    proposal_id: str,
    *,
    deps: TeacherMemoryApplyDeps,
    approve: bool = True,
) -> Dict[str, Any]:
    path = deps.proposal_path(teacher_id, proposal_id)
    if not path.exists():
        return {"error": "proposal not found", "proposal_id": proposal_id}

    record = _load_apply_record(path)
    status = str(record.get("status") or "proposed")
    if status in {"applied", "rejected"}:
        return {"ok": True, "proposal_id": proposal_id, "status": status, "detail": "already processed"}

    payload = _proposal_payload(record)
    if not approve:
        return _reject_record(
            teacher_id=teacher_id,
            proposal_id=proposal_id,
            path=path,
            record=record,
            deps=deps,
            target=payload.target,
            source=payload.source,
            reason="manual_reject",
        )
    if not payload.content:
        return {"error": "empty content", "proposal_id": proposal_id}
    if deps.auto_apply_strict and deps.is_sensitive(payload.content):
        return _reject_record(
            teacher_id=teacher_id,
            proposal_id=proposal_id,
            path=path,
            record=record,
            deps=deps,
            target=payload.target,
            source=payload.source,
            reason="sensitive_content_blocked",
            error="sensitive_content_blocked",
        )

    out_path = _resolve_apply_target_path(teacher_id, payload.target, deps)
    supersedes = deps.find_conflicting_applied(teacher_id, proposal_id, payload.target, payload.content)
    stamp = deps.now_iso()
    entry = _build_memory_entry(
        proposal_id=proposal_id,
        stamp=stamp,
        title=payload.title,
        content=payload.content,
        source=payload.source,
        provenance=payload.provenance,
        supersedes=supersedes,
    )
    _append_memory_entry(out_path, entry)
    ttl_days = _mark_record_applied(record, out_path=out_path, stamp=stamp, supersedes=supersedes, deps=deps)
    mem0_info = _maybe_index_mem0(
        teacher_id=teacher_id,
        proposal_id=proposal_id,
        out_path=out_path,
        payload=payload,
        stamp=stamp,
        deps=deps,
    )
    if mem0_info is not None:
        record["mem0"] = mem0_info

    deps.atomic_write_json(path, record)
    if supersedes:
        deps.mark_superseded(teacher_id, supersedes, proposal_id)
    deps.log_event(
        teacher_id,
        "proposal_applied",
        {
            "proposal_id": proposal_id,
            "target": payload.target,
            "source": payload.source,
            "priority_score": int(record.get("priority_score") or 0),
            "supersedes": len(supersedes),
            "ttl_days": ttl_days,
            "expired": bool(deps.is_expired_record(record)),
        },
    )
    out: Dict[str, Any] = {
        "ok": True,
        "proposal_id": proposal_id,
        "status": "applied",
        "applied_to": str(out_path),
        "provenance": payload.provenance,
    }
    if mem0_info is not None:
        out["mem0"] = mem0_info
    if supersedes:
        out["supersedes"] = supersedes
    return out
