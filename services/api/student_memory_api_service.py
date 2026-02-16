from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

_log = logging.getLogger(__name__)

_ALLOWED_MEMORY_TYPES = {
    "learning_preference",
    "stable_misconception",
    "long_term_goal",
    "effective_intervention",
}

_ALLOWED_STATUSES = {"proposed", "applied", "rejected", "deleted"}

_BLOCK_PATTERNS: Tuple[Tuple[str, Any], ...] = (
    (
        "score_detail",
        re.compile(
            r"(?:(?<!\d)\d{1,3}(?:\.\d+)?\s*分(?=$|[\s，。！？；、,.!?;:）】)])|得分\s*\d{1,3}|成绩\s*\d{1,3})",
            re.IGNORECASE,
        ),
    ),
    ("ranking_detail", re.compile(r"(?:排名|名次|第\s*\d+\s*名|top\s*\d+|百分位)", re.IGNORECASE)),
    ("phone_number", re.compile(r"(?<!\d)1\d{10}(?!\d)")),
    ("id_number", re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")),
    ("contact_info", re.compile(r"(?:微信|手机号|家庭住址|身份证号|联系方式)", re.IGNORECASE)),
)

_AUTO_MIN_CONTENT_CHARS = 12
_AUTO_MAX_PROPOSALS_PER_DAY = 6

_AUTO_GOAL_PATTERNS: Tuple[Any, ...] = (
    re.compile(r"(?:长期目标|阶段目标|我的目标|目标是|我希望(?:在|能)|计划在|我要在)", re.IGNORECASE),
)
_AUTO_PREFERENCE_PATTERNS: Tuple[Any, ...] = (
    re.compile(r"(?:以后|后续|下次|今后|默认|每次|一直).{0,16}(?:先|分步|简短|详细|举例|图示|总结|结论|步骤)", re.IGNORECASE),
    re.compile(r"(?:我更喜欢|我希望你|偏好|请你以后).{0,20}(?:先|分步|简短|详细|举例|图示|总结|结论|步骤)", re.IGNORECASE),
)
_AUTO_MISCONCEPTION_PATTERNS: Tuple[Any, ...] = (
    re.compile(r"(?:总是|经常|老是|反复).{0,10}(?:混淆|搞混|分不清|弄错)", re.IGNORECASE),
)
_AUTO_INTERVENTION_PATTERNS: Tuple[Any, ...] = (
    re.compile(r"(?:这个方法|这种方式|这种讲法).{0,10}(?:有用|有效|更容易懂|更清楚)", re.IGNORECASE),
)
_AUTO_BLOCK_PATTERNS: Tuple[Any, ...] = (
    re.compile(r"(?:开始今天作业|继续今天作业|诊断问题|训练问题)", re.IGNORECASE),
    re.compile(r"(?:A\.|B\.|C\.|D\.)"),
    re.compile(r"(?:求|计算|选择题|填空题|解答题).{0,12}(?:答案|过程)", re.IGNORECASE),
)


@dataclass(frozen=True)
class StudentMemoryApiDeps:
    resolve_teacher_id: Callable[[Optional[str]], str]
    teacher_workspace_dir: Callable[[str], Path]
    now_iso: Callable[[], str]


def _norm_text_for_dedupe(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "").strip().lower())


def _safe_fs_id(value: str, prefix: str) -> str:
    raw = str(value or "").strip()
    slug = re.sub(r"[^\w-]+", "_", raw).strip("_")
    if len(slug) < 6:
        slug = f"{prefix}_{uuid.uuid4().hex[:10]}"
    return slug


def _proposals_dir(teacher_id: str, *, deps: StudentMemoryApiDeps) -> Path:
    base = deps.teacher_workspace_dir(teacher_id) / "student_memory" / "proposals"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _proposal_path(teacher_id: str, proposal_id: str, *, deps: StudentMemoryApiDeps) -> Path:
    return _proposals_dir(teacher_id, deps=deps) / f"{_safe_fs_id(proposal_id, prefix='smem')}.json"


def _event_log_path(teacher_id: str, *, deps: StudentMemoryApiDeps) -> Path:
    base = deps.teacher_workspace_dir(teacher_id) / "telemetry"
    base.mkdir(parents=True, exist_ok=True)
    return base / "student_memory_events.jsonl"


def _atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{uuid.uuid4().hex[:8]}")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _append_event(
    teacher_id: str,
    event: str,
    payload: Optional[Dict[str, Any]],
    *,
    deps: StudentMemoryApiDeps,
) -> None:
    rec: Dict[str, Any] = {"ts": deps.now_iso(), "event": str(event or "").strip() or "unknown"}
    if isinstance(payload, dict):
        for key, value in payload.items():
            if value is not None:
                rec[str(key)] = value
    try:
        path = _event_log_path(teacher_id, deps=deps)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        _log.warning("failed to write student memory event log teacher=%s", teacher_id, exc_info=True)


def _load_record(path: Path) -> Dict[str, Any]:
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(rec, dict):
            return rec
    except Exception:
        _log.warning("failed to load student memory proposal file %s", path, exc_info=True)
    return {}


def _validate_candidate(memory_type: str, content: str) -> Dict[str, Any]:
    mt = str(memory_type or "").strip().lower()
    if mt not in _ALLOWED_MEMORY_TYPES:
        return {
            "ok": False,
            "error": "invalid_memory_type",
            "allowed_memory_types": sorted(_ALLOWED_MEMORY_TYPES),
        }

    text = str(content or "").strip()
    if len(text) < 8:
        return {"ok": False, "error": "content_too_short"}

    risk_flags: List[str] = []
    for label, pattern in _BLOCK_PATTERNS:
        try:
            if pattern.search(text):
                risk_flags.append(label)
        except Exception:
            _log.debug("student memory block pattern failed label=%s", label, exc_info=True)
    if risk_flags:
        return {"ok": False, "error": "content_blocked", "risk_flags": sorted(set(risk_flags))}

    return {"ok": True, "memory_type": mt, "content": text, "risk_flags": []}


def create_proposal_api(
    *,
    teacher_id: Optional[str],
    student_id: str,
    memory_type: str,
    content: str,
    evidence_refs: Optional[List[str]],
    source: Optional[str],
    deps: StudentMemoryApiDeps,
) -> Dict[str, Any]:
    teacher_id_final = deps.resolve_teacher_id(teacher_id)
    sid = str(student_id or "").strip()
    if not sid:
        return {"ok": False, "error": "student_id_required"}

    check = _validate_candidate(memory_type, content)
    if not check.get("ok"):
        _append_event(
            teacher_id_final,
            "proposal_blocked",
            {
                "student_id": sid,
                "memory_type": str(memory_type or "").strip().lower(),
                "error": str(check.get("error") or ""),
                "risk_flags": check.get("risk_flags") or [],
            },
            deps=deps,
        )
        out = {"ok": False, "error": str(check.get("error") or "invalid_candidate")}
        if isinstance(check.get("risk_flags"), list):
            out["risk_flags"] = check.get("risk_flags") or []
        if isinstance(check.get("allowed_memory_types"), list):
            out["allowed_memory_types"] = check.get("allowed_memory_types") or []
        return out

    proposal_id = f"smem_{uuid.uuid4().hex[:12]}"
    stamp = deps.now_iso()
    record: Dict[str, Any] = {
        "proposal_id": proposal_id,
        "teacher_id": teacher_id_final,
        "student_id": sid,
        "memory_type": str(check.get("memory_type") or "").strip(),
        "content": str(check.get("content") or "").strip(),
        "source": str(source or "manual").strip() or "manual",
        "evidence_refs": [str(item).strip() for item in (evidence_refs or []) if str(item).strip()],
        "status": "proposed",
        "created_at": stamp,
        "risk_flags": [],
    }
    path = _proposal_path(teacher_id_final, proposal_id, deps=deps)
    _atomic_write_json(path, record)
    _append_event(
        teacher_id_final,
        "proposal_created",
        {
            "proposal_id": proposal_id,
            "student_id": sid,
            "memory_type": record["memory_type"],
            "source": record["source"],
        },
        deps=deps,
    )
    return {"ok": True, "proposal_id": proposal_id, "status": "proposed", "teacher_id": teacher_id_final}


def _infer_auto_candidate(
    *,
    user_text: str,
    assistant_text: str,
) -> Optional[Dict[str, str]]:
    text = str(user_text or "").strip()
    if len(text) < _AUTO_MIN_CONTENT_CHARS:
        return None
    if any(p.search(text) for p in _AUTO_BLOCK_PATTERNS):
        return None

    if any(p.search(text) for p in _AUTO_GOAL_PATTERNS):
        return {"memory_type": "long_term_goal", "content": text[:260]}
    if any(p.search(text) for p in _AUTO_PREFERENCE_PATTERNS):
        return {"memory_type": "learning_preference", "content": text[:260]}
    if any(p.search(text) for p in _AUTO_MISCONCEPTION_PATTERNS):
        return {"memory_type": "stable_misconception", "content": text[:260]}

    assistant = str(assistant_text or "").strip()
    if assistant and any(p.search(text) for p in _AUTO_INTERVENTION_PATTERNS):
        return {"memory_type": "effective_intervention", "content": text[:260]}
    return None


def _auto_daily_quota_reached(
    existing: List[Dict[str, Any]],
    *,
    today: str,
) -> bool:
    count = 0
    for rec in existing:
        status = str(rec.get("status") or "").strip().lower()
        if status not in {"proposed", "applied"}:
            continue
        created_at = str(rec.get("created_at") or "").strip()
        if not today or not created_at.startswith(today):
            continue
        source = str(rec.get("source") or "").strip().lower()
        if not source.startswith("auto_"):
            continue
        count += 1
        if count >= _AUTO_MAX_PROPOSALS_PER_DAY:
            return True
    return False


def _auto_find_duplicate(
    existing: List[Dict[str, Any]],
    *,
    student_id: str,
    memory_type: str,
    content: str,
) -> Optional[Dict[str, Any]]:
    sid = str(student_id or "").strip()
    mt = str(memory_type or "").strip().lower()
    norm = _norm_text_for_dedupe(content)
    if not sid or not mt or not norm:
        return None
    for rec in existing:
        status = str(rec.get("status") or "").strip().lower()
        if status not in {"proposed", "applied"}:
            continue
        if str(rec.get("student_id") or "").strip() != sid:
            continue
        if str(rec.get("memory_type") or "").strip().lower() != mt:
            continue
        if _norm_text_for_dedupe(str(rec.get("content") or "")) == norm:
            return rec
    return None


def student_memory_auto_propose_from_turn_api(
    *,
    teacher_id: Optional[str],
    student_id: str,
    session_id: str,
    user_text: str,
    assistant_text: str,
    request_id: Optional[str],
    deps: StudentMemoryApiDeps,
) -> Dict[str, Any]:
    teacher_input = str(teacher_id or "").strip()
    if not teacher_input:
        return {"ok": False, "created": False, "reason": "missing_teacher_id"}
    sid = str(student_id or "").strip()
    if not sid:
        return {"ok": False, "created": False, "reason": "student_id_required"}

    candidate = _infer_auto_candidate(user_text=user_text, assistant_text=assistant_text)
    if not candidate:
        return {"ok": False, "created": False, "reason": "no_candidate"}

    teacher_id_final = deps.resolve_teacher_id(teacher_input)
    existing_resp = list_proposals_api(
        teacher_id_final,
        student_id=sid,
        status=None,
        limit=300,
        deps=deps,
    )
    existing = (
        existing_resp.get("proposals")
        if bool(existing_resp.get("ok")) and isinstance(existing_resp.get("proposals"), list)
        else []
    )
    today = str(deps.now_iso() or "").strip().split("T", 1)[0]
    if _auto_daily_quota_reached(existing, today=today):
        return {"ok": False, "created": False, "reason": "daily_quota_reached"}

    duplicate = _auto_find_duplicate(
        existing,
        student_id=sid,
        memory_type=str(candidate.get("memory_type") or ""),
        content=str(candidate.get("content") or ""),
    )
    if duplicate:
        return {
            "ok": True,
            "created": False,
            "reason": "duplicate",
            "proposal_id": str(duplicate.get("proposal_id") or ""),
            "memory_type": str(candidate.get("memory_type") or ""),
        }

    refs: List[str] = []
    sid_ref = str(session_id or "").strip()
    if sid_ref:
        refs.append(f"session:{sid_ref}")
    rid_ref = str(request_id or "").strip()
    if rid_ref:
        refs.append(f"request:{rid_ref}")

    created = create_proposal_api(
        teacher_id=teacher_id_final,
        student_id=sid,
        memory_type=str(candidate.get("memory_type") or ""),
        content=str(candidate.get("content") or ""),
        evidence_refs=refs or None,
        source="auto_student_infer",
        deps=deps,
    )
    if not created.get("ok"):
        return {
            "ok": False,
            "created": False,
            "reason": str(created.get("error") or "create_failed"),
            "error": str(created.get("error") or "create_failed"),
        }
    return {
        "ok": True,
        "created": True,
        "proposal_id": str(created.get("proposal_id") or ""),
        "status": str(created.get("status") or "proposed"),
        "memory_type": str(candidate.get("memory_type") or ""),
        "teacher_id": teacher_id_final,
        "student_id": sid,
    }


def list_proposals_api(
    teacher_id: Optional[str],
    *,
    student_id: Optional[str],
    status: Optional[str],
    limit: int,
    deps: StudentMemoryApiDeps,
) -> Dict[str, Any]:
    teacher_id_final = deps.resolve_teacher_id(teacher_id)
    student_filter = str(student_id or "").strip() or None
    status_norm = str(status or "").strip().lower() or None
    if status_norm and status_norm not in _ALLOWED_STATUSES:
        return {"ok": False, "error": "invalid_status"}

    take = max(1, min(int(limit or 20), 200))
    proposals_dir = _proposals_dir(teacher_id_final, deps=deps)

    def _safe_mtime(path: Path) -> float:
        try:
            return path.stat().st_mtime
        except OSError:
            return 0.0

    items: List[Dict[str, Any]] = []
    for path in sorted(proposals_dir.glob("*.json"), key=_safe_mtime, reverse=True):
        rec = _load_record(path)
        if not rec:
            continue
        rec_status = str(rec.get("status") or "").strip().lower()
        if status_norm:
            if rec_status != status_norm:
                continue
        elif rec_status == "deleted":
            continue
        if student_filter and str(rec.get("student_id") or "").strip() != student_filter:
            continue
        if "proposal_id" not in rec:
            rec["proposal_id"] = path.stem
        items.append(rec)
        if len(items) >= take:
            break

    return {
        "ok": True,
        "teacher_id": teacher_id_final,
        "student_id": student_filter,
        "proposals": items,
    }


def review_proposal_api(
    proposal_id: str,
    *,
    teacher_id: Optional[str],
    approve: bool,
    deps: StudentMemoryApiDeps,
) -> Dict[str, Any]:
    teacher_id_final = deps.resolve_teacher_id(teacher_id)
    pid = str(proposal_id or "").strip()
    if not pid:
        return {"ok": False, "error": "proposal_id_required"}
    path = _proposal_path(teacher_id_final, pid, deps=deps)
    if not path.exists():
        return {"ok": False, "error": "proposal not found"}

    rec = _load_record(path)
    if not rec:
        return {"ok": False, "error": "proposal not found"}

    next_status = "applied" if bool(approve) else "rejected"
    rec["proposal_id"] = pid
    rec["status"] = next_status
    rec["reviewed_at"] = deps.now_iso()
    rec["reviewed_by"] = teacher_id_final
    _atomic_write_json(path, rec)
    _append_event(
        teacher_id_final,
        "proposal_reviewed",
        {
            "proposal_id": pid,
            "student_id": str(rec.get("student_id") or ""),
            "status": next_status,
        },
        deps=deps,
    )
    return {"ok": True, "proposal_id": pid, "status": next_status}


def delete_proposal_api(
    proposal_id: str,
    *,
    teacher_id: Optional[str],
    deps: StudentMemoryApiDeps,
) -> Dict[str, Any]:
    teacher_id_final = deps.resolve_teacher_id(teacher_id)
    pid = str(proposal_id or "").strip()
    if not pid:
        return {"ok": False, "error": "proposal_id_required"}
    path = _proposal_path(teacher_id_final, pid, deps=deps)
    if not path.exists():
        return {"ok": False, "error": "proposal not found"}

    rec = _load_record(path)
    if not rec:
        return {"ok": False, "error": "proposal not found"}

    prev = str(rec.get("status") or "proposed").strip().lower() or "proposed"
    if prev == "deleted":
        return {"ok": True, "proposal_id": pid, "status": "deleted", "detail": "already_deleted"}

    rec["proposal_id"] = pid
    rec["status"] = "deleted"
    rec["deleted_at"] = deps.now_iso()
    rec["deleted_from_status"] = prev
    _atomic_write_json(path, rec)
    _append_event(
        teacher_id_final,
        "proposal_deleted",
        {
            "proposal_id": pid,
            "student_id": str(rec.get("student_id") or ""),
            "deleted_from_status": prev,
        },
        deps=deps,
    )
    return {"ok": True, "proposal_id": pid, "status": "deleted"}


def insights_api(
    teacher_id: Optional[str],
    *,
    student_id: Optional[str],
    days: int,
    deps: StudentMemoryApiDeps,
) -> Dict[str, Any]:
    teacher_id_final = deps.resolve_teacher_id(teacher_id)
    student_filter = str(student_id or "").strip() or None
    span = max(1, min(int(days or 14), 90))
    cutoff = datetime.now() - timedelta(days=span)

    status_counts: Dict[str, int] = {k: 0 for k in sorted(_ALLOWED_STATUSES)}
    type_counts: Dict[str, int] = {}
    total = 0

    proposals_dir = _proposals_dir(teacher_id_final, deps=deps)
    for path in proposals_dir.glob("*.json"):
        rec = _load_record(path)
        if not rec:
            continue
        if student_filter and str(rec.get("student_id") or "").strip() != student_filter:
            continue
        created_at = str(rec.get("created_at") or "").strip()
        try:
            created_dt = datetime.fromisoformat(created_at)
        except Exception:
            created_dt = None
        if created_dt is not None and created_dt < cutoff:
            continue
        status = str(rec.get("status") or "proposed").strip().lower() or "proposed"
        mtype = str(rec.get("memory_type") or "unknown").strip().lower() or "unknown"
        status_counts[status] = status_counts.get(status, 0) + 1
        type_counts[mtype] = type_counts.get(mtype, 0) + 1
        total += 1

    return {
        "ok": True,
        "teacher_id": teacher_id_final,
        "student_id": student_filter,
        "days": span,
        "total": total,
        "status_counts": status_counts,
        "type_counts": type_counts,
    }
