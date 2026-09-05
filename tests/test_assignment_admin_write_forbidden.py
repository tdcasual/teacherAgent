from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from services.api.auth_service import mint_test_token
from tests.helpers.app_factory import create_test_app

SECRET = "admin-write-forbidden-secret"
_AUTH_KEYS = ("AUTH_REQUIRED", "AUTH_TOKEN_SECRET", "APP_ENV", "ADMIN_USERNAME")


@contextmanager
def _auth_env():
    saved = {key: os.environ.get(key) for key in _AUTH_KEYS}
    try:
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _auth_app(tmp: Path):
    return create_test_app(
        tmp,
        env_overrides={
            "AUTH_REQUIRED": "1",
            "AUTH_TOKEN_SECRET": SECRET,
            "APP_ENV": "development",
            "ADMIN_USERNAME": "admin",
        },
        env_unset=["ADMIN_PASSWORD"],
    )


def _admin_headers() -> dict[str, str]:
    token = mint_test_token(
        {"sub": "admin", "role": "admin", "tv": 1, "tenant_id": "school"},
        secret=SECRET,
    )
    return {"Authorization": f"Bearer {token}"}


def test_admin_bearer_is_403_on_assignment_write_paths() -> None:
    with _auth_env(), TemporaryDirectory() as td:
        app_mod = _auth_app(Path(td))
        headers = _admin_headers()
        with TestClient(app_mod.app) as client:
            start = client.post(
                "/assignment/upload/start",
                headers=headers,
                data={"assignment_id": "HW1"},
                files={"files": ("q.png", b"x", "image/png")},
            )
            assert start.status_code == 403
            assert start.json().get("detail") == "forbidden"

            confirm = client.post(
                "/assignment/upload/confirm",
                headers=headers,
                json={"job_id": "job-1"},
            )
            assert confirm.status_code == 403
            assert confirm.json().get("detail") == "forbidden"

            generate = client.post(
                "/assignment/generate",
                headers=headers,
                data={"assignment_id": "HW1"},
            )
            assert generate.status_code == 403
            assert generate.json().get("detail") == "forbidden"

            archive = client.post("/assignment/HW1/archive", headers=headers)
            assert archive.status_code == 403
            assert archive.json().get("detail") == "forbidden"

            unarchive = client.post("/assignment/HW1/unarchive", headers=headers)
            assert unarchive.status_code == 403
            assert unarchive.json().get("detail") == "forbidden"

            grade = client.post(
                "/teacher/assignment/HW1/student/S001/grade",
                headers=headers,
                json={"comment": "nope"},
            )
            assert grade.status_code == 403
            assert grade.json().get("detail") == "forbidden"

            recompute = client.post("/assignment/HW1/recompute-roster", headers=headers)
            assert recompute.status_code == 403
            assert recompute.json().get("detail") == "forbidden"

            draft_save = client.post(
                "/assignment/upload/draft/save",
                headers=headers,
                json={"job_id": "job-1"},
            )
            assert draft_save.status_code == 403
            assert draft_save.json().get("detail") == "forbidden"
