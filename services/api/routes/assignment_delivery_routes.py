from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException

from ..auth_service import AuthError, auth_required, require_principal, resolve_student_scope


def _scoped_student_id(student_id: Optional[str]) -> str:
    try:
        scoped = resolve_student_scope(student_id, required_for_admin=False)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    sid = str(scoped or "").strip()
    if not sid:
        raise HTTPException(status_code=400, detail="student_id is required")
    return sid


def _require_assignment_access(assignment_id: str, *, core: Any) -> None:
    if not auth_required():
        return
    try:
        principal = require_principal(roles=("teacher", "student", "admin", "service"))
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    if principal is None:
        return
    if principal.role in {"teacher", "admin", "service"}:
        return

    # Student: enforce assignment scope using the same specificity rules as
    # assignment selection in assignment_today.
    try:
        folder = core.resolve_assignment_dir(assignment_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not folder.exists():
        raise HTTPException(status_code=404, detail="assignment not found")

    meta = core.load_assignment_meta(folder)
    class_name = ""
    try:
        profile_path = core.resolve_student_profile_path(principal.actor_id)
        profile = core.load_profile_file(profile_path)
        class_name = str(profile.get("class_name") or "").strip()
    except Exception:
        class_name = ""
    if int(core.assignment_specificity(meta, principal.actor_id, class_name)) <= 0:
        raise HTTPException(status_code=403, detail="forbidden_assignment_scope")


def register_assignment_delivery_routes(
    router: APIRouter, *, app_deps: Any, assignment_app: Any, core: Any
) -> None:
    @router.get("/assignment/{assignment_id}/download")
    async def assignment_download(assignment_id: str, file: str) -> Any:
        _require_assignment_access(assignment_id, core=core)
        return await assignment_app.download_assignment_file(
            assignment_id,
            file,
            deps=app_deps,
        )

    @router.get("/assignment/today")
    async def assignment_today(
        student_id: str,
        date: Optional[str] = None,
        auto_generate: bool = False,
        generate: bool = True,
        per_kp: int = 5,
    ) -> Any:
        sid = _scoped_student_id(student_id)
        return await assignment_app.get_assignment_today(
            student_id=sid,
            date=date,
            auto_generate=auto_generate,
            generate=generate,
            per_kp=per_kp,
            deps=app_deps,
        )

    @router.get("/assignment/{assignment_id}")
    async def assignment_detail(assignment_id: str) -> Any:
        _require_assignment_access(assignment_id, core=core)
        # Keep compatibility with tests and legacy monkeypatch surface on app_core.
        return core._get_assignment_detail_api_impl(
            assignment_id,
            deps=core._assignment_api_deps(),
        )
