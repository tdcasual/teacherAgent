from __future__ import annotations

import base64
import json
import sqlite3
import time
from pathlib import Path

from fastapi.testclient import TestClient

from services.api.auth_registry_service import AuthRegistryStore, build_auth_registry_store
from services.api.auth_service import mint_test_token
from tests.helpers.app_factory import create_test_app


def _load_app(
    tmp_path: Path,
    *,
    secret: str,
    admin_username: str,
    admin_password: str,
):
    return create_test_app(
        tmp_path,
        env_overrides={
            "MASTER_KEY_DEV_DEFAULT": "dev-key",
            "AUTH_REQUIRED": "1",
            "AUTH_TOKEN_SECRET": secret,
            "ADMIN_USERNAME": admin_username,
            "ADMIN_PASSWORD": admin_password,
        },
    )


def _token_claims(token: str) -> dict:
    payload = str(token or "").split(".", 1)[0]
    padding = "=" * (-len(payload) % 4)
    raw = base64.urlsafe_b64decode(payload + padding)
    return json.loads(raw.decode("utf-8"))


def test_admin_password_change_revokes_old_access_token(tmp_path: Path) -> None:
    secret = "admin-token-version-secret"
    admin_username = "principal_admin"
    admin_password = "AdminPass123"
    app_mod = _load_app(
        tmp_path,
        secret=secret,
        admin_username=admin_username,
        admin_password=admin_password,
    )
    client = TestClient(app_mod.app)

    login_res = client.post(
        "/auth/admin/login",
        json={"username": admin_username, "password": admin_password},
    )
    assert login_res.status_code == 200
    login_payload = login_res.json()
    assert login_payload.get("ok") is True
    access_token = str(login_payload.get("access_token") or "")
    assert access_token
    assert _token_claims(access_token).get("tv") == 1
    headers = {"Authorization": f"Bearer {access_token}"}

    before = client.get("/auth/admin/teacher/list", headers=headers)
    assert before.status_code == 200

    change_res = client.post(
        "/auth/admin/change-password",
        headers=headers,
        json={"current_password": admin_password, "new_password": "NewAdminPass123"},
    )
    assert change_res.status_code == 200
    change_payload = change_res.json()
    assert change_payload.get("ok") is True
    assert int(change_payload.get("token_version") or 0) == 2

    revoked = client.get("/auth/admin/teacher/list", headers=headers)
    assert revoked.status_code == 401
    assert revoked.json().get("detail") == "token_revoked"

    relogin = client.post(
        "/auth/admin/login",
        json={"username": admin_username, "password": "NewAdminPass123"},
    )
    assert relogin.status_code == 200
    new_token = str(relogin.json().get("access_token") or "")
    assert new_token
    assert _token_claims(new_token).get("tv") == 2
    after = client.get(
        "/auth/admin/teacher/list",
        headers={"Authorization": f"Bearer {new_token}"},
    )
    assert after.status_code == 200


def test_registered_admin_token_without_tv_is_revoked(tmp_path: Path) -> None:
    secret = "admin-missing-tv-secret"
    admin_username = "principal_admin"
    admin_password = "AdminPass123"
    app_mod = _load_app(
        tmp_path,
        secret=secret,
        admin_username=admin_username,
        admin_password=admin_password,
    )
    client = TestClient(app_mod.app)
    login_res = client.post(
        "/auth/admin/login",
        json={"username": admin_username, "password": admin_password},
    )
    assert login_res.status_code == 200
    assert login_res.json().get("ok") is True

    legacy = mint_test_token(
        {
            "sub": admin_username,
            "role": "admin",
            "exp": int(time.time()) + 3600,
        },
        secret=secret,
    )
    revoked = client.get(
        "/auth/admin/teacher/list",
        headers={"Authorization": f"Bearer {legacy}"},
    )
    assert revoked.status_code == 401
    assert revoked.json().get("detail") == "token_revoked"


def test_admin_disable_revokes_old_access_token(tmp_path: Path) -> None:
    secret = "admin-disable-token-version-secret"
    admin_username = "principal_admin"
    admin_password = "AdminPass123"
    app_mod = _load_app(
        tmp_path,
        secret=secret,
        admin_username=admin_username,
        admin_password=admin_password,
    )
    client = TestClient(app_mod.app)

    login_res = client.post(
        "/auth/admin/login",
        json={"username": admin_username, "password": admin_password},
    )
    assert login_res.status_code == 200
    access_token = str(login_res.json().get("access_token") or "")
    assert access_token
    headers = {"Authorization": f"Bearer {access_token}"}
    assert client.get("/auth/admin/teacher/list", headers=headers).status_code == 200

    store = build_auth_registry_store(data_dir=tmp_path / "data")
    disable_result = store.set_admin_disabled(
        username=admin_username,
        is_disabled=True,
        actor_id=admin_username,
        actor_role="admin",
    )
    assert disable_result.get("ok") is True
    assert disable_result.get("is_disabled") is True
    assert int(disable_result.get("token_version") or 0) == 2

    revoked = client.get("/auth/admin/teacher/list", headers=headers)
    assert revoked.status_code == 401
    assert revoked.json().get("detail") == "token_revoked"


def test_admin_auth_token_version_column_migrates_existing_table(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    db_path = data_dir / "auth" / "auth_registry.sqlite3"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            """
            CREATE TABLE admin_auth (
                admin_username TEXT PRIMARY KEY,
                username_norm TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                password_algo TEXT NOT NULL,
                password_set_at TEXT NOT NULL,
                failed_count INTEGER NOT NULL DEFAULT 0,
                locked_until TEXT,
                is_disabled INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            (
                "INSERT INTO admin_auth(admin_username, username_norm, password_hash, "
                "password_algo, password_set_at, failed_count, locked_until, is_disabled, "
                "updated_at) VALUES (?, ?, ?, ?, ?, 0, NULL, 0, ?)"
            ),
            ("legacy_admin", "legacy_admin", "hash", "pbkdf2_sha256", "2026-01-01T00:00:00+00:00",
             "2026-01-01T00:00:00+00:00"),
        )
        conn.commit()

    store = AuthRegistryStore(db_path=db_path, data_dir=data_dir)
    with store._connect() as conn:
        columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(admin_auth)")}
        assert "token_version" in columns
        version = conn.execute(
            "SELECT token_version FROM admin_auth WHERE admin_username = ?",
            ("legacy_admin",),
        ).fetchone()
    assert version is not None
    assert int(version[0] or 0) == 1
    assert store.token_version_matches(
        role="admin", subject_id="legacy_admin", token_version=1
    )
