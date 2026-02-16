from __future__ import annotations

import os
import stat
from pathlib import Path

from services.api.auth_secret_bootstrap import ensure_auth_token_secret


def test_generates_and_persists_secret_when_auth_required(tmp_path: Path, monkeypatch) -> None:
    secret_file = tmp_path / "config" / "auth_token_secret"
    monkeypatch.setenv("AUTH_REQUIRED", "1")
    monkeypatch.setenv("AUTH_TOKEN_SECRET_FILE", str(secret_file))
    monkeypatch.delenv("AUTH_TOKEN_SECRET", raising=False)

    secret = ensure_auth_token_secret()

    assert secret
    assert os.getenv("AUTH_TOKEN_SECRET") == secret
    assert secret_file.exists()
    assert secret_file.read_text(encoding="utf-8").strip() == secret
    file_mode = stat.S_IMODE(secret_file.stat().st_mode)
    assert file_mode & 0o077 == 0


def test_reuses_existing_secret_file(tmp_path: Path, monkeypatch) -> None:
    secret_file = tmp_path / "config" / "auth_token_secret"
    secret_file.parent.mkdir(parents=True, exist_ok=True)
    secret_file.write_text("persisted-secret\n", encoding="utf-8")

    monkeypatch.setenv("AUTH_REQUIRED", "1")
    monkeypatch.setenv("AUTH_TOKEN_SECRET_FILE", str(secret_file))
    monkeypatch.delenv("AUTH_TOKEN_SECRET", raising=False)

    secret = ensure_auth_token_secret()

    assert secret == "persisted-secret"
    assert os.getenv("AUTH_TOKEN_SECRET") == "persisted-secret"


def test_does_not_generate_secret_when_auth_disabled(tmp_path: Path, monkeypatch) -> None:
    secret_file = tmp_path / "config" / "auth_token_secret"
    monkeypatch.setenv("AUTH_REQUIRED", "0")
    monkeypatch.setenv("AUTH_TOKEN_SECRET_FILE", str(secret_file))
    monkeypatch.delenv("AUTH_TOKEN_SECRET", raising=False)

    secret = ensure_auth_token_secret()

    assert secret == ""
    assert not secret_file.exists()
    assert os.getenv("AUTH_TOKEN_SECRET") in (None, "")
