from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException

from ..api_models import (
    AdminBulkMoveRequest,
    AdminEnrollClassRequest,
    AdminEnrollRequest,
    AdminRenameClassRequest,
    AdminRosterRequest,
    AdminSubjectAddRequest,
    AdminUnenrollRequest,
)
from ..auth.identity_graph_service import conflict_status
from ..auth_registry_service import build_auth_registry_store
from ..auth_service import AuthError, AuthPrincipal, require_principal


def _require_admin_principal() -> AuthPrincipal:
    """Identity graph routes require a real admin principal.

    Do not fall back to admin_local when AUTH_REQUIRED=0 and
    require_principal returns None. Tests mint an admin Bearer token.
    """
    try:
        principal = require_principal(roles=("admin",))
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    if principal is None:
        raise HTTPException(status_code=401, detail="missing_authorization")
    return principal


def _build_store(core: Any) -> Any:
    return build_auth_registry_store(data_dir=core.DATA_DIR)


def _raise_identity_result(result: dict[str, Any]) -> dict[str, Any]:
    if result.get("ok"):
        return result
    error = str(result.get("error") or "invalid_request")
    raise HTTPException(status_code=conflict_status(error), detail=error)


def register_identity_admin_routes(router: APIRouter, core: Any) -> None:
    @router.get("/auth/admin/subjects")
    def auth_admin_subjects_list() -> Any:
        _require_admin_principal()
        return _build_store(core).list_subjects()

    @router.post("/auth/admin/subjects")
    def auth_admin_subjects_add(req: AdminSubjectAddRequest) -> Any:
        _require_admin_principal()
        return _raise_identity_result(
            _build_store(core).add_subject(
                subject_id=req.subject_id,
                display_name=req.display_name,
                pack_id=str(req.pack_id or ""),
            )
        )

    @router.post("/auth/admin/subjects/seed")
    def auth_admin_subjects_seed() -> Any:
        _require_admin_principal()
        return _build_store(core).seed_subjects()

    @router.get("/auth/admin/roster")
    def auth_admin_roster_list(teacher_id: Optional[str] = None) -> Any:
        _require_admin_principal()
        return _build_store(core).list_roster(teacher_id=teacher_id)

    @router.post("/auth/admin/roster")
    def auth_admin_roster_add(req: AdminRosterRequest) -> Any:
        _require_admin_principal()
        return _raise_identity_result(
            _build_store(core).add_roster(
                teacher_id=req.teacher_id,
                subject_id=req.subject_id,
                class_name=req.class_name,
                allow_empty=bool(req.allow_empty),
            )
        )

    @router.delete("/auth/admin/roster")
    def auth_admin_roster_remove(
        teacher_id: str,
        subject_id: str,
        class_name: str,
    ) -> Any:
        _require_admin_principal()
        return _raise_identity_result(
            _build_store(core).remove_roster(
                teacher_id=teacher_id,
                subject_id=subject_id,
                class_name=class_name,
            )
        )

    @router.get("/auth/admin/enrollments")
    def auth_admin_enrollments_list(subject_id: str, class_name: str) -> Any:
        _require_admin_principal()
        return _raise_identity_result(
            _build_store(core).list_enrollments(subject_id=subject_id, class_name=class_name)
        )

    @router.post("/auth/admin/enrollments/enroll-class")
    def auth_admin_enroll_class(req: AdminEnrollClassRequest) -> Any:
        _require_admin_principal()
        return _raise_identity_result(
            _build_store(core).enroll_class(
                teacher_id=req.teacher_id,
                subject_id=req.subject_id,
                class_name=req.class_name,
                resync=bool(req.resync),
            )
        )

    @router.post("/auth/admin/enrollments/enroll")
    def auth_admin_enroll(req: AdminEnrollRequest) -> Any:
        _require_admin_principal()
        return _raise_identity_result(
            _build_store(core).enroll(
                student_id=req.student_id,
                subject_id=req.subject_id,
                class_name=req.class_name,
                teacher_id=str(req.teacher_id or ""),
            )
        )

    @router.post("/auth/admin/enrollments/unenroll")
    def auth_admin_unenroll(req: AdminUnenrollRequest) -> Any:
        _require_admin_principal()
        return _raise_identity_result(
            _build_store(core).unenroll(
                student_id=req.student_id,
                subject_id=req.subject_id,
                class_name=req.class_name,
            )
        )

    @router.post("/auth/admin/enrollments/bulk-move")
    def auth_admin_bulk_move(req: AdminBulkMoveRequest) -> Any:
        _require_admin_principal()
        return _raise_identity_result(
            _build_store(core).bulk_move_enrollments(
                subject_id=req.subject_id,
                from_class=req.from_class,
                to_class=req.to_class,
                student_ids=req.student_ids,
            )
        )

    @router.post("/auth/admin/enrollments/rename-class")
    def auth_admin_rename_class(req: AdminRenameClassRequest) -> Any:
        _require_admin_principal()
        return _raise_identity_result(
            _build_store(core).rename_class(
                subject_id=req.subject_id,
                old_class_name=req.old_class_name,
                new_class_name=req.new_class_name,
            )
        )
