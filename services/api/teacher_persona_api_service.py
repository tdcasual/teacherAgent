from __future__ import annotations

import fcntl
import json
import logging
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, TypeVar

from .fs_atomic import atomic_write_json

_log = logging.getLogger(__name__)
_T = TypeVar("_T")

_MAX_NAME_LEN = 80
_MAX_SUMMARY_LEN = 500
_MAX_RULE_LEN = 300
_MAX_EXAMPLE_LEN = 300


@dataclass(frozen=True)
class TeacherPersonaApiDeps:
    data_dir: Path
    uploads_dir: Path
    now_iso: Callable[[], str]


def _safe_id(value: Any) -> str:
    return str(value or "").strip()


def _teacher_personas_path(teacher_id: str, deps: TeacherPersonaApiDeps) -> Path:
    base = (deps.data_dir / "teacher_personas").resolve()
    tid = _safe_id(teacher_id)
    if not tid:
        raise ValueError("missing_teacher_id")
    folder = (base / tid).resolve()
    if folder != base and base not in folder.parents:
        raise ValueError("invalid_teacher_id")
    return folder / "personas.json"


def _student_assignments_path(student_id: str, deps: TeacherPersonaApiDeps) -> Path:
    base = (deps.data_dir / "persona_assignments" / "by_student").resolve()
    sid = _safe_id(student_id)
    if not sid:
        raise ValueError("missing_student_id")
    path = (base / f"{sid}.json").resolve()
    if path != base and base not in path.parents:
        raise ValueError("invalid_student_id")
    return path


def _teacher_avatar_dir(teacher_id: str, persona_id: str, deps: TeacherPersonaApiDeps) -> Path:
    base = (deps.uploads_dir / "persona_avatars" / "teacher").resolve()
    tid = _safe_id(teacher_id)
    pid = _safe_id(persona_id)
    if not tid or not pid:
        raise ValueError("invalid_avatar_owner")
    folder = (base / tid / pid).resolve()
    if folder != base and base not in folder.parents:
        raise ValueError("invalid_avatar_path")
    return folder


def _read_json_dict(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        _log.warning("failed to read/parse json file %s", path, exc_info=True)
        return {}
    return raw if isinstance(raw, dict) else {}


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    atomic_write_json(path, payload)


def _lock_path(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".lock")


def _with_path_lock(path: Path, fn: Callable[[], _T]) -> _T:
    lock_path = _lock_path(path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        return fn()
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def _normalize_teacher_store(payload: Dict[str, Any], teacher_id: str) -> Dict[str, Any]:
    out = dict(payload if isinstance(payload, dict) else {})
    personas = out.get("personas")
    if not isinstance(personas, list):
        personas = []
    out["teacher_id"] = _safe_id(out.get("teacher_id")) or _safe_id(teacher_id)
    out["personas"] = [item for item in personas if isinstance(item, dict)]
    return out


def _as_str_list(value: Any, limit: int) -> List[str]:
    if not isinstance(value, list):
        return []
    out: List[str] = []
    for item in value:
        text = str(item or "").strip()
        if not text:
            continue
        out.append(text)
        if len(out) >= limit:
            break
    return out


def _validate_name(value: Any) -> str:
    text = _safe_id(value)
    if not text or len(text) > _MAX_NAME_LEN:
        raise ValueError("invalid_name")
    return text


def _validate_summary(value: Any) -> str:
    text = _safe_id(value)
    if len(text) > _MAX_SUMMARY_LEN:
        raise ValueError("invalid_summary")
    return text


def _validate_list_items(value: Any, *, limit: int, max_item_len: int, error: str) -> List[str]:
    items = _as_str_list(value, limit)
    if not items:
        raise ValueError(error)
    if any(len(item) > max_item_len for item in items):
        raise ValueError(error)
    return items


def _validate_avatar_file(filename: str, content: bytes) -> str:
    if len(content) > 2 * 1024 * 1024:
        raise ValueError("avatar_too_large")
    if not content:
        raise ValueError("avatar_empty")
    lower = str(filename or "").strip().lower()
    if "." not in lower:
        raise ValueError("avatar_invalid_extension")
    ext = lower.rsplit(".", 1)[-1]
    if ext not in {"png", "jpg", "jpeg", "webp"}:
        raise ValueError("avatar_invalid_extension")
    if content[:256].lower().find(b"<svg") >= 0:
        raise ValueError("avatar_svg_not_allowed")
    return "jpg" if ext == "jpeg" else ext


def _load_teacher_personas(teacher_id: str, deps: TeacherPersonaApiDeps) -> Dict[str, Any]:
    path = _teacher_personas_path(teacher_id, deps)
    return _normalize_teacher_store(_read_json_dict(path), teacher_id)


def teacher_personas_get_api(teacher_id: str, *, deps: TeacherPersonaApiDeps) -> Dict[str, Any]:
    tid = _safe_id(teacher_id)
    if not tid:
        return {"ok": False, "error": "missing_teacher_id"}
    payload = _load_teacher_personas(tid, deps)
    return {
        "ok": True,
        "teacher_id": tid,
        "personas": payload.get("personas", []),
    }


def teacher_persona_create_api(
    teacher_id: str,
    req: Dict[str, Any],
    *,
    deps: TeacherPersonaApiDeps,
) -> Dict[str, Any]:
    tid = _safe_id(teacher_id)
    if not tid:
        return {"ok": False, "error": "missing_teacher_id"}
    payload = req if isinstance(req, dict) else {}
    try:
        name = _validate_name(payload.get("name"))
        summary = _validate_summary(payload.get("summary"))
        style_rules = _validate_list_items(
            payload.get("style_rules"),
            limit=20,
            max_item_len=_MAX_RULE_LEN,
            error="invalid_style_rules",
        )
        few_shot_examples = _validate_list_items(
            payload.get("few_shot_examples"),
            limit=10,
            max_item_len=_MAX_EXAMPLE_LEN,
            error="invalid_few_shot_examples",
        )
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    visibility_mode = _safe_id(payload.get("visibility_mode")).lower() or "assigned_only"
    if visibility_mode not in {"assigned_only", "hidden_all"}:
        return {"ok": False, "error": "invalid_visibility_mode"}
    lifecycle_status = _safe_id(payload.get("lifecycle_status")).lower() or "active"
    if lifecycle_status not in {"draft", "active", "archived"}:
        return {"ok": False, "error": "invalid_lifecycle_status"}

    path = _teacher_personas_path(tid, deps)

    def _create_locked() -> Dict[str, Any]:
        store = _normalize_teacher_store(_read_json_dict(path), tid)
        persona = {
            "persona_id": f"tp_{uuid.uuid4().hex[:12]}",
            "teacher_id": tid,
            "name": name,
            "summary": summary,
            "style_rules": style_rules,
            "few_shot_examples": few_shot_examples,
            "avatar_url": _safe_id(payload.get("avatar_url")),
            "intensity_cap": _safe_id(payload.get("intensity_cap")) or "low",
            "lifecycle_status": lifecycle_status,
            "visibility_mode": visibility_mode,
            "created_at": deps.now_iso(),
            "updated_at": deps.now_iso(),
        }
        personas = list(store.get("personas") or [])
        personas.append(persona)
        store["personas"] = personas
        _write_json(path, store)
        return {"ok": True, "teacher_id": tid, "persona": persona}

    return _with_path_lock(path, _create_locked)


def teacher_persona_update_api(
    teacher_id: str,
    persona_id: str,
    req: Dict[str, Any],
    *,
    deps: TeacherPersonaApiDeps,
) -> Dict[str, Any]:
    tid = _safe_id(teacher_id)
    pid = _safe_id(persona_id)
    if not tid:
        return {"ok": False, "error": "missing_teacher_id"}
    if not pid:
        return {"ok": False, "error": "missing_persona_id"}

    patch = req if isinstance(req, dict) else {}
    path = _teacher_personas_path(tid, deps)

    def _update_locked() -> Dict[str, Any]:
        store = _normalize_teacher_store(_read_json_dict(path), tid)
        personas = list(store.get("personas") or [])
        idx = next((i for i, item in enumerate(personas) if _safe_id(item.get("persona_id")) == pid), -1)
        if idx < 0:
            return {"ok": False, "error": "persona_not_found"}

        current = dict(personas[idx])
        try:
            if "name" in patch:
                current["name"] = _validate_name(patch.get("name"))
            if "summary" in patch:
                current["summary"] = _validate_summary(patch.get("summary"))
            if "avatar_url" in patch:
                current["avatar_url"] = _safe_id(patch.get("avatar_url"))
            if "intensity_cap" in patch:
                current["intensity_cap"] = _safe_id(patch.get("intensity_cap")) or "low"
            if "style_rules" in patch:
                current["style_rules"] = _validate_list_items(
                    patch.get("style_rules"),
                    limit=20,
                    max_item_len=_MAX_RULE_LEN,
                    error="invalid_style_rules",
                )
            if "few_shot_examples" in patch:
                current["few_shot_examples"] = _validate_list_items(
                    patch.get("few_shot_examples"),
                    limit=10,
                    max_item_len=_MAX_EXAMPLE_LEN,
                    error="invalid_few_shot_examples",
                )
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        if "visibility_mode" in patch:
            visibility_mode = _safe_id(patch.get("visibility_mode")).lower()
            if visibility_mode not in {"assigned_only", "hidden_all"}:
                return {"ok": False, "error": "invalid_visibility_mode"}
            current["visibility_mode"] = visibility_mode
        if "lifecycle_status" in patch:
            lifecycle_status = _safe_id(patch.get("lifecycle_status")).lower()
            if lifecycle_status not in {"draft", "active", "archived"}:
                return {"ok": False, "error": "invalid_lifecycle_status"}
            current["lifecycle_status"] = lifecycle_status
        current["updated_at"] = deps.now_iso()
        personas[idx] = current
        store["personas"] = personas
        _write_json(path, store)
        return {"ok": True, "teacher_id": tid, "persona": current}

    return _with_path_lock(path, _update_locked)


def teacher_persona_visibility_api(
    teacher_id: str,
    persona_id: str,
    req: Dict[str, Any],
    *,
    deps: TeacherPersonaApiDeps,
) -> Dict[str, Any]:
    payload = req if isinstance(req, dict) else {}
    visibility_mode = _safe_id(payload.get("visibility_mode")).lower()
    if visibility_mode not in {"assigned_only", "hidden_all"}:
        return {"ok": False, "error": "invalid_visibility_mode"}
    return teacher_persona_update_api(
        teacher_id,
        persona_id,
        {"visibility_mode": visibility_mode},
        deps=deps,
    )


def teacher_persona_assign_api(
    teacher_id: str,
    persona_id: str,
    req: Dict[str, Any],
    *,
    deps: TeacherPersonaApiDeps,
) -> Dict[str, Any]:
    tid = _safe_id(teacher_id)
    pid = _safe_id(persona_id)
    if not tid:
        return {"ok": False, "error": "missing_teacher_id"}
    if not pid:
        return {"ok": False, "error": "missing_persona_id"}
    body = req if isinstance(req, dict) else {}
    sid = _safe_id(body.get("student_id"))
    if not sid:
        return {"ok": False, "error": "missing_student_id"}
    status = _safe_id(body.get("status")).lower() or "active"
    if status not in {"active", "inactive"}:
        return {"ok": False, "error": "invalid_status"}

    store = _load_teacher_personas(tid, deps)
    exists = any(_safe_id(item.get("persona_id")) == pid for item in store.get("personas") or [])
    if not exists:
        return {"ok": False, "error": "persona_not_found"}

    assign_path = _student_assignments_path(sid, deps)

    def _assign_locked() -> Dict[str, Any]:
        assign_payload = _read_json_dict(assign_path)
        records = assign_payload.get("assignments")
        if not isinstance(records, list):
            records = []
        next_records: List[Dict[str, Any]] = []
        found = False
        for record in records:
            if not isinstance(record, dict):
                continue
            same = _safe_id(record.get("teacher_id")) == tid and _safe_id(record.get("persona_id")) == pid
            if not same:
                next_records.append(record)
                continue
            found = True
            updated = dict(record)
            updated["status"] = status
            updated["updated_at"] = deps.now_iso()
            next_records.append(updated)

        if not found:
            next_records.append(
                {
                    "assignment_id": f"pasg_{uuid.uuid4().hex[:12]}",
                    "teacher_id": tid,
                    "persona_id": pid,
                    "student_id": sid,
                    "status": status,
                    "assigned_at": deps.now_iso(),
                    "updated_at": deps.now_iso(),
                }
            )

        assign_payload["assignments"] = next_records
        _write_json(assign_path, assign_payload)
        return {"ok": True, "teacher_id": tid, "persona_id": pid, "student_id": sid, "status": status}

    return _with_path_lock(assign_path, _assign_locked)


def teacher_persona_avatar_upload_api(
    teacher_id: str,
    persona_id: str,
    *,
    filename: str,
    content: bytes,
    deps: TeacherPersonaApiDeps,
) -> Dict[str, Any]:
    tid = _safe_id(teacher_id)
    pid = _safe_id(persona_id)
    if not tid:
        return {"ok": False, "error": "missing_teacher_id"}
    if not pid:
        return {"ok": False, "error": "missing_persona_id"}
    try:
        ext = _validate_avatar_file(filename, content)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    path = _teacher_personas_path(tid, deps)

    def _upload_locked() -> Dict[str, Any]:
        store = _normalize_teacher_store(_read_json_dict(path), tid)
        personas = list(store.get("personas") or [])
        idx = next((i for i, item in enumerate(personas) if _safe_id(item.get("persona_id")) == pid), -1)
        if idx < 0:
            return {"ok": False, "error": "persona_not_found"}
        folder = _teacher_avatar_dir(tid, pid, deps)
        folder.mkdir(parents=True, exist_ok=True)
        file_name = f"avatar_{uuid.uuid4().hex[:10]}.{ext}"
        target = folder / file_name
        target.write_bytes(content)
        avatar_url = f"/teacher/personas/avatar/{tid}/{pid}/{file_name}"
        updated = dict(personas[idx])
        updated["avatar_url"] = avatar_url
        updated["updated_at"] = deps.now_iso()
        personas[idx] = updated
        store["personas"] = personas
        _write_json(path, store)
        return {"ok": True, "teacher_id": tid, "persona_id": pid, "avatar_url": avatar_url}

    return _with_path_lock(path, _upload_locked)


def resolve_teacher_persona_avatar_path(
    teacher_id: str,
    persona_id: str,
    file_name: str,
    *,
    deps: TeacherPersonaApiDeps,
) -> Path | None:
    tid = _safe_id(teacher_id)
    pid = _safe_id(persona_id)
    fname = _safe_id(file_name)
    if not tid or not pid or not fname:
        return None
    if "/" in fname or "\\" in fname:
        return None
    try:
        folder = _teacher_avatar_dir(tid, pid, deps)
    except ValueError:
        return None
    target = (folder / fname).resolve()
    if target != folder and folder not in target.parents:
        return None
    if not target.exists() or not target.is_file():
        return None
    return target
