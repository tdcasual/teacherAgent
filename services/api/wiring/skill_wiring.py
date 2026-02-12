"""Teacher skill CRUD wiring — extracted from app_core."""
from __future__ import annotations

__all__ = [
    "create_teacher_skill",
    "update_teacher_skill",
    "delete_teacher_skill",
    "import_skill_from_github",
    "preview_github_skill",
    "check_skill_dependencies",
    "install_skill_dependencies",
]

from typing import Any, Dict, List, Optional

from ..teacher_skill_service import (
    TeacherSkillDeps,
    create_teacher_skill as _create_impl,
    update_teacher_skill as _update_impl,
    delete_teacher_skill as _delete_impl,
    import_skill_from_github as _import_impl,
    preview_github_skill as _preview_impl,
    check_skill_dependencies as _check_deps_impl,
    install_skill_dependencies as _install_deps_impl,
)

from . import get_app_core as _app_core


def _teacher_skill_deps() -> TeacherSkillDeps:
    _ac = _app_core()
    from ..skills.loader import clear_cache
    return TeacherSkillDeps(
        teacher_skills_dir=_ac.TEACHER_SKILLS_DIR,
        clear_skill_cache=clear_cache,
    )


def create_teacher_skill(
    *, title: str, description: str,
    keywords: List[str] = (), examples: List[str] = (),
    allowed_roles: List[str] = ("teacher",),
) -> Dict[str, Any]:
    return _create_impl(
        _teacher_skill_deps(), title=title,
        description=description, keywords=list(keywords),
        examples=list(examples),
        allowed_roles=list(allowed_roles),
    )


def update_teacher_skill(
    *, skill_id: str, title=None, description=None,
    keywords=None, examples=None, allowed_roles=None,
) -> Dict[str, Any]:
    return _update_impl(
        _teacher_skill_deps(), skill_id=skill_id,
        title=title, description=description,
        keywords=keywords, examples=examples,
        allowed_roles=allowed_roles,
    )


def delete_teacher_skill(*, skill_id: str) -> Dict[str, Any]:
    return _delete_impl(_teacher_skill_deps(), skill_id=skill_id)


def import_skill_from_github(*, github_url: str, overwrite: bool = False) -> Dict[str, Any]:
    return _import_impl(_teacher_skill_deps(), github_url=github_url, overwrite=overwrite)


def preview_github_skill(*, github_url: str) -> Dict[str, Any]:
    return _preview_impl(_teacher_skill_deps(), github_url=github_url)


def check_skill_dependencies(*, skill_id: str) -> Dict[str, Any]:
    return _check_deps_impl(_teacher_skill_deps(), skill_id=skill_id)


def install_skill_dependencies(*, skill_id: str, packages=None) -> Dict[str, Any]:
    return _install_deps_impl(_teacher_skill_deps(), skill_id=skill_id, packages=packages)
