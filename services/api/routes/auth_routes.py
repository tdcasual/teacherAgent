from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from ..api_models import (
    AuthExportTokensRequest,
    AuthResetTokenRequest,
    StudentIdentifyRequest,
    StudentLoginRequest,
    StudentSetPasswordRequest,
    TeacherIdentifyRequest,
    TeacherLoginRequest,
    TeacherSetPasswordRequest,
)
from ..auth_registry_service import build_auth_registry_store
from ..auth_service import AuthError, access_token_ttl_sec, mint_access_token, require_principal


def _admin_actor() -> tuple[str, str]:
    try:
        principal = require_principal(roles=("admin",))
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    if principal is None:
        # auth disabled: keep local development flow available
        return "admin_local", "admin"
    return principal.actor_id, principal.role


def register_auth_routes(router: APIRouter, core: Any) -> None:
    @router.post("/auth/student/identify")
    def auth_student_identify(req: StudentIdentifyRequest) -> Any:
        store = build_auth_registry_store(data_dir=core.DATA_DIR)
        return store.identify_student(name=req.name, class_name=req.class_name)

    @router.post("/auth/student/login")
    def auth_student_login(req: StudentLoginRequest) -> Any:
        store = build_auth_registry_store(data_dir=core.DATA_DIR)
        login_result = store.login(
            role="student",
            candidate_id=req.candidate_id,
            credential_type=req.credential_type,
            credential=req.credential,
        )
        if not login_result.get("ok"):
            return login_result
        token_version = int(login_result.get("token_version") or 1)
        subject_id = str(login_result.get("subject_id") or "").strip()
        token = mint_access_token(
            subject_id=subject_id,
            role="student",
            token_version=token_version,
        )
        return {
            "ok": True,
            "access_token": token,
            "expires_in": access_token_ttl_sec(),
            "role": "student",
            "subject_id": subject_id,
            "student": login_result.get("student") or {},
            "password_set": bool(login_result.get("password_set")),
        }

    @router.post("/auth/student/set-password")
    def auth_student_set_password(req: StudentSetPasswordRequest) -> Any:
        store = build_auth_registry_store(data_dir=core.DATA_DIR)
        return store.set_password(
            role="student",
            candidate_id=req.candidate_id,
            credential_type=req.credential_type,
            credential=req.credential,
            new_password=req.new_password,
            actor_id=req.candidate_id,
            actor_role="student",
        )

    @router.post("/auth/teacher/identify")
    def auth_teacher_identify(req: TeacherIdentifyRequest) -> Any:
        store = build_auth_registry_store(data_dir=core.DATA_DIR)
        return store.identify_teacher(name=req.name, email=req.email)

    @router.post("/auth/teacher/login")
    def auth_teacher_login(req: TeacherLoginRequest) -> Any:
        store = build_auth_registry_store(data_dir=core.DATA_DIR)
        login_result = store.login(
            role="teacher",
            candidate_id=req.candidate_id,
            credential_type=req.credential_type,
            credential=req.credential,
        )
        if not login_result.get("ok"):
            return login_result
        token_version = int(login_result.get("token_version") or 1)
        subject_id = str(login_result.get("subject_id") or "").strip()
        token = mint_access_token(
            subject_id=subject_id,
            role="teacher",
            token_version=token_version,
        )
        return {
            "ok": True,
            "access_token": token,
            "expires_in": access_token_ttl_sec(),
            "role": "teacher",
            "subject_id": subject_id,
            "teacher": login_result.get("teacher") or {},
            "password_set": bool(login_result.get("password_set")),
        }

    @router.post("/auth/teacher/set-password")
    def auth_teacher_set_password(req: TeacherSetPasswordRequest) -> Any:
        store = build_auth_registry_store(data_dir=core.DATA_DIR)
        return store.set_password(
            role="teacher",
            candidate_id=req.candidate_id,
            credential_type=req.credential_type,
            credential=req.credential,
            new_password=req.new_password,
            actor_id=req.candidate_id,
            actor_role="teacher",
        )

    @router.post("/auth/admin/student/reset-token")
    def auth_admin_student_reset_token(req: AuthResetTokenRequest) -> Any:
        actor_id, actor_role = _admin_actor()
        store = build_auth_registry_store(data_dir=core.DATA_DIR)
        result = store.reset_token(
            role="student",
            target_id=req.target_id,
            actor_id=actor_id,
            actor_role=actor_role,
        )
        if not result.get("ok") and result.get("error") == "not_found":
            raise HTTPException(status_code=404, detail="not_found")
        return result

    @router.post("/auth/admin/teacher/reset-token")
    def auth_admin_teacher_reset_token(req: AuthResetTokenRequest) -> Any:
        actor_id, actor_role = _admin_actor()
        store = build_auth_registry_store(data_dir=core.DATA_DIR)
        result = store.reset_token(
            role="teacher",
            target_id=req.target_id,
            actor_id=actor_id,
            actor_role=actor_role,
        )
        if not result.get("ok") and result.get("error") == "not_found":
            raise HTTPException(status_code=404, detail="not_found")
        return result

    @router.post("/auth/admin/student/export-tokens")
    def auth_admin_student_export_tokens(req: AuthExportTokensRequest) -> Any:
        actor_id, actor_role = _admin_actor()
        store = build_auth_registry_store(data_dir=core.DATA_DIR)
        return store.export_tokens(
            role="student",
            ids=req.ids,
            actor_id=actor_id,
            actor_role=actor_role,
        )

    @router.post("/auth/admin/teacher/export-tokens")
    def auth_admin_teacher_export_tokens(req: AuthExportTokensRequest) -> Any:
        actor_id, actor_role = _admin_actor()
        store = build_auth_registry_store(data_dir=core.DATA_DIR)
        return store.export_tokens(
            role="teacher",
            ids=req.ids,
            actor_id=actor_id,
            actor_role=actor_role,
        )
