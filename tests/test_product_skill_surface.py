from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from services.api.content_catalog_service import list_skills
from services.api.skill_auto_router import resolve_effective_skill
from services.api.skills.loader import load_skills
from services.api.skills.product import (
    PRODUCT_SKILL_IDS,
    extra_skill_ids_for_teacher,
    is_product_skill,
    visible_skill_ids,
)
from services.api.skills.router import resolve_skill

APP_ROOT = Path(__file__).resolve().parents[1]


def test_product_allowlist_is_assignment_core() -> None:
    assert PRODUCT_SKILL_IDS == {
        "teacher-assignment-ops",
        "homework-generator",
        "student-coach",
    }
    assert not is_product_skill("physics-core-examples")
    assert not is_product_skill("physics-lesson-capture")
    assert not is_product_skill("physics-student-focus")


def test_list_skills_returns_only_product_ids(tmp_path: Path) -> None:
    fake_skills = {
        "teacher-assignment-ops": SimpleNamespace(
            as_public_dict=lambda: {"id": "teacher-assignment-ops"}
        ),
        "physics-core-examples": SimpleNamespace(
            as_public_dict=lambda: {"id": "physics-core-examples"}
        ),
        "homework-generator": SimpleNamespace(
            as_public_dict=lambda: {"id": "homework-generator"}
        ),
    }
    deps = SimpleNamespace(
        data_dir=tmp_path,
        app_root=tmp_path,
        load_profile_file=lambda _path: {},
        load_skills=lambda _skills_dir: SimpleNamespace(skills=fake_skills, errors=[]),
    )
    payload = list_skills(deps=deps)
    ids = [item["id"] for item in payload["skills"]]
    assert ids == ["homework-generator", "teacher-assignment-ops"]
    assert "physics-core-examples" not in ids


def test_resolve_skill_does_not_select_physics_for_teacher() -> None:
    loaded = load_skills(APP_ROOT / "skills")
    selection = resolve_skill(
        loaded,
        requested_skill_id="physics-core-examples",
        role_hint="teacher",
    )
    assert selection.skill is not None
    assert selection.skill.skill_id == "teacher-assignment-ops"


def test_auto_router_does_not_select_physics_skills() -> None:
    explicit = resolve_effective_skill(
        app_root=APP_ROOT,
        role_hint="teacher",
        requested_skill_id="physics-core-examples",
        last_user_text="登记核心例题 CE001",
    )
    assert explicit.get("effective_skill_id") == "teacher-assignment-ops"
    assert explicit.get("effective_skill_id") not in {
        "physics-core-examples",
        "physics-lesson-capture",
        "physics-student-focus",
    }

    auto_ce = resolve_effective_skill(
        app_root=APP_ROOT,
        role_hint="teacher",
        requested_skill_id="",
        last_user_text="登记核心例题 CE042，并补两道变式题。",
    )
    assert auto_ce.get("effective_skill_id") != "physics-core-examples"

    auto_focus = resolve_effective_skill(
        app_root=APP_ROOT,
        role_hint="teacher",
        requested_skill_id="",
        last_user_text="帮我看某个学生的画像和最近作业表现。",
    )
    assert auto_focus.get("effective_skill_id") != "physics-student-focus"


def test_physics_roster_unlocks_pack_affiliates() -> None:
    pack = SimpleNamespace(
        skill_affiliates=("physics-lesson-capture", "physics-core-examples", "physics-student-focus")
    )
    extra = extra_skill_ids_for_teacher(
        teacher_id="t_zhang",
        list_roster=lambda teacher_id: {
            "items": [
                {"teacher_id": teacher_id, "subject_id": "physics", "class_name": "高二2403班"},
                {"teacher_id": teacher_id, "subject_id": "physics", "class_name": "高二2404班"},
            ]
        },
        load_pack=lambda _subject_id: pack,
    )
    assert extra == {
        "physics-lesson-capture",
        "physics-core-examples",
        "physics-student-focus",
    }
    math_only = extra_skill_ids_for_teacher(
        teacher_id="t_li",
        list_roster=lambda teacher_id: {
            "items": [{"teacher_id": teacher_id, "subject_id": "math", "class_name": "高一1班"}]
        },
        load_pack=lambda subject_id: SimpleNamespace(
            skill_affiliates=() if subject_id != "physics" else pack.skill_affiliates
        ),
    )
    assert math_only == frozenset()
    assert "physics-core-examples" in visible_skill_ids(extra_skill_ids=extra)


def test_list_skills_includes_pack_affiliates_when_extra_ids_given(tmp_path: Path) -> None:
    fake_skills = {
        "teacher-assignment-ops": SimpleNamespace(
            as_public_dict=lambda: {"id": "teacher-assignment-ops"}
        ),
        "physics-core-examples": SimpleNamespace(
            as_public_dict=lambda: {"id": "physics-core-examples"}
        ),
    }
    deps = SimpleNamespace(
        data_dir=tmp_path,
        app_root=tmp_path,
        load_profile_file=lambda _path: {},
        load_skills=lambda _skills_dir: SimpleNamespace(skills=fake_skills, errors=[]),
    )
    payload = list_skills(deps=deps, extra_skill_ids=("physics-core-examples",))
    ids = [item["id"] for item in payload["skills"]]
    assert "teacher-assignment-ops" in ids
    assert "physics-core-examples" in ids


def test_physics_teacher_can_select_and_auto_route_affiliates() -> None:
    extra = (
        "physics-lesson-capture",
        "physics-core-examples",
        "physics-student-focus",
    )
    loaded = load_skills(APP_ROOT / "skills")
    selection = resolve_skill(
        loaded,
        requested_skill_id="physics-core-examples",
        role_hint="teacher",
        extra_skill_ids=extra,
    )
    assert selection.skill is not None
    assert selection.skill.skill_id == "physics-core-examples"

    explicit = resolve_effective_skill(
        app_root=APP_ROOT,
        role_hint="teacher",
        requested_skill_id="physics-core-examples",
        last_user_text="登记核心例题 CE001",
        extra_skill_ids=extra,
    )
    assert explicit.get("effective_skill_id") == "physics-core-examples"
    assert explicit.get("reason") == "explicit"

    auto_ce = resolve_effective_skill(
        app_root=APP_ROOT,
        role_hint="teacher",
        requested_skill_id="",
        last_user_text="登记核心例题 CE042，并补两道变式题。",
        extra_skill_ids=extra,
    )
    assert auto_ce.get("effective_skill_id") == "physics-core-examples"

    auto_focus = resolve_effective_skill(
        app_root=APP_ROOT,
        role_hint="teacher",
        requested_skill_id="",
        last_user_text="帮我看某个学生的画像和最近作业表现。",
        extra_skill_ids=extra,
    )
    assert auto_focus.get("effective_skill_id") == "physics-student-focus"
