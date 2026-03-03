from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import services.api.auth_registry_service as auth_registry_service


def test_auth_registry_delegates_login_to_login_service() -> None:
    source = Path("services/api/auth_registry_service.py").read_text(encoding="utf-8")
    assert "from .auth.login_service import handle_login" in source


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
