from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List


@dataclass(frozen=True)
class TeacherPersonaApiDeps:
    data_dir: Path
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


def _read_json_dict(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


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


def _load_teacher_personas(teacher_id: str, deps: TeacherPersonaApiDeps) -> Dict[str, Any]:
    path = _teacher_personas_path(teacher_id, deps)
    payload = _read_json_dict(path)
    personas = payload.get("personas")
    if not isinstance(personas, list):
        personas = []
    payload["teacher_id"] = _safe_id(payload.get("teacher_id")) or _safe_id(teacher_id)
    payload["personas"] = [item for item in personas if isinstance(item, dict)]
    return payload


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
    name = _safe_id(payload.get("name"))
    if not name:
        return {"ok": False, "error": "invalid_name"}
    style_rules = _as_str_list(payload.get("style_rules"), 20)
    few_shot_examples = _as_str_list(payload.get("few_shot_examples"), 10)
    if not style_rules:
        return {"ok": False, "error": "invalid_style_rules"}
    if not few_shot_examples:
        return {"ok": False, "error": "invalid_few_shot_examples"}

    visibility_mode = _safe_id(payload.get("visibility_mode")).lower() or "assigned_only"
    if visibility_mode not in {"assigned_only", "hidden_all"}:
        return {"ok": False, "error": "invalid_visibility_mode"}
    lifecycle_status = _safe_id(payload.get("lifecycle_status")).lower() or "active"
    if lifecycle_status not in {"draft", "active", "archived"}:
        return {"ok": False, "error": "invalid_lifecycle_status"}

    store = _load_teacher_personas(tid, deps)
    persona = {
        "persona_id": f"tp_{uuid.uuid4().hex[:12]}",
        "teacher_id": tid,
        "name": name,
        "summary": _safe_id(payload.get("summary")),
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
    _write_json(_teacher_personas_path(tid, deps), store)
    return {"ok": True, "teacher_id": tid, "persona": persona}


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

    store = _load_teacher_personas(tid, deps)
    personas = list(store.get("personas") or [])
    idx = next((i for i, item in enumerate(personas) if _safe_id(item.get("persona_id")) == pid), -1)
    if idx < 0:
        return {"ok": False, "error": "persona_not_found"}

    patch = req if isinstance(req, dict) else {}
    current = dict(personas[idx])
    if "name" in patch:
        name = _safe_id(patch.get("name"))
        if not name:
            return {"ok": False, "error": "invalid_name"}
        current["name"] = name
    if "summary" in patch:
        current["summary"] = _safe_id(patch.get("summary"))
    if "avatar_url" in patch:
        current["avatar_url"] = _safe_id(patch.get("avatar_url"))
    if "intensity_cap" in patch:
        current["intensity_cap"] = _safe_id(patch.get("intensity_cap")) or "low"
    if "style_rules" in patch:
        style_rules = _as_str_list(patch.get("style_rules"), 20)
        if not style_rules:
            return {"ok": False, "error": "invalid_style_rules"}
        current["style_rules"] = style_rules
    if "few_shot_examples" in patch:
        examples = _as_str_list(patch.get("few_shot_examples"), 10)
        if not examples:
            return {"ok": False, "error": "invalid_few_shot_examples"}
        current["few_shot_examples"] = examples
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
    _write_json(_teacher_personas_path(tid, deps), store)
    return {"ok": True, "teacher_id": tid, "persona": current}


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
