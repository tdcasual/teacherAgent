from __future__ import annotations

import base64
import json
import sqlite3
import time
from pathlib import Path

from fastapi.testclient import TestClient

from services.api.auth_registry_service import AuthRegistryStore, build_auth_registry_store
from services.api.auth_service import mint_access_token
from tests.helpers.app_factory import create_test_app


def _load_app(tmp_path: Path, *, secret: str, admin_username: str, admin_password: str):
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
    payload = str(token or "").split(".")[0]
    padding = "=" * (-len(payload) % 4)
    raw = base64.urlsafe_b64decode(payload + padding)
    data = json.loads(raw.decode("utf-8"))
    assert isinstance(data, dict)
    return data


def _login_admin(client: TestClient, *, username: str, password: str) -> dict:
    res = client.post("/auth/admin/login", json={"username": username, "password": password})
    assert res.status_code == 200
    payload = res.json()
    assert payload.get("ok") is True
    return payload


def test_admin_login_mints_token_version(tmp_path: Path):
    secret = "admin-tv-mint-secret"
    username = "principal_admin"
    password = "AdminPass1"
    app_mod = _load_app(tmp_path, secret=secret, admin_username=username, admin_password=password)
    client = TestClient(app_mod.app)

    payload = _login_admin(client, username=username, password=password)
    token = str(payload.get("access_token") or "")
    assert token
    claims = _token_claims(token)
    assert claims.get("role") == "admin"
    assert claims.get("sub") == username
    assert int(claims.get("tv")) == 1

    protected = client.get(
        "/auth/admin/teacher/list",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert protected.status_code == 200
    assert protected.json().get("ok") is True


def test_admin_token_without_tv_is_rejected(tmp_path: Path):
    secret = "admin-tv-missing-secret"
    username = "principal_admin"
    password = "AdminPass1"
    app_mod = _load_app(tmp_path, secret=secret, admin_username=username, admin_password=password)
    client = TestClient(app_mod.app)
    _login_admin(client, username=username, password=password)

    token = mint_access_token(subject_id=username, role="admin")
    assert "tv" not in _token_claims(token)

    rejected = client.get(
        "/auth/admin/teacher/list",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert rejected.status_code == 401
    assert rejected.json().get("detail") == "token_revoked"


def test_unregistered_admin_token_without_tv_is_rejected(tmp_path: Path):
    secret = "admin-tv-unregistered-missing-secret"
    app_mod = _load_app(
        tmp_path,
        secret=secret,
        admin_username="principal_admin",
        admin_password="AdminPass1",
    )
    client = TestClient(app_mod.app)

    token = mint_access_token(subject_id="admin_a", role="admin")
    assert "tv" not in _token_claims(token)
    rejected = client.get(
        "/auth/admin/teacher/list",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert rejected.status_code == 401
    assert rejected.json().get("detail") == "token_revoked"


def test_unregistered_admin_token_with_tv_is_rejected(tmp_path: Path):
    secret = "admin-tv-unregistered-secret"
    app_mod = _load_app(
        tmp_path,
        secret=secret,
        admin_username="principal_admin",
        admin_password="AdminPass1",
    )
    client = TestClient(app_mod.app)

    token = mint_access_token(subject_id="admin_a", role="admin", token_version=1)
    rejected = client.get(
        "/auth/admin/teacher/list",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert rejected.status_code == 401
    assert rejected.json().get("detail") == "token_revoked"


def test_admin_password_rotation_revokes_old_token(tmp_path: Path):
    secret = "admin-tv-rotate-secret"
    username = "principal_admin"
    password = "AdminPass1"
    app_mod = _load_app(tmp_path, secret=secret, admin_username=username, admin_password=password)
    client = TestClient(app_mod.app)

    payload = _login_admin(client, username=username, password=password)
    old_token = str(payload.get("access_token") or "")
    assert old_token
    before = client.get(
        "/auth/admin/teacher/list",
        headers={"Authorization": f"Bearer {old_token}"},
    )
    assert before.status_code == 200

    store = build_auth_registry_store(data_dir=tmp_path / "data")
    rotated = store.rotate_admin_password(
        new_password="AdminPass2",
        actor_id=username,
        actor_role="admin",
    )
    assert rotated.get("ok") is True
    assert int(rotated.get("token_version") or 0) == 2

    revoked = client.get(
        "/auth/admin/teacher/list",
        headers={"Authorization": f"Bearer {old_token}"},
    )
    assert revoked.status_code == 401
    assert revoked.json().get("detail") == "token_revoked"

    new_payload = _login_admin(client, username=username, password="AdminPass2")
    new_token = str(new_payload.get("access_token") or "")
    assert int(_token_claims(new_token).get("tv")) == 2
    after = client.get(
        "/auth/admin/teacher/list",
        headers={"Authorization": f"Bearer {new_token}"},
    )
    assert after.status_code == 200


def test_admin_disable_revokes_old_token(tmp_path: Path):
    secret = "admin-tv-disable-secret"
    username = "principal_admin"
    password = "AdminPass1"
    app_mod = _load_app(tmp_path, secret=secret, admin_username=username, admin_password=password)
    client = TestClient(app_mod.app)

    payload = _login_admin(client, username=username, password=password)
    token = str(payload.get("access_token") or "")
    store = build_auth_registry_store(data_dir=tmp_path / "data")
    disabled = store.set_admin_disabled(
        is_disabled=True,
        actor_id=username,
        actor_role="admin",
    )
    assert disabled.get("ok") is True
    assert disabled.get("is_disabled") is True
    assert int(disabled.get("token_version") or 0) >= 2

    revoked = client.get(
        "/auth/admin/teacher/list",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert revoked.status_code == 401
    assert revoked.json().get("detail") == "token_revoked"


def test_admin_token_version_mismatch_is_revoked(tmp_path: Path):
    secret = "admin-tv-mismatch-secret"
    username = "principal_admin"
    password = "AdminPass1"
    app_mod = _load_app(tmp_path, secret=secret, admin_username=username, admin_password=password)
    client = TestClient(app_mod.app)
    _login_admin(client, username=username, password=password)

    stale = mint_access_token(subject_id=username, role="admin", token_version=99)
    rejected = client.get(
        "/auth/admin/teacher/list",
        headers={"Authorization": f"Bearer {stale}"},
    )
    assert rejected.status_code == 401
    assert rejected.json().get("detail") == "token_revoked"


def test_existing_admin_auth_table_gains_token_version_column(tmp_path: Path):
    data_dir = tmp_path / "data"
    db_path = data_dir / "auth" / "auth_registry.sqlite3"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
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
            ("legacy_admin", "legacy_admin", "not-a-real-hash", "pbkdf2_sha256", now, now),
        )
        conn.commit()

    store = AuthRegistryStore(db_path=db_path, data_dir=data_dir)
    with store._connect() as conn:
        cols = {str(row[1]) for row in conn.execute("PRAGMA table_info(admin_auth)").fetchall()}
        assert "token_version" in cols
        version = conn.execute(
            "SELECT token_version FROM admin_auth WHERE admin_username = ?",
            ("legacy_admin",),
        ).fetchone()
    assert version is not None
    assert int(version["token_version"] or 0) == 1
