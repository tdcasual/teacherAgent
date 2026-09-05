from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..api_models import (
    AdminLoginRequest,
    AdminTeacherCreateRequest,
    AdminTeacherResetPasswordRequest,
    AdminTeacherSetDisabledRequest,
    AuthExportTokensRequest,
    AuthResetTokenRequest,
    StudentIdentifyRequest,
    StudentLoginRequest,
    StudentSetPasswordRequest,
    TeacherIdentifyRequest,
    TeacherLoginRequest,
    TeacherSetPasswordRequest,
    TeacherStudentPasswordResetRequest,
)
from ..auth.student_provision_service import MAX_CSV_BYTES, import_students
from ..auth_registry_service import build_auth_registry_store
from ..auth_service import AuthError, access_token_ttl_sec, mint_access_token, require_principal
from .auth_identity_route_handlers import _require_admin_principal, register_identity_admin_routes


def _mask_login_failure(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("ok"):
        return payload
    error = str(payload.get("error") or "")
    if error in {
        "missing_candidate_id",
        "invalid_credential_type",
        "missing_credential",
        "missing_username",
        "missing_password",
    }:
        return payload
    return {"ok": False, "error": "invalid_credential"}


def _teacher_or_admin_actor() -> tuple[str, str]:
    try:
        principal = require_principal(roles=("teacher", "admin"))
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    if principal is None:
        return "teacher_local", "teacher"
    return principal.actor_id, principal.role


def _build_store(core: Any) -> Any:
    return build_auth_registry_store(data_dir=core.DATA_DIR)


def _raise_not_found(result: dict[str, Any]) -> None:
    if not result.get("ok") and result.get("error") == "not_found":
        raise HTTPException(status_code=404, detail="not_found")


def _raise_student_reset_result(result: dict[str, Any]) -> dict[str, Any]:
    _raise_not_found(result)
    if result.get("ok"):
        return result
    error = str(result.get("error") or "")
    if error == "forbidden":
        raise HTTPException(status_code=403, detail="forbidden")
    if error == "roster_required":
        raise HTTPException(status_code=400, detail="roster_required")
    return result


def _student_login_response(login_result: dict[str, Any]) -> dict[str, Any]:
    if not login_result.get("ok"):
        return _mask_login_failure(login_result)
    token_version = int(login_result.get("token_version") or 1)
    subject_id = str(login_result.get("subject_id") or "").strip()
    token = mint_access_token(subject_id=subject_id, role="student", token_version=token_version)
    return {
        "ok": True,
        "access_token": token,
        "expires_in": access_token_ttl_sec(),
        "role": "student",
        "subject_id": subject_id,
        "student": login_result.get("student") or {},
        "password_set": bool(login_result.get("password_set")),
    }


def _teacher_login_response(login_result: dict[str, Any]) -> dict[str, Any]:
    if not login_result.get("ok"):
        return _mask_login_failure(login_result)
    token_version = int(login_result.get("token_version") or 1)
    subject_id = str(login_result.get("subject_id") or "").strip()
    token = mint_access_token(subject_id=subject_id, role="teacher", token_version=token_version)
    return {
        "ok": True,
        "access_token": token,
        "expires_in": access_token_ttl_sec(),
        "role": "teacher",
        "subject_id": subject_id,
        "teacher": login_result.get("teacher") or {},
        "password_set": bool(login_result.get("password_set")),
    }


def _register_student_auth_routes(router: APIRouter, core: Any) -> None:
    @router.post("/auth/student/identify")
    def auth_student_identify(req: StudentIdentifyRequest) -> Any:
        return _build_store(core).identify_student(name=req.name, class_name=req.class_name)

    @router.post("/auth/student/login")
    def auth_student_login(req: StudentLoginRequest) -> Any:
        login_result = _build_store(core).login(
            role="student",
            candidate_id=req.candidate_id,
            credential_type=req.credential_type,
            credential=req.credential,
        )
        return _student_login_response(login_result)

    @router.post("/auth/student/set-password")
    def auth_student_set_password(req: StudentSetPasswordRequest) -> Any:
        return _build_store(core).set_password(
            role="student",
            candidate_id=req.candidate_id,
            credential_type=req.credential_type,
            credential=req.credential,
            new_password=req.new_password,
            actor_id=req.candidate_id,
            actor_role="student",
        )


def _register_teacher_auth_routes(router: APIRouter, core: Any) -> None:
    @router.post("/auth/teacher/identify")
    def auth_teacher_identify(req: TeacherIdentifyRequest) -> Any:
        return _build_store(core).identify_teacher(name=req.name, email=req.email)

    @router.post("/auth/teacher/login")
    def auth_teacher_login(req: TeacherLoginRequest) -> Any:
        login_result = _build_store(core).login(
            role="teacher",
            candidate_id=req.candidate_id,
            credential_type=req.credential_type,
            credential=req.credential,
        )
        return _teacher_login_response(login_result)

    @router.post("/auth/teacher/set-password")
    def auth_teacher_set_password(req: TeacherSetPasswordRequest) -> Any:
        return _build_store(core).set_password(
            role="teacher",
            candidate_id=req.candidate_id,
            credential_type=req.credential_type,
            credential=req.credential,
            new_password=req.new_password,
            actor_id=req.candidate_id,
            actor_role="teacher",
        )

    @router.post("/auth/teacher/student/reset-passwords")
    def auth_teacher_student_reset_passwords(req: TeacherStudentPasswordResetRequest) -> Any:
        actor_id, actor_role = _teacher_or_admin_actor()
        result = _build_store(core).reset_student_passwords(
            scope=req.scope,
            student_id=req.student_id,
            class_name=req.class_name,
            new_password=req.new_password,
            actor_id=actor_id,
            actor_role=actor_role,
        )
        return _raise_student_reset_result(result)


def _raise_admin_teacher_create_result(result: dict[str, Any]) -> dict[str, Any]:
    if result.get("ok"):
        return result
    error = str(result.get("error") or "invalid_request")
    if error in {"teacher_id_taken", "email_taken"}:
        raise HTTPException(status_code=409, detail=error)
    raise HTTPException(status_code=400, detail=error)


def _raise_admin_students_import_result(result: dict[str, Any]) -> dict[str, Any]:
    if result.get("ok"):
        return result
    error = str(result.get("error") or "invalid_request")
    raise HTTPException(status_code=400, detail=error)


def _truthy_form_flag(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _register_admin_teacher_routes(router: APIRouter, core: Any) -> None:
    @router.post("/auth/admin/teacher/create", status_code=201)
    def auth_admin_teacher_create(req: AdminTeacherCreateRequest) -> Any:
        principal = _require_admin_principal()
        result = _build_store(core).create_teacher(
            teacher_name=req.teacher_name,
            email=req.email,
            teacher_id=req.teacher_id,
            actor_id=principal.actor_id,
            actor_role=principal.role,
        )
        return _raise_admin_teacher_create_result(result)

    @router.get("/auth/admin/teacher/list")
    def auth_admin_teacher_list() -> Any:
        _require_admin_principal()
        return _build_store(core).list_teacher_auth_status()

    @router.post("/auth/admin/teacher/set-disabled")
    def auth_admin_teacher_set_disabled(req: AdminTeacherSetDisabledRequest) -> Any:
        principal = _require_admin_principal()
        result = _build_store(core).set_teacher_disabled(
            target_id=req.target_id,
            is_disabled=req.is_disabled,
            actor_id=principal.actor_id,
            actor_role=principal.role,
        )
        _raise_not_found(result)
        return result

    @router.post("/auth/admin/teacher/reset-password")
    def auth_admin_teacher_reset_password(req: AdminTeacherResetPasswordRequest) -> Any:
        principal = _require_admin_principal()
        result = _build_store(core).reset_teacher_password(
            target_id=req.target_id,
            new_password=req.new_password,
            actor_id=principal.actor_id,
            actor_role=principal.role,
        )
        _raise_not_found(result)
        return result

    @router.post("/auth/admin/students/import")
    async def auth_admin_students_import(
        file: UploadFile = File(...),
        reset_passwords: str = Form("false"),
    ) -> Any:
        principal = _require_admin_principal()
        raw = await file.read(MAX_CSV_BYTES + 1)
        result = import_students(
            _build_store(core),
            raw_csv=raw or b"",
            reset_passwords=_truthy_form_flag(reset_passwords),
            actor_id=principal.actor_id,
            actor_role=principal.role,
        )
        return _raise_admin_students_import_result(result)


def _register_admin_token_routes(router: APIRouter, core: Any) -> None:
    @router.post("/auth/admin/student/reset-token")
    def auth_admin_student_reset_token(req: AuthResetTokenRequest) -> Any:
        principal = _require_admin_principal()
        result = _build_store(core).reset_token(
            role="student",
            target_id=req.target_id,
            actor_id=principal.actor_id,
            actor_role=principal.role,
        )
        _raise_not_found(result)
        return result

    @router.post("/auth/admin/teacher/reset-token")
    def auth_admin_teacher_reset_token(req: AuthResetTokenRequest) -> Any:
        principal = _require_admin_principal()
        result = _build_store(core).reset_token(
            role="teacher",
            target_id=req.target_id,
            actor_id=principal.actor_id,
            actor_role=principal.role,
        )
        _raise_not_found(result)
        return result

    @router.post("/auth/admin/student/export-tokens")
    def auth_admin_student_export_tokens(req: AuthExportTokensRequest) -> Any:
        principal = _require_admin_principal()
        return _build_store(core).export_tokens(
            role="student",
            ids=req.ids,
            actor_id=principal.actor_id,
            actor_role=principal.role,
        )

    @router.post("/auth/admin/teacher/export-tokens")
    def auth_admin_teacher_export_tokens(req: AuthExportTokensRequest) -> Any:
        principal = _require_admin_principal()
        return _build_store(core).export_tokens(
            role="teacher",
            ids=req.ids,
            actor_id=principal.actor_id,
            actor_role=principal.role,
        )


def _register_admin_auth_routes(router: APIRouter, core: Any) -> None:
    @router.post("/auth/admin/login")
    def auth_admin_login(req: AdminLoginRequest) -> Any:
        login_result = _build_store(core).login_admin(username=req.username, password=req.password)
        if not login_result.get("ok"):
            return _mask_login_failure(login_result)
        subject_id = str(login_result.get("subject_id") or "").strip()
        token_version = int(login_result.get("token_version") or 1)
        try:
            token = mint_access_token(
                subject_id=subject_id, role="admin", token_version=token_version
            )
        except AuthError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)
        return {
            "ok": True,
            "access_token": token,
            "expires_in": access_token_ttl_sec(),
            "role": "admin",
            "subject_id": subject_id,
        }

    _register_admin_teacher_routes(router, core)
    _register_admin_token_routes(router, core)
    register_identity_admin_routes(router, core)


def register_auth_routes(router: APIRouter, core: Any) -> None:
    _register_student_auth_routes(router, core)
    _register_teacher_auth_routes(router, core)
    _register_admin_auth_routes(router, core)
