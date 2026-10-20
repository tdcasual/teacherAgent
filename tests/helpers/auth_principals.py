from __future__ import annotations

import time
from pathlib import Path

from services.api.auth_registry_service import build_auth_registry_store
from services.api.auth_service import mint_test_token


def _subject_token_version(store, *, role: str, subject_id: str) -> int | None:
    table, id_field = {
        "teacher": ("teacher_auth", "teacher_id"),
        "student": ("student_auth", "student_id"),
        "admin": ("admin_auth", "admin_username"),
    }[role]
    with store._connect() as conn:
        row = conn.execute(
            f"SELECT token_version FROM {table} WHERE {id_field} = ?",
            (subject_id,),
        ).fetchone()
    if row is None:
        return None
    return int(row["token_version"])


def register_and_mint_bearer(
    tmp: Path, actor_id: str, role: str, *, secret: str, tenant_id: str = "school"
) -> dict[str, str]:
    claims: dict = {
        "sub": actor_id,
        "role": role,
        "tenant_id": tenant_id,
        "exp": int(time.time()) + 3600,
    }
    if role in {"teacher", "student", "admin"}:
        store = build_auth_registry_store(data_dir=tmp / "data")
        if role == "teacher":
            row = store._ensure_teacher_auth(
                teacher_id=actor_id, teacher_name=actor_id, email=None, regenerate_token=False
            )
            claims["tv"] = int(row["token_version"])  # 用该行，禁止写死 1
        elif role == "student":
            row = store._ensure_student_auth(
                student_id=actor_id, student_name=actor_id, class_name="c1", regenerate_token=False
            )
            claims["tv"] = int(row["token_version"])
        else:
            # admin：bootstrap 幂等且不 bump tv（auth/bootstrap_service.py:29-36）
            # 默认用户名 admin，不是 admin_a
            store.bootstrap_admin()
            tv = _subject_token_version(store, role="admin", subject_id=actor_id)
            if tv is None:
                # 缺行（例如 sub=admin_a）：不 INSERT；不带 tv → 今日 401
                pass
            else:
                claims["tv"] = tv
    # service 及其它非 tv 角色：不碰 registry、claims 不设 tv（与今日 _bearer payload 相同）
    token = mint_test_token(claims, secret=secret)
    return {"Authorization": f"Bearer {token}"}
