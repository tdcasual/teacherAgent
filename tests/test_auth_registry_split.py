from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import services.api.auth_registry_service as auth_registry_service

# Ratcheted after identify/bootstrap extraction. Do not raise.
_AUTH_REGISTRY_MAX_LINES = 1700


def test_auth_registry_line_budget() -> None:
    source = Path("services/api/auth_registry_service.py").read_text(encoding="utf-8")
    line_count = len(source.splitlines())
    assert line_count <= _AUTH_REGISTRY_MAX_LINES, (
        f"auth_registry_service.py is {line_count} lines "
        f"(limit {_AUTH_REGISTRY_MAX_LINES}). Extract remaining god-file logic."
    )


def test_auth_registry_delegates_login_to_login_service() -> None:
    source = Path("services/api/auth_registry_service.py").read_text(encoding="utf-8")
    assert "from .auth.login_service import handle_login" in source


def test_auth_registry_delegates_identify_to_identify_service() -> None:
    source = Path("services/api/auth_registry_service.py").read_text(encoding="utf-8")
    assert (
        "from .auth.identify_service import handle_identify_student, handle_identify_teacher"
        in source
    )


def test_auth_registry_delegates_bootstrap_to_bootstrap_service() -> None:
    source = Path("services/api/auth_registry_service.py").read_text(encoding="utf-8")
    assert "from .auth.bootstrap_service import" in source
    assert "handle_bootstrap_admin" in source
    assert "handle_bootstrap_teachers" in source


def test_auth_registry_login_calls_split_login_handler(monkeypatch: Any) -> None:
    captured: Dict[str, Any] = {}

    def _fake_handle_login(
        store: Any,
        *,
        role: str,
        candidate_id: str,
        credential_type: str,
        credential: str,
        **_: Any,
    ) -> Dict[str, Any]:
        captured["store"] = store
        captured["role"] = role
        captured["candidate_id"] = candidate_id
        captured["credential_type"] = credential_type
        captured["credential"] = credential
        return {"ok": True, "delegated": True}

    monkeypatch.setattr(auth_registry_service, "handle_login", _fake_handle_login, raising=False)
    store = object.__new__(auth_registry_service.AuthRegistryStore)
    result = auth_registry_service.AuthRegistryStore.login(
        store,
        role="student",
        candidate_id="S001",
        credential_type="token",
        credential="token-123",
    )

    assert result == {"ok": True, "delegated": True}
    assert captured["store"] is store
    assert captured["role"] == "student"
    assert captured["candidate_id"] == "S001"
    assert captured["credential_type"] == "token"
    assert captured["credential"] == "token-123"


def test_auth_registry_identify_student_calls_split_handler(monkeypatch: Any) -> None:
    captured: Dict[str, Any] = {}

    def _fake_handle_identify_student(
        store: Any,
        *,
        name: str,
        class_name: str | None,
    ) -> Dict[str, Any]:
        captured["store"] = store
        captured["name"] = name
        captured["class_name"] = class_name
        return {"ok": True, "delegated": True}

    monkeypatch.setattr(
        auth_registry_service,
        "handle_identify_student",
        _fake_handle_identify_student,
        raising=False,
    )
    store = object.__new__(auth_registry_service.AuthRegistryStore)
    result = auth_registry_service.AuthRegistryStore.identify_student(
        store,
        name="刘昊然",
        class_name="高二2403班",
    )
    assert result == {"ok": True, "delegated": True}
    assert captured["store"] is store
    assert captured["name"] == "刘昊然"
    assert captured["class_name"] == "高二2403班"


def test_auth_registry_bootstrap_admin_calls_split_handler(monkeypatch: Any) -> None:
    captured: Dict[str, Any] = {}

    def _fake_handle_bootstrap_admin(store: Any, **kwargs: Any) -> Dict[str, Any]:
        captured["store"] = store
        captured["kwargs"] = kwargs
        return {"ok": True, "created": True, "delegated": True}

    monkeypatch.setattr(
        auth_registry_service,
        "handle_bootstrap_admin",
        _fake_handle_bootstrap_admin,
        raising=False,
    )
    store = object.__new__(auth_registry_service.AuthRegistryStore)
    result = auth_registry_service.AuthRegistryStore.bootstrap_admin(store)
    assert result == {"ok": True, "created": True, "delegated": True}
    assert captured["store"] is store
