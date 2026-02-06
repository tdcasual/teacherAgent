#!/usr/bin/env python3
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass(frozen=True)
class ValidationError:
    skill_id: str
    message: str


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    # Import from project runtime (repo root on PYTHONPATH when run via `python3` in this repo).
    from services.api.app import APP_ROOT, allowed_tools  # type: ignore
    from services.common.tool_registry import DEFAULT_TOOL_REGISTRY  # type: ignore
    from services.api.skills.loader import load_skills  # type: ignore
    from services.api.skills.runtime import compile_skill_runtime  # type: ignore

    skills_dir = APP_ROOT / "skills"
    loaded = load_skills(skills_dir)

    errors: List[ValidationError] = []
    for e in loaded.errors:
        errors.append(ValidationError(skill_id=e.skill_id or "(unknown)", message=f"{e.path}: {e.message}"))

    known_tools = set(DEFAULT_TOOL_REGISTRY.names())
    role_allowed = set()
    role_allowed |= set(allowed_tools("teacher"))
    role_allowed |= set(allowed_tools("student"))

    for skill_id, spec in loaded.skills.items():
        # Validate prompt modules existence/path safety by compiling runtime.
        try:
            compile_skill_runtime(spec)
        except Exception as exc:
            errors.append(ValidationError(skill_id=skill_id, message=f"prompt_modules invalid: {exc}"))

        # Validate tool ids against known tool set.
        allow = spec.agent.tools.allow or []
        deny = spec.agent.tools.deny or []
        for tool_name in list(allow) + list(deny):
            if tool_name not in known_tools:
                errors.append(ValidationError(skill_id=skill_id, message=f"unknown tool referenced: {tool_name}"))
            elif tool_name not in role_allowed:
                errors.append(ValidationError(skill_id=skill_id, message=f"tool not allowed for any role: {tool_name}"))

        # Basic role sanity.
        if not spec.allowed_roles:
            errors.append(ValidationError(skill_id=skill_id, message="allowed_roles is empty (skill will be usable by all roles)"))

    if errors:
        print("[FAIL] Skill validation failed:")
        for err in errors:
            print(f"- {err.skill_id}: {err.message}")
        return 1

    print(f"[OK] Validated {len(loaded.skills)} skills.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
