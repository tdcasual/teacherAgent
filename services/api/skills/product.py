from __future__ import annotations

from typing import Any, Callable, Iterable

PRODUCT_SKILL_IDS = frozenset(
    {
        "teacher-assignment-ops",
        "homework-generator",
        "student-coach",
    }
)


def is_product_skill(skill_id: str) -> bool:
    return str(skill_id or "").strip() in PRODUCT_SKILL_IDS


def product_skill_ids(skill_ids: Iterable[str]) -> list[str]:
    return [skill_id for skill_id in skill_ids if is_product_skill(skill_id)]


def visible_skill_ids(*, extra_skill_ids: Iterable[str] = ()) -> frozenset[str]:
    allowed = set(PRODUCT_SKILL_IDS)
    for skill_id in extra_skill_ids:
        text = str(skill_id or "").strip()
        if text:
            allowed.add(text)
    return frozenset(allowed)


def is_visible_skill(skill_id: str, *, extra_skill_ids: Iterable[str] = ()) -> bool:
    return str(skill_id or "").strip() in visible_skill_ids(extra_skill_ids=extra_skill_ids)


def affiliate_skill_ids_for_subjects(
    subject_ids: Iterable[str],
    *,
    load_pack: Callable[[str], Any],
) -> frozenset[str]:
    affiliates: set[str] = set()
    for subject_id in subject_ids:
        sid = str(subject_id or "").strip()
        if not sid:
            continue
        try:
            pack = load_pack(sid)
        except Exception:
            continue
        for skill_id in getattr(pack, "skill_affiliates", ()) or ():
            text = str(skill_id or "").strip()
            if text:
                affiliates.add(text)
    return frozenset(affiliates)


def extra_skill_ids_for_teacher(
    *,
    teacher_id: str,
    list_roster: Callable[..., Any],
    load_pack: Callable[[str], Any],
) -> frozenset[str]:
    tid = str(teacher_id or "").strip()
    if not tid:
        return frozenset()
    try:
        payload = list_roster(teacher_id=tid) or {}
    except Exception:
        return frozenset()
    items = payload.get("items") if isinstance(payload, dict) else None
    subjects = [
        str(item.get("subject_id") or "").strip()
        for item in (items or [])
        if isinstance(item, dict)
    ]
    return affiliate_skill_ids_for_subjects(subjects, load_pack=load_pack)
