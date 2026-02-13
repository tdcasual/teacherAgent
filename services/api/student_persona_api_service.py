from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class StudentPersonaApiDeps:
    data_dir: Path
    uploads_dir: Path
    now_iso: Callable[[], str]


def _safe_json_path(root: Path, key: str) -> Path:
    base = root.resolve()
    ident = str(key or "").strip()
    if not ident:
        raise ValueError("id_required")
    path = (base / f"{ident}.json").resolve()
    if path != base and base not in path.parents:
        raise ValueError("invalid_id")
    return path


def _student_profile_path(student_id: str, deps: StudentPersonaApiDeps) -> Path:
    return _safe_json_path(deps.data_dir / "student_profiles", student_id)


def _student_assignment_path(student_id: str, deps: StudentPersonaApiDeps) -> Path:
    return _safe_json_path(deps.data_dir / "persona_assignments" / "by_student", student_id)


def _teacher_personas_path(teacher_id: str, deps: StudentPersonaApiDeps) -> Path:
    base = (deps.data_dir / "teacher_personas").resolve()
    ident = str(teacher_id or "").strip()
    if not ident:
        raise ValueError("teacher_id_required")
    folder = (base / ident).resolve()
    if folder != base and base not in folder.parents:
        raise ValueError("invalid_teacher_id")
    return folder / "personas.json"


def _student_avatar_dir(student_id: str, persona_id: str, deps: StudentPersonaApiDeps) -> Path:
    base = (deps.uploads_dir / "persona_avatars" / "student").resolve()
    sid = str(student_id or "").strip()
    pid = str(persona_id or "").strip()
    if not sid or not pid:
        raise ValueError("invalid_avatar_owner")
    folder = (base / sid / pid).resolve()
    if folder != base and base not in folder.parents:
        raise ValueError("invalid_avatar_path")
    return folder


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


def _as_str_list(value: Any, *, limit: int) -> List[str]:
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


def _ensure_profile(student_id: str, deps: StudentPersonaApiDeps) -> Dict[str, Any]:
    path = _student_profile_path(student_id, deps)
    profile = _read_json_dict(path)
    profile["student_id"] = str(profile.get("student_id") or student_id).strip() or student_id
    personas = profile.get("personas")
    if not isinstance(personas, dict):
        personas = {}
        profile["personas"] = personas
    custom = personas.get("custom")
    if not isinstance(custom, list):
        personas["custom"] = []
    personas["active_persona_id"] = str(personas.get("active_persona_id") or "").strip()
    notified = personas.get("first_activation_notified_ids")
    if not isinstance(notified, list):
        personas["first_activation_notified_ids"] = []
    return profile


def _resolve_assigned_personas(student_id: str, deps: StudentPersonaApiDeps) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen: set[str] = set()
    assign_payload = _read_json_dict(_student_assignment_path(student_id, deps))
    records = assign_payload.get("assignments")
    if not isinstance(records, list):
        return out
    for record in records:
        if not isinstance(record, dict):
            continue
        if str(record.get("status") or "active").strip().lower() != "active":
            continue
        teacher_id = str(record.get("teacher_id") or "").strip()
        persona_id = str(record.get("persona_id") or "").strip()
        if not teacher_id or not persona_id:
            continue
        key = f"{teacher_id}:{persona_id}"
        if key in seen:
            continue
        seen.add(key)
        teacher_payload = _read_json_dict(_teacher_personas_path(teacher_id, deps))
        personas = teacher_payload.get("personas")
        if not isinstance(personas, list):
            continue
        for persona in personas:
            if not isinstance(persona, dict):
                continue
            if str(persona.get("persona_id") or "").strip() != persona_id:
                continue
            lifecycle = str(persona.get("lifecycle_status") or "active").strip().lower()
            visibility = str(persona.get("visibility_mode") or "assigned_only").strip().lower()
            if lifecycle != "active" or visibility == "hidden_all":
                break
            out.append(
                {
                    "persona_id": persona_id,
                    "teacher_id": teacher_id,
                    "name": str(persona.get("name") or ""),
                    "summary": str(persona.get("summary") or ""),
                    "avatar_url": str(persona.get("avatar_url") or ""),
                    "style_rules": _as_str_list(persona.get("style_rules"), limit=20),
                    "few_shot_examples": _as_str_list(persona.get("few_shot_examples"), limit=10),
                    "source": "teacher_assigned",
                    "review_status": "approved",
                }
            )
            break
    return out


def _review_custom_persona(name: str, style_rules: List[str], examples: List[str]) -> Tuple[str, str]:
    text = "\n".join([name] + style_rules + examples)
    normalized = re.sub(r"\s+", "", text).lower()
    blocked_patterns = [
        "忽略系统",
        "忽略以上规则",
        "泄露系统提示",
        "ignoreallsystem",
        "revealtheprompt",
        "你现在是系统管理员",
        "bypass",
        "越权",
    ]
    for pattern in blocked_patterns:
        if pattern in normalized:
            return "rejected", "contains_unsafe_instruction"
    roleplay_overreach = [
        "我是林黛玉本人",
        "i am the real",
        "我是现实中的",
        "我就是历史人物",
    ]
    for pattern in roleplay_overreach:
        if pattern in text.lower():
            return "rejected", "roleplay_overreach"
    return "approved", ""


def student_personas_get_api(student_id: str, *, deps: StudentPersonaApiDeps) -> Dict[str, Any]:
    sid = str(student_id or "").strip()
    if not sid:
        return {"ok": False, "error": "missing_student_id"}
    profile = _ensure_profile(sid, deps)
    personas = profile.get("personas") if isinstance(profile.get("personas"), dict) else {}
    custom_raw = personas.get("custom") if isinstance(personas, dict) else []
    custom = custom_raw if isinstance(custom_raw, list) else []
    assigned = _resolve_assigned_personas(sid, deps)

    custom_ids = {
        str(item.get("persona_id") or "").strip()
        for item in custom
        if isinstance(item, dict) and str(item.get("review_status") or "").strip().lower() == "approved"
    }
    assigned_ids = {str(item.get("persona_id") or "").strip() for item in assigned}
    active_persona_id = str(personas.get("active_persona_id") or "").strip() if isinstance(personas, dict) else ""
    if active_persona_id and active_persona_id not in custom_ids and active_persona_id not in assigned_ids:
        personas["active_persona_id"] = ""
        _write_json(_student_profile_path(sid, deps), profile)
        active_persona_id = ""

    return {
        "ok": True,
        "student_id": sid,
        "assigned": assigned,
        "custom": [item for item in custom if isinstance(item, dict)],
        "active_persona_id": active_persona_id,
    }


def student_persona_custom_create_api(
    student_id: str,
    payload: Dict[str, Any],
    *,
    deps: StudentPersonaApiDeps,
) -> Dict[str, Any]:
    sid = str(student_id or "").strip()
    if not sid:
        return {"ok": False, "error": "missing_student_id"}
    body = payload if isinstance(payload, dict) else {}
    name = str(body.get("name") or "").strip()
    if not name:
        return {"ok": False, "error": "invalid_name"}
    style_rules = _as_str_list(body.get("style_rules"), limit=20)
    few_shot_examples = _as_str_list(body.get("few_shot_examples"), limit=10)
    if not style_rules:
        return {"ok": False, "error": "invalid_style_rules"}
    if not few_shot_examples:
        return {"ok": False, "error": "invalid_few_shot_examples"}

    profile = _ensure_profile(sid, deps)
    personas = profile["personas"]
    custom_raw = personas.get("custom")
    custom = custom_raw if isinstance(custom_raw, list) else []
    approved_count = sum(
        1
        for item in custom
        if isinstance(item, dict) and str(item.get("review_status") or "").strip().lower() == "approved"
    )
    if approved_count >= 5:
        return {"ok": False, "error": "custom_persona_limit_reached"}

    review_status, review_reason = _review_custom_persona(name, style_rules, few_shot_examples)
    persona = {
        "persona_id": f"custom_{uuid.uuid4().hex[:12]}",
        "name": name,
        "summary": str(body.get("summary") or "").strip(),
        "style_rules": style_rules,
        "few_shot_examples": few_shot_examples,
        "avatar_url": str(body.get("avatar_url") or "").strip(),
        "review_status": review_status,
        "review_reason": review_reason,
        "created_at": deps.now_iso(),
        "updated_at": deps.now_iso(),
    }
    custom.append(persona)
    personas["custom"] = custom
    _write_json(_student_profile_path(sid, deps), profile)
    return {"ok": True, "student_id": sid, "persona": persona}


def student_persona_activate_api(
    student_id: str,
    persona_id: str,
    *,
    deps: StudentPersonaApiDeps,
) -> Dict[str, Any]:
    sid = str(student_id or "").strip()
    if not sid:
        return {"ok": False, "error": "missing_student_id"}
    target_persona_id = str(persona_id or "").strip()
    profile = _ensure_profile(sid, deps)
    personas = profile["personas"]
    if not target_persona_id:
        personas["active_persona_id"] = ""
        _write_json(_student_profile_path(sid, deps), profile)
        return {"ok": True, "student_id": sid, "active_persona_id": ""}

    listing = student_personas_get_api(sid, deps=deps)
    if not listing.get("ok"):
        return listing
    assigned_ids = {str(item.get("persona_id") or "").strip() for item in listing.get("assigned", [])}
    custom_ids = {
        str(item.get("persona_id") or "").strip()
        for item in listing.get("custom", [])
        if str(item.get("review_status") or "").strip().lower() == "approved"
    }
    if target_persona_id not in assigned_ids and target_persona_id not in custom_ids:
        return {"ok": False, "error": "persona_not_available"}

    personas["active_persona_id"] = target_persona_id
    _write_json(_student_profile_path(sid, deps), profile)
    return {"ok": True, "student_id": sid, "active_persona_id": target_persona_id}


def student_persona_custom_delete_api(
    student_id: str,
    persona_id: str,
    *,
    deps: StudentPersonaApiDeps,
) -> Dict[str, Any]:
    sid = str(student_id or "").strip()
    target_persona_id = str(persona_id or "").strip()
    if not sid:
        return {"ok": False, "error": "missing_student_id"}
    if not target_persona_id:
        return {"ok": False, "error": "missing_persona_id"}

    profile = _ensure_profile(sid, deps)
    personas = profile["personas"]
    custom_raw = personas.get("custom")
    custom = custom_raw if isinstance(custom_raw, list) else []
    original_size = len(custom)
    next_custom = [
        item
        for item in custom
        if not (isinstance(item, dict) and str(item.get("persona_id") or "").strip() == target_persona_id)
    ]
    removed = len(next_custom) < original_size
    personas["custom"] = next_custom
    if str(personas.get("active_persona_id") or "").strip() == target_persona_id:
        personas["active_persona_id"] = ""
    _write_json(_student_profile_path(sid, deps), profile)
    return {
        "ok": True,
        "student_id": sid,
        "removed": removed,
        "active_persona_id": str(personas.get("active_persona_id") or "").strip(),
    }


def student_persona_custom_update_api(
    student_id: str,
    persona_id: str,
    payload: Dict[str, Any],
    *,
    deps: StudentPersonaApiDeps,
) -> Dict[str, Any]:
    sid = str(student_id or "").strip()
    pid = str(persona_id or "").strip()
    if not sid:
        return {"ok": False, "error": "missing_student_id"}
    if not pid:
        return {"ok": False, "error": "missing_persona_id"}
    body = payload if isinstance(payload, dict) else {}

    profile = _ensure_profile(sid, deps)
    personas = profile["personas"]
    custom_raw = personas.get("custom")
    custom = custom_raw if isinstance(custom_raw, list) else []
    idx = next(
        (
            i
            for i, item in enumerate(custom)
            if isinstance(item, dict) and str(item.get("persona_id") or "").strip() == pid
        ),
        -1,
    )
    if idx < 0:
        return {"ok": False, "error": "custom_persona_not_found"}

    current = dict(custom[idx])
    if "name" in body:
        name = str(body.get("name") or "").strip()
        if not name:
            return {"ok": False, "error": "invalid_name"}
        current["name"] = name
    if "summary" in body:
        current["summary"] = str(body.get("summary") or "").strip()
    if "style_rules" in body:
        style_rules = _as_str_list(body.get("style_rules"), limit=20)
        if not style_rules:
            return {"ok": False, "error": "invalid_style_rules"}
        current["style_rules"] = style_rules
    if "few_shot_examples" in body:
        few_shot_examples = _as_str_list(body.get("few_shot_examples"), limit=10)
        if not few_shot_examples:
            return {"ok": False, "error": "invalid_few_shot_examples"}
        current["few_shot_examples"] = few_shot_examples

    review_status, review_reason = _review_custom_persona(
        str(current.get("name") or ""),
        _as_str_list(current.get("style_rules"), limit=20),
        _as_str_list(current.get("few_shot_examples"), limit=10),
    )
    current["review_status"] = review_status
    current["review_reason"] = review_reason
    current["updated_at"] = deps.now_iso()
    custom[idx] = current
    personas["custom"] = custom
    if review_status != "approved" and str(personas.get("active_persona_id") or "").strip() == pid:
        personas["active_persona_id"] = ""
    _write_json(_student_profile_path(sid, deps), profile)
    return {"ok": True, "student_id": sid, "persona": current}


def _build_persona_prompt(persona: Dict[str, Any]) -> str:
    name = str(persona.get("name") or persona.get("persona_id") or "未命名角色").strip() or "未命名角色"
    rules = _as_str_list(persona.get("style_rules"), limit=12)
    examples = _as_str_list(persona.get("few_shot_examples"), limit=5)
    lines: List[str] = [
        f"你当前启用了虚拟风格卡「{name}」。",
        "此风格卡只影响语气和讲解节奏，不改变事实正确性与教学约束。",
        "禁止声称你是真实历史人物或具备现实身份。",
        "每次回复最多使用一处角色化措辞；其余内容保持清晰、可执行、分步骤。",
    ]
    if rules:
        lines.append("风格规则：")
        for idx, item in enumerate(rules, start=1):
            lines.append(f"{idx}. {item}")
    if examples:
        lines.append("风格示例（仅供语气参考，不可照抄）：")
        for idx, item in enumerate(examples, start=1):
            lines.append(f"- 示例{idx}: {item}")
    return "\n".join(lines)


def resolve_student_persona_runtime(
    student_id: str,
    persona_id: str,
    *,
    deps: StudentPersonaApiDeps,
) -> Dict[str, Any]:
    sid = str(student_id or "").strip()
    pid = str(persona_id or "").strip()
    if not sid:
        return {"ok": False, "error": "missing_student_id"}
    if not pid:
        return {"ok": False, "error": "missing_persona_id"}

    listing = student_personas_get_api(sid, deps=deps)
    if not listing.get("ok"):
        return {"ok": False, "error": str(listing.get("error") or "persona_not_available")}

    persona: Optional[Dict[str, Any]] = None
    for item in listing.get("assigned", []):
        if isinstance(item, dict) and str(item.get("persona_id") or "").strip() == pid:
            persona = dict(item)
            break
    if persona is None:
        for item in listing.get("custom", []):
            if not isinstance(item, dict):
                continue
            if str(item.get("persona_id") or "").strip() != pid:
                continue
            if str(item.get("review_status") or "").strip().lower() != "approved":
                continue
            persona = dict(item)
            break
    if persona is None:
        return {"ok": False, "error": "persona_not_available"}

    profile = _ensure_profile(sid, deps)
    personas = profile.get("personas") if isinstance(profile.get("personas"), dict) else {}
    notified_raw = personas.get("first_activation_notified_ids") if isinstance(personas, dict) else []
    notified_ids = {
        str(item or "").strip()
        for item in notified_raw
        if str(item or "").strip()
    }
    first_notice = pid not in notified_ids
    if first_notice and isinstance(personas, dict):
        notified_ids.add(pid)
        personas["first_activation_notified_ids"] = sorted(notified_ids)
        _write_json(_student_profile_path(sid, deps), profile)

    return {
        "ok": True,
        "student_id": sid,
        "persona_id": pid,
        "persona_name": str(persona.get("name") or pid),
        "persona_prompt": _build_persona_prompt(persona),
        "first_notice": first_notice,
    }


def student_persona_avatar_upload_api(
    student_id: str,
    persona_id: str,
    *,
    filename: str,
    content: bytes,
    deps: StudentPersonaApiDeps,
) -> Dict[str, Any]:
    sid = str(student_id or "").strip()
    pid = str(persona_id or "").strip()
    if not sid:
        return {"ok": False, "error": "missing_student_id"}
    if not pid:
        return {"ok": False, "error": "missing_persona_id"}

    profile = _ensure_profile(sid, deps)
    personas = profile["personas"]
    custom_raw = personas.get("custom")
    custom = custom_raw if isinstance(custom_raw, list) else []
    idx = next(
        (
            i
            for i, item in enumerate(custom)
            if isinstance(item, dict) and str(item.get("persona_id") or "").strip() == pid
        ),
        -1,
    )
    if idx < 0:
        return {"ok": False, "error": "custom_persona_not_found"}

    try:
        ext = _validate_avatar_file(filename, content)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    folder = _student_avatar_dir(sid, pid, deps)
    folder.mkdir(parents=True, exist_ok=True)
    file_name = f"avatar_{uuid.uuid4().hex[:10]}.{ext}"
    target = folder / file_name
    target.write_bytes(content)
    avatar_url = f"/student/personas/avatar/{sid}/{pid}/{file_name}"
    updated = dict(custom[idx])
    updated["avatar_url"] = avatar_url
    updated["updated_at"] = deps.now_iso()
    custom[idx] = updated
    personas["custom"] = custom
    _write_json(_student_profile_path(sid, deps), profile)
    return {"ok": True, "student_id": sid, "persona_id": pid, "avatar_url": avatar_url}


def resolve_student_persona_avatar_path(
    student_id: str,
    persona_id: str,
    file_name: str,
    *,
    deps: StudentPersonaApiDeps,
) -> Optional[Path]:
    sid = str(student_id or "").strip()
    pid = str(persona_id or "").strip()
    fname = str(file_name or "").strip()
    if not sid or not pid or not fname:
        return None
    if "/" in fname or "\\" in fname:
        return None
    try:
        folder = _student_avatar_dir(sid, pid, deps)
    except ValueError:
        return None
    target = (folder / fname).resolve()
    if target != folder and folder not in target.parents:
        return None
    if not target.exists() or not target.is_file():
        return None
    return target
