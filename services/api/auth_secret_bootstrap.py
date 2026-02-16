from __future__ import annotations

import logging
import os
import secrets
from pathlib import Path

_log = logging.getLogger(__name__)

_DEFAULT_SECRET_FILE_RELATIVE = Path("config") / "auth_token_secret"


def _truthy(value: str) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _app_root() -> Path:
    return Path(__file__).resolve().parents[2]


def resolve_auth_token_secret_file() -> Path:
    raw = str(os.getenv("AUTH_TOKEN_SECRET_FILE", "") or "").strip()
    if raw:
        path = Path(raw)
        if path.is_absolute():
            return path
        return (_app_root() / path).resolve()
    return (_app_root() / _DEFAULT_SECRET_FILE_RELATIVE).resolve()


def _read_secret_file(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        secret = path.read_text(encoding="utf-8").strip()
    except Exception as exc:  # pragma: no cover - defensive; covered via runtime behavior
        raise RuntimeError(f"failed to read auth token secret file: {path}") from exc
    return secret


def _write_secret_file(path: Path, secret: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(secret)
            handle.write("\n")
    finally:
        try:
            os.chmod(path, 0o600)
        except Exception:
            _log.debug("failed to chmod auth token secret file", exc_info=True)


def ensure_auth_token_secret() -> str:
    secret = str(os.getenv("AUTH_TOKEN_SECRET", "") or "").strip()
    if secret:
        return secret

    auth_required = _truthy(str(os.getenv("AUTH_REQUIRED", "") or ""))
    secret_file = resolve_auth_token_secret_file()

    persisted = _read_secret_file(secret_file)
    if persisted:
        os.environ["AUTH_TOKEN_SECRET"] = persisted
        return persisted

    if not auth_required:
        return ""

    generated = secrets.token_urlsafe(48)
    try:
        _write_secret_file(secret_file, generated)
    except Exception as exc:  # pragma: no cover - defensive; covered via runtime behavior
        raise RuntimeError(
            f"AUTH_REQUIRED is enabled but failed to persist AUTH_TOKEN_SECRET at {secret_file}"
        ) from exc
    os.environ["AUTH_TOKEN_SECRET"] = generated
    _log.warning(
        "Generated AUTH_TOKEN_SECRET and persisted to %s; keep this file private and backed up.",
        secret_file,
    )
    return generated
