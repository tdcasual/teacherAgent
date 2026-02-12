from __future__ import annotations

from typing import Any, Dict, Optional, Set

from fastapi import HTTPException

from ..auth_service import AuthError, resolve_teacher_scope


def scoped_teacher_id(teacher_id: Optional[str]) -> Optional[str]:
    try:
        return resolve_teacher_scope(teacher_id)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


def scoped_payload_teacher_id(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(payload or {})
    data["teacher_id"] = scoped_teacher_id(data.get("teacher_id"))
    return data


def ensure_ok_result(
    result: Dict[str, Any], *, not_found_errors: Optional[Set[str]] = None
) -> None:
    if result.get("ok"):
        return
    error = str(result.get("error") or "").strip()
    if error and not_found_errors and error in not_found_errors:
        raise HTTPException(status_code=404, detail=result)
    raise HTTPException(status_code=400, detail=result)


def ensure_ok_error_detail(
    result: Dict[str, Any],
    *,
    default_error: str = "invalid_request",
    not_found_errors: Optional[Set[str]] = None,
) -> None:
    if result.get("ok"):
        return
    error = str(result.get("error") or "").strip()
    if error and not_found_errors and error in not_found_errors:
        raise HTTPException(status_code=404, detail=error)
    raise HTTPException(status_code=400, detail=error or default_error)
