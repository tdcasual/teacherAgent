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
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        _log.warning("failed to read proposal file for teacher=%s proposal=%s", teacher_id, proposal_id, exc_info=True)
        record = {}
    status = str(record.get("status") or "proposed")
    if status in {"applied", "rejected"}:
        return {"ok": True, "proposal_id": proposal_id, "status": status, "detail": "already processed"}

    if not approve:
        record["status"] = "rejected"
        record["rejected_at"] = deps.now_iso()
        deps.atomic_write_json(path, record)
        deps.log_event(
            teacher_id,
            "proposal_rejected",
            {
                "proposal_id": proposal_id,
                "target": str(record.get("target") or "MEMORY"),
                "source": str(record.get("source") or "manual"),
                "reason": "manual_reject",
            },
        )
        return {"ok": True, "proposal_id": proposal_id, "status": "rejected"}

    target = str(record.get("target") or "MEMORY").upper()
    title = str(record.get("title") or "").strip()
    content = str(record.get("content") or "").strip()
    source = str(record.get("source") or "manual").strip().lower() or "manual"
    if not content:
        return {"error": "empty content", "proposal_id": proposal_id}
    if deps.auto_apply_strict and deps.is_sensitive(content):
        record["status"] = "rejected"
        record["rejected_at"] = deps.now_iso()
        record["reject_reason"] = "sensitive_content_blocked"
        deps.atomic_write_json(path, record)
        deps.log_event(
            teacher_id,
            "proposal_rejected",
            {
                "proposal_id": proposal_id,
                "target": target,
                "source": source,
                "reason": "sensitive_content_blocked",
            },
        )
        return {"error": "sensitive_content_blocked", "proposal_id": proposal_id}

    if target == "DAILY":
        out_path = deps.teacher_daily_memory_path(teacher_id)
    elif target in {"MEMORY", "USER", "AGENTS", "SOUL", "HEARTBEAT"}:
        out_path = deps.teacher_workspace_file(teacher_id, f"{target}.md" if target != "MEMORY" else "MEMORY.md")
    else:
        out_path = deps.teacher_workspace_file(teacher_id, "MEMORY.md")

    supersedes = deps.find_conflicting_applied(teacher_id, proposal_id, target, content)
    stamp = deps.now_iso()
    entry_lines = []
    if title:
        entry_lines.append(f"## {title}".strip())
    else:
        entry_lines.append("## Memory Update")
    entry_lines.append(f"- ts: {stamp}")
    entry_lines.append(f"- entry_id: {proposal_id}")
    entry_lines.append(f"- source: {source}")
    if supersedes:
        entry_lines.append(f"- supersedes: {', '.join(supersedes)}")
    entry_lines.append("")
    entry_lines.append(content)
    entry = "\n".join(entry_lines).strip() + "\n\n"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("a", encoding="utf-8") as f:
        f.write(entry)

    record["status"] = "applied"
    record["applied_at"] = stamp
    record["applied_to"] = str(out_path)
    record["ttl_days"] = deps.record_ttl_days(record)
    expire_at = deps.record_expire_at(record)
    if expire_at is not None:
        record["expires_at"] = expire_at.isoformat(timespec="seconds")
    else:
        record.pop("expires_at", None)
    if supersedes:
        record["supersedes"] = supersedes

    mem0_info: Optional[Dict[str, Any]] = None
    try:
        if deps.mem0_should_index_target(target):
            index_text = f"{title or 'Memory Update'}\n{content}".strip()
            mem0_info = deps.mem0_index_entry(
                teacher_id,
                index_text,
                {
                    "file": str(out_path),
                    "proposal_id": proposal_id,
                    "target": target,
                    "title": title or "Memory Update",
                    "source": source,
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
    except Exception as exc:
        mem0_info = {"ok": False, "error": str(exc)[:200]}
        deps.diag_log("teacher.mem0.index.crash", {"teacher_id": teacher_id, "proposal_id": proposal_id, "error": str(exc)[:200]})

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
            "target": target,
            "source": source,
            "priority_score": int(record.get("priority_score") or 0),
            "supersedes": len(supersedes),
            "ttl_days": deps.record_ttl_days(record),
            "expired": bool(deps.is_expired_record(record)),
        },
    )
    out: Dict[str, Any] = {"ok": True, "proposal_id": proposal_id, "status": "applied", "applied_to": str(out_path)}
    if mem0_info is not None:
        out["mem0"] = mem0_info
    if supersedes:
        out["supersedes"] = supersedes
    return out
