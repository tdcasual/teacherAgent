from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from ..core_utils import normalize


def handle_identify_student(
    store: Any,
    *,
    name: str,
    class_name: Optional[str],
) -> Dict[str, Any]:
    q_name = str(name or "").strip()
    q_class = str(class_name or "").strip()
    if not q_name:
        return {"ok": False, "error": "missing_name", "message": "请先输入姓名。"}

    profiles = _match_student_profiles(store, name=q_name, class_name=q_class)
    if not profiles:
        return {
            "ok": False,
            "error": "not_found",
            "message": "未找到该学生，请检查姓名或班级。",
        }

    candidates = _student_identify_candidates(store, profiles)
    if not candidates:
        return {
            "ok": False,
            "error": "not_found",
            "message": "未找到该学生，请检查姓名或班级。",
        }
    if len(candidates) > 1:
        return {
            "ok": False,
            "error": "multiple",
            "message": "同名学生，请补充班级。",
            "candidates": candidates[:10],
        }
    return {"ok": True, **candidates[0]}


def handle_identify_teacher(
    store: Any,
    *,
    name: str,
    email: Optional[str],
) -> Dict[str, Any]:
    store.bootstrap_teachers(regenerate_token=False)

    q_name = str(name or "").strip()
    q_email = str(email or "").strip()
    if not q_name:
        return {"ok": False, "error": "missing_name", "message": "请先输入教师姓名。"}

    name_norm = normalize(q_name)
    email_norm = normalize(q_email)
    with store._connect() as conn:
        rows = list(
            conn.execute(
                (
                    "SELECT teacher_id, teacher_name, email, name_norm, email_norm, password_hash "
                    "FROM teacher_auth WHERE name_norm = ? ORDER BY teacher_id"
                ),
                (name_norm,),
            ).fetchall()
        )

    if email_norm:
        rows = [row for row in rows if normalize(str(row["email"] or "")) == email_norm]

    if not rows:
        msg = "未找到该教师，请检查姓名或邮箱。" if q_email else "未找到该教师，请检查姓名。"
        return {"ok": False, "error": "not_found", "message": msg}

    if len(rows) > 1 and not email_norm:
        return {
            "ok": False,
            "error": "multiple",
            "message": "同名教师，请补充邮箱进行确认。",
            "need_email_disambiguation": True,
            "candidates": _teacher_disambiguation_candidates(store, rows),
        }

    if len(rows) > 1:
        return {
            "ok": False,
            "error": "multiple",
            "message": "姓名+邮箱仍无法唯一定位，请联系管理员处理重复数据。",
            "need_email_disambiguation": True,
        }

    return {"ok": True, **_public_teacher_identify_item(store, rows[0])}


def _match_student_profiles(store: Any, *, name: str, class_name: str) -> List[Dict[str, str]]:
    name_norm = normalize(name)
    class_norm = normalize(class_name)
    # Roster CSV writes student_auth only; profiles JSON is not the login source.
    profiles = [
        item
        for item in store._list_student_identities()
        if normalize(item.get("student_name", "")) == name_norm
    ]
    if class_norm:
        profiles = [
            item for item in profiles if normalize(item.get("class_name", "")) == class_norm
        ]
    return profiles


def _public_student_identify_item(store: Any, ensured: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "candidate_id": store.issue_opaque_candidate_id(
            role="student",
            subject_id=str(ensured.get("student_id") or ""),
        ),
        "student": {
            "student_name": str(ensured.get("student_name") or ""),
            "class_name": str(ensured.get("class_name") or ""),
        },
        "password_set": bool(ensured.get("password_hash")),
    }


def _student_identify_candidates(
    store: Any, profiles: Sequence[Dict[str, str]]
) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    for profile in profiles:
        ensured = store._ensure_student_auth(
            student_id=str(profile.get("student_id") or "").strip(),
            student_name=str(profile.get("student_name") or "").strip(),
            class_name=str(profile.get("class_name") or "").strip(),
            regenerate_token=False,
        )
        if not ensured:
            continue
        candidates.append(_public_student_identify_item(store, ensured))
    return candidates


def _public_teacher_identify_item(store: Any, row: Any) -> Dict[str, Any]:
    return {
        "candidate_id": store.issue_opaque_candidate_id(
            role="teacher",
            subject_id=str(row["teacher_id"] or ""),
        ),
        "teacher": {
            "teacher_name": str(row["teacher_name"] or ""),
            "email": str(row["email"] or ""),
        },
        "password_set": bool(str(row["password_hash"] or "").strip()),
    }


def _teacher_disambiguation_candidates(store: Any, rows: Sequence[Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in rows[:10]:
        item = _public_teacher_identify_item(store, row)
        out.append({"candidate_id": item["candidate_id"], "teacher": item["teacher"]})
    return out
