from __future__ import annotations

import contextvars
import hashlib
import hmac
import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from .auth_service import AuthError, auth_required, require_principal
from .config import get_default_config
from .fs_atomic import atomic_write_json

_log = logging.getLogger(__name__)

CONFIRM_TTL_SEC = 300
CONFIRMATION_REQUIRED = "confirmation_required"
MUTATING_TOOL_NAMES = frozenset(
    {
        "student.profile.update",
        "student.import",
        "assignment.generate",
        "assignment.render",
        "assignment.requirements.save",
        "assignment.publish",
        "assignment.archive",
        "assignment.unarchive",
        "assignment.recompute_roster",
        "lesson.capture",
        "core_example.register",
        "teacher.memory.apply",
        "chart.exec",
        "chart.agent.run",
    }
)


@dataclass(frozen=True)
class ToolConfirmContext:
    actor_id: str = ""
    job_id: str = ""
    lane_id: str = ""
    tool_call_id: str = ""
    role: str = ""
    skill_id: str = ""
    teacher_id: str = ""


_CONFIRM_CTX: contextvars.ContextVar[Optional[ToolConfirmContext]] = contextvars.ContextVar(
    "tool_confirm_ctx",
    default=None,
)


def bind_tool_confirm_context(**kwargs: Any) -> Any:
    current = _CONFIRM_CTX.get() or ToolConfirmContext()
    updated = ToolConfirmContext(
        actor_id=str(kwargs["actor_id"] if "actor_id" in kwargs else current.actor_id or ""),
        job_id=str(kwargs["job_id"] if "job_id" in kwargs else current.job_id or ""),
        lane_id=str(kwargs["lane_id"] if "lane_id" in kwargs else current.lane_id or ""),
        tool_call_id=str(kwargs["tool_call_id"] if "tool_call_id" in kwargs else current.tool_call_id or ""),
        role=str(kwargs["role"] if "role" in kwargs else current.role or ""),
        skill_id=str(kwargs["skill_id"] if "skill_id" in kwargs else current.skill_id or ""),
        teacher_id=str(kwargs["teacher_id"] if "teacher_id" in kwargs else current.teacher_id or ""),
    )
    return _CONFIRM_CTX.set(updated)


def reset_tool_confirm_context(token: Any) -> None:
    if token is None:
        return
    _CONFIRM_CTX.reset(token)


def current_tool_confirm_context() -> ToolConfirmContext:
    return _CONFIRM_CTX.get() or ToolConfirmContext()


def tool_is_mutating(tool: Any, name: str = "") -> bool:
    if tool is not None and bool(getattr(tool, "mutating", False)):
        return True
    return str(name or getattr(tool, "name", "") or "") in MUTATING_TOOL_NAMES


def is_confirmation_required_result(result: Any) -> bool:
    return isinstance(result, dict) and str(result.get("error") or "") == CONFIRMATION_REQUIRED


def _auth_secret() -> str:
    return str(os.getenv("AUTH_TOKEN_SECRET", "") or "").strip()


def canonical_args_hash(args: Any) -> str:
    payload = args if isinstance(args, dict) else {}
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def make_confirm_id(*, tool: str, args: Any, actor_id: str, job_id: str, exp: int) -> str:
    message = f"{tool}|{canonical_args_hash(args)}|{actor_id}|{job_id}|{exp}"
    return hmac.new(_auth_secret().encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()


def build_tool_preview(tool: str, args: Any) -> str:
    compact = json.dumps(args if isinstance(args, dict) else {}, ensure_ascii=False, sort_keys=True)
    if len(compact) > 400:
        compact = compact[:397] + "..."
    return f"{tool}: {compact}"


def confirms_dir(data_dir: Optional[Path] = None) -> Path:
    root = Path(data_dir or get_default_config().DATA_DIR)
    return root / "tool_confirms"


def _confirm_path(confirm_id: str, data_dir: Optional[Path] = None) -> Path:
    safe_id = "".join(ch for ch in str(confirm_id or "") if ch in "0123456789abcdef")
    return confirms_dir(data_dir) / f"{safe_id}.json"


def confirm_pending_is_live(pending: Any, *, now: Optional[int] = None) -> bool:
    if not isinstance(pending, dict) or not pending:
        return False
    try:
        exp = int(pending.get("exp") or 0)
    except Exception:  # policy: allowed-broad-except
        return False
    clock = int(now if now is not None else time.time())
    return exp > clock


def create_tool_confirm_pending(
    *,
    tool: str,
    args: Dict[str, Any],
    actor_id: str = "",
    job_id: str = "",
    lane_id: str = "",
    tool_call_id: str = "",
    role: str = "",
    skill_id: str = "",
    teacher_id: str = "",
    data_dir: Optional[Path] = None,
    now: Optional[int] = None,
) -> Dict[str, Any]:
    clock = int(now if now is not None else time.time())
    exp = clock + CONFIRM_TTL_SEC
    actor = str(actor_id or "")
    job = str(job_id or "")
    confirm_id = make_confirm_id(tool=str(tool), args=args, actor_id=actor, job_id=job, exp=exp)
    payload = {
        "tool": str(tool),
        "args": dict(args or {}),
        "actor_id": actor,
        "job_id": job,
        "lane_id": str(lane_id or ""),
        "tool_call_id": str(tool_call_id or ""),
        "role": str(role or ""),
        "skill_id": str(skill_id or ""),
        "teacher_id": str(teacher_id or ""),
        "exp": exp,
    }
    directory = confirms_dir(data_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = _confirm_path(confirm_id, data_dir)
    atomic_write_json(path, payload)
    os.chmod(path, 0o600)
    preview = build_tool_preview(str(tool), args)
    return {
        "error": CONFIRMATION_REQUIRED,
        "confirm_id": confirm_id,
        "tool": str(tool),
        "preview": preview,
        "exp": exp,
        "tool_call_id": str(tool_call_id or ""),
    }


def consume_tool_confirm_pending(
    confirm_id: str,
    *,
    actor_id: str = "",
    data_dir: Optional[Path] = None,
    now: Optional[int] = None,
) -> Dict[str, Any]:
    path = _confirm_path(confirm_id, data_dir)
    if not path.is_file():
        return {"error": "confirm_not_found"}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # policy: allowed-broad-except
        _log.debug("failed to read confirm ticket %s", confirm_id, exc_info=True)
        return {"error": "confirm_not_found"}
    if not isinstance(data, dict):
        return {"error": "confirm_not_found"}
    try:
        exp = int(data.get("exp") or 0)
    except Exception:  # policy: allowed-broad-except
        return {"error": "confirm_not_found"}
    expected = make_confirm_id(
        tool=str(data.get("tool") or ""),
        args=data.get("args") or {},
        actor_id=str(data.get("actor_id") or ""),
        job_id=str(data.get("job_id") or ""),
        exp=exp,
    )
    if not hmac.compare_digest(str(confirm_id), expected):
        return {"error": "confirm_not_found"}
    if not confirm_pending_is_live({"exp": data.get("exp")}, now=now):
        try:
            path.unlink(missing_ok=True)
        except Exception:  # policy: allowed-broad-except
            _log.debug("failed to delete expired confirm ticket %s", confirm_id, exc_info=True)
        return {"error": "confirm_not_found"}
    pending_actor = str(data.get("actor_id") or "")
    request_actor = str(actor_id or "")
    if pending_actor and request_actor and pending_actor != request_actor:
        return {"error": "forbidden"}
    consumed = path.with_suffix(".json.consumed")
    try:
        os.rename(str(path), str(consumed))
    except FileNotFoundError:
        return {"error": "confirm_not_found"}
    except Exception:  # policy: allowed-broad-except
        _log.debug("failed to consume confirm ticket %s", confirm_id, exc_info=True)
        return {"error": "confirm_not_found"}
    try:
        consumed.unlink(missing_ok=True)
    except Exception:  # policy: allowed-broad-except
        _log.debug("failed to unlink consumed confirm ticket %s", confirm_id, exc_info=True)
    return {"ok": True, "pending": data}


def maybe_confirmation_required(
    *,
    tool: Any,
    name: str,
    args: Dict[str, Any],
    confirmed: bool,
    actor_id: str = "",
    job_id: str = "",
    lane_id: str = "",
    tool_call_id: str = "",
    role: str = "",
    skill_id: str = "",
    teacher_id: str = "",
    data_dir: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    if confirmed or not tool_is_mutating(tool, name):
        return None
    ctx = current_tool_confirm_context()
    return create_tool_confirm_pending(
        tool=name,
        args=args,
        actor_id=str(actor_id or ctx.actor_id or ""),
        job_id=str(job_id or ctx.job_id or ""),
        lane_id=str(lane_id or ctx.lane_id or ""),
        tool_call_id=str(tool_call_id or ctx.tool_call_id or ""),
        role=str(role or ctx.role or ""),
        skill_id=str(skill_id or ctx.skill_id or ""),
        teacher_id=str(teacher_id or ctx.teacher_id or ""),
        data_dir=data_dir,
    )


def _resume_after_confirm(job_id: str, lane_id: str, *, tenant_id: Optional[str]) -> Dict[str, Any]:
    from services.api.workers.rq_tasks import resume_chat_job_after_confirm

    return resume_chat_job_after_confirm(job_id, lane_id, tenant_id=tenant_id)


def confirm_teacher_tool(
    *,
    confirm_id: str,
    confirmed: bool,
    actor_id: str,
    core: Any,
    data_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    consumed = consume_tool_confirm_pending(confirm_id, actor_id=actor_id, data_dir=data_dir)
    if consumed.get("error"):
        return consumed
    pending = consumed.get("pending") if isinstance(consumed.get("pending"), dict) else {}
    job_id = str(pending.get("job_id") or "")
    lane_id = str(pending.get("lane_id") or "")
    if confirmed:
        result = core.tool_dispatch(
            str(pending.get("tool") or ""),
            pending.get("args") if isinstance(pending.get("args"), dict) else {},
            str(pending.get("role") or "teacher") or "teacher",
            skill_id=str(pending.get("skill_id") or "") or None,
            teacher_id=str(pending.get("teacher_id") or actor_id or "") or None,
            confirmed=True,
        )
    else:
        result = {"error": "cancelled"}
    if job_id and callable(getattr(core, "write_chat_job", None)):
        core.write_chat_job(job_id, {"confirm_resume_result": result})
    if job_id and lane_id:
        tenant_id = str(getattr(core, "TENANT_ID", "") or "") or None
        _resume_after_confirm(job_id, lane_id, tenant_id=tenant_id)
    return {"ok": True, "job_id": job_id, "executed": bool(confirmed), "result": result}


def resolve_confirm_actor_id() -> str:
    try:
        principal = require_principal(roles=("teacher", "admin"))
    except AuthError:
        if auth_required():
            raise
        return ""
    if principal is None:
        return ""
    return str(principal.actor_id or "")
