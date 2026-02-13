from __future__ import annotations

import re
from pathlib import Path

ROUTES_DIR = Path("services/api/routes")
ROUTE_DECORATOR_RE = re.compile(r"@router\.(?:get|post|put|delete|patch)\(")

# Explicitly public endpoints keep an allowlist to make auth decisions visible in reviews.
PUBLIC_ROUTE_MODULE_ALLOWLIST = {
    "misc_general_routes.py",
    "misc_health_routes.py",
}

AUTH_GUARD_MARKERS = (
    "require_principal(",
    "resolve_student_scope(",
    "resolve_teacher_scope(",
    "scoped_teacher_id(",
    "scoped_payload_teacher_id(",
    "_scoped_student_id(",
)


def test_route_modules_declare_auth_guard_or_public_allowlist() -> None:
    missing: list[str] = []
    for path in sorted(ROUTES_DIR.glob("*_routes.py")):
        if path.name in PUBLIC_ROUTE_MODULE_ALLOWLIST:
            continue
        text = path.read_text(encoding="utf-8")
        if not ROUTE_DECORATOR_RE.search(text):
            continue
        if any(marker in text for marker in AUTH_GUARD_MARKERS):
            continue
        missing.append(path.name)

    assert not missing, (
        "route modules missing auth guard markers; add explicit guard "
        f"or PUBLIC_ROUTE_MODULE_ALLOWLIST entry: {missing}"
    )
