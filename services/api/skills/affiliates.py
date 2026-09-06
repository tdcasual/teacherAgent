from __future__ import annotations

from typing import Any, Optional

from .product import extra_skill_ids_for_teacher


def extra_skill_ids_from_core(core: Any, *, teacher_id: str) -> frozenset[str]:
    tid = str(teacher_id or "").strip()
    data_dir = getattr(core, "DATA_DIR", None)
    if not tid or data_dir is None:
        return frozenset()
    from ..auth_registry_service import build_auth_registry_store
    from ..subject_pack_service import load_pack

    store = build_auth_registry_store(data_dir=data_dir)
    return extra_skill_ids_for_teacher(
        teacher_id=tid,
        list_roster=store.list_roster,
        load_pack=load_pack,
    )


def extra_skill_ids_for_principal(core: Any, principal: Optional[Any]) -> frozenset[str]:
    if principal is None:
        return frozenset()
    if str(getattr(principal, "role", "") or "").strip() != "teacher":
        return frozenset()
    return extra_skill_ids_from_core(core, teacher_id=str(getattr(principal, "actor_id", "") or ""))


def extra_skill_ids_for_role(core: Any, role_hint: Optional[str]) -> frozenset[str]:
    if str(role_hint or "").strip() != "teacher":
        return frozenset()
    from ..auth_service import get_current_principal

    return extra_skill_ids_for_principal(core, get_current_principal())
