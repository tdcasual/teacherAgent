"""Tests for the lightweight teacher skill system."""
from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_teacher_skills_dir(tmp_path: Path) -> Path:
    d = tmp_path / "teacher_skills"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _make_deps(tmp_path: Path):
    from services.api.teacher_skill_service import TeacherSkillDeps
    from services.api.skills.loader import clear_cache
    return TeacherSkillDeps(
        teacher_skills_dir=_make_teacher_skills_dir(tmp_path),
        clear_skill_cache=clear_cache,
    )


# ---------------------------------------------------------------------------
# 1. Create skill → verify SKILL.md written correctly
# ---------------------------------------------------------------------------

def test_create_teacher_skill(tmp_path):
    from services.api.teacher_skill_service import create_teacher_skill
    deps = _make_deps(tmp_path)
    result = create_teacher_skill(
        deps, title="课堂小测", description="生成课堂小测验",
        keywords=["小测", "课堂"], examples=["生成小测"],
        allowed_roles=["teacher"],
    )
    assert result["ok"] is True
    skill_id = result["skill_id"]
    md_path = deps.teacher_skills_dir / skill_id / "SKILL.md"
    assert md_path.exists()
    content = md_path.read_text(encoding="utf-8")
    assert "课堂小测" in content
    assert "生成课堂小测验" in content


# ---------------------------------------------------------------------------
# 2. Update skill → verify content updated
# ---------------------------------------------------------------------------

def test_update_teacher_skill(tmp_path):
    from services.api.teacher_skill_service import create_teacher_skill, update_teacher_skill
    deps = _make_deps(tmp_path)
    r = create_teacher_skill(deps, title="旧标题", description="旧描述")
    skill_id = r["skill_id"]
    result = update_teacher_skill(deps, skill_id=skill_id, title="新标题", description="新描述")
    assert result["ok"] is True
    content = (deps.teacher_skills_dir / skill_id / "SKILL.md").read_text(encoding="utf-8")
    assert "新标题" in content
    assert "新描述" in content


# ---------------------------------------------------------------------------
# 3. Delete skill → verify directory deleted
# ---------------------------------------------------------------------------

def test_delete_teacher_skill(tmp_path):
    from services.api.teacher_skill_service import create_teacher_skill, delete_teacher_skill
    deps = _make_deps(tmp_path)
    r = create_teacher_skill(deps, title="待删除技能", description="desc")
    skill_id = r["skill_id"]
    assert (deps.teacher_skills_dir / skill_id).exists()
    result = delete_teacher_skill(deps, skill_id=skill_id)
    assert result["ok"] is True
    assert not (deps.teacher_skills_dir / skill_id).exists()


# ---------------------------------------------------------------------------
# 4. Delete non-existent skill → verify rejection
# ---------------------------------------------------------------------------

def test_delete_nonexistent_skill(tmp_path):
    from services.api.teacher_skill_service import delete_teacher_skill
    deps = _make_deps(tmp_path)
    result = delete_teacher_skill(deps, skill_id="no-such-skill-here")
    assert result["ok"] is False


# ---------------------------------------------------------------------------
# 5. GitHub URL parsing → verify raw URL conversion
# ---------------------------------------------------------------------------

def test_github_url_to_raw():
    from services.api.teacher_skill_service import _github_url_to_raw
    # tree format
    url = "https://github.com/user/repo/tree/main/skills/my-skill"
    raw = _github_url_to_raw(url)
    assert raw == "https://raw.githubusercontent.com/user/repo/main/skills/my-skill/SKILL.md"
    # blob format
    url2 = "https://github.com/user/repo/blob/main/skills/my-skill/SKILL.md"
    raw2 = _github_url_to_raw(url2)
    assert raw2 == "https://raw.githubusercontent.com/user/repo/main/skills/my-skill/SKILL.md"
    # repo root
    url3 = "https://github.com/user/repo"
    raw3 = _github_url_to_raw(url3)
    assert raw3 == "https://raw.githubusercontent.com/user/repo/main/SKILL.md"


def test_github_url_rejects_non_github():
    from services.api.teacher_skill_service import _github_url_to_raw
    with pytest.raises(ValueError, match="only github.com"):
        _github_url_to_raw("https://evil.com/raw.githubusercontent.com/user/repo")


def test_build_skill_md_yaml_special_chars(tmp_path):
    """Verify YAML special characters in title/keywords don't break the frontmatter."""
    from services.api.teacher_skill_service import create_teacher_skill
    import yaml as _yaml
    deps = _make_deps(tmp_path)
    result = create_teacher_skill(
        deps, title="test: injection #1", description="desc",
        keywords=["key: val", "[bracket]", "{brace}"],
    )
    assert result["ok"] is True
    md_path = deps.teacher_skills_dir / result["skill_id"] / "SKILL.md"
    content = md_path.read_text(encoding="utf-8")
    # Verify the frontmatter is valid YAML by re-parsing
    assert content.startswith("---\n")
    fm_end = content.index("---", 4)
    fm_text = content[4:fm_end]
    parsed = _yaml.safe_load(fm_text)
    assert parsed["title"] == "test: injection #1"
    assert "key: val" in parsed["keywords"]


# ---------------------------------------------------------------------------
# 6. YAML frontmatter parsing → verify field mapping
# ---------------------------------------------------------------------------

def test_parse_yaml_frontmatter():
    from services.api.skills.loader import _parse_yaml_frontmatter
    content = textwrap.dedent("""\
    ---
    title: My Skill
    description: A test skill
    keywords:
      - test
      - demo
    ---
    This is the body of the skill.
    """)
    fm, body = _parse_yaml_frontmatter(content)
    assert fm["title"] == "My Skill"
    assert fm["description"] == "A test skill"
    assert fm["keywords"] == ["test", "demo"]
    assert "This is the body" in body


# ---------------------------------------------------------------------------
# 7. No frontmatter SKILL.md → verify fallback behavior
# ---------------------------------------------------------------------------

def test_parse_yaml_frontmatter_no_frontmatter():
    from services.api.skills.loader import _parse_yaml_frontmatter
    content = "# Simple Skill\n\nJust a description."
    fm, body = _parse_yaml_frontmatter(content)
    assert fm == {}
    assert body == content


# ---------------------------------------------------------------------------
# 8. skill_id conflict (system skill same name) → system wins
# ---------------------------------------------------------------------------

def test_system_skill_overrides_teacher(tmp_path):
    from services.api.skills.loader import load_skills, clear_cache
    clear_cache()
    # Create a system skills dir with a skill
    system_dir = tmp_path / "system_skills" / "my-skill"
    system_dir.mkdir(parents=True)
    (system_dir / "skill.yaml").write_text(
        "title: System Skill\ndesc: system version\nrouting:\n  keywords:\n    - test\n",
        encoding="utf-8",
    )
    # Create a teacher skills dir with same skill_id
    teacher_dir = tmp_path / "teacher_skills" / "my-skill"
    teacher_dir.mkdir(parents=True)
    (teacher_dir / "SKILL.md").write_text(
        "---\ntitle: Teacher Skill\n---\nteacher version\n",
        encoding="utf-8",
    )
    loaded = load_skills(tmp_path / "system_skills", teacher_skills_dir=tmp_path / "teacher_skills")
    # System skill should win (higher priority source dir)
    assert "my-skill" in loaded.skills
    assert loaded.skills["my-skill"].title == "System Skill"
    clear_cache()


# ---------------------------------------------------------------------------
# 9. load_skills three source dirs → verify priority
# ---------------------------------------------------------------------------

def test_load_skills_teacher_dir(tmp_path):
    from services.api.skills.loader import load_skills, clear_cache
    clear_cache()
    teacher_dir = tmp_path / "teacher_skills" / "teacher-only-skill"
    teacher_dir.mkdir(parents=True)
    (teacher_dir / "SKILL.md").write_text(
        "---\ntitle: Teacher Only\nkeywords:\n  - unique\n---\nTeacher body\n",
        encoding="utf-8",
    )
    system_dir = tmp_path / "system_skills"
    system_dir.mkdir(parents=True, exist_ok=True)
    loaded = load_skills(system_dir, teacher_skills_dir=tmp_path / "teacher_skills")
    assert "teacher-only-skill" in loaded.skills
    spec = loaded.skills["teacher-only-skill"]
    assert spec.source_type == "teacher"
    assert spec.title == "Teacher Only"
    assert spec.instructions == "Teacher body"
    clear_cache()


# ---------------------------------------------------------------------------
# 10. Lightweight skill enters auto_router → config-based scoring works
# ---------------------------------------------------------------------------

def test_lightweight_skill_routing(tmp_path):
    from services.api.skills.loader import load_skills, clear_cache
    clear_cache()
    teacher_dir = tmp_path / "teacher_skills" / "quiz-gen"
    teacher_dir.mkdir(parents=True)
    (teacher_dir / "SKILL.md").write_text(
        "---\ntitle: 小测生成\nkeywords:\n  - 小测\n  - 生成\n---\n生成课堂小测验的指令\n",
        encoding="utf-8",
    )
    system_dir = tmp_path / "system_skills"
    system_dir.mkdir(parents=True, exist_ok=True)
    loaded = load_skills(system_dir, teacher_skills_dir=tmp_path / "teacher_skills")
    spec = loaded.skills["quiz-gen"]
    assert "小测" in spec.routing.keywords
    assert "生成" in spec.routing.keywords
    clear_cache()


# ---------------------------------------------------------------------------
# 11. Windows \r\n line endings in frontmatter → verify correct parsing
# ---------------------------------------------------------------------------

def test_parse_yaml_frontmatter_crlf():
    from services.api.skills.loader import _parse_yaml_frontmatter
    content = "---\r\ntitle: CRLF Skill\r\ndescription: Windows file\r\n---\r\nBody with CRLF.\r\n"
    fm, body = _parse_yaml_frontmatter(content)
    assert fm["title"] == "CRLF Skill"
    assert fm["description"] == "Windows file"
    assert "Body with CRLF." in body


# ---------------------------------------------------------------------------
# 12. CJK title fallback keywords → full title used as keyword
# ---------------------------------------------------------------------------

def test_cjk_title_fallback_keywords(tmp_path):
    from services.api.skills.loader import load_skills, clear_cache
    clear_cache()
    teacher_dir = tmp_path / "teacher_skills" / "cjk-skill"
    teacher_dir.mkdir(parents=True)
    (teacher_dir / "SKILL.md").write_text(
        "---\ntitle: 课堂小测生成器\n---\n生成课堂小测验\n",
        encoding="utf-8",
    )
    system_dir = tmp_path / "system_skills"
    system_dir.mkdir(parents=True, exist_ok=True)
    loaded = load_skills(system_dir, teacher_skills_dir=tmp_path / "teacher_skills")
    spec = loaded.skills["cjk-skill"]
    # CJK title without spaces should produce the full title as a keyword
    assert "课堂小测生成器" in spec.routing.keywords
    clear_cache()


# ---------------------------------------------------------------------------
# 13. Duplicate skill ID on create → verify rejection
# ---------------------------------------------------------------------------

def test_create_duplicate_skill_id(tmp_path):
    from services.api.teacher_skill_service import create_teacher_skill
    deps = _make_deps(tmp_path)
    r1 = create_teacher_skill(deps, title="Same Title", description="first")
    assert r1["ok"] is True
    r2 = create_teacher_skill(deps, title="Same Title", description="second")
    assert r2["ok"] is False
    assert "已存在" in r2.get("error", "")


# ---------------------------------------------------------------------------
# 14. Update skill can clear keywords/examples to empty
# ---------------------------------------------------------------------------

def test_update_skill_clear_fields(tmp_path):
    from services.api.teacher_skill_service import create_teacher_skill, update_teacher_skill
    deps = _make_deps(tmp_path)
    r = create_teacher_skill(
        deps, title="With Keywords", description="desc",
        keywords=["kw1", "kw2"], examples=["ex1"],
    )
    skill_id = r["skill_id"]
    # Clear keywords and examples by passing empty lists
    result = update_teacher_skill(deps, skill_id=skill_id, keywords=[], examples=[])
    assert result["ok"] is True
    content = (deps.teacher_skills_dir / skill_id / "SKILL.md").read_text(encoding="utf-8")
    # Keywords and examples should not appear in the frontmatter
    assert "kw1" not in content
    assert "ex1" not in content


# ---------------------------------------------------------------------------
# 15. Adversarial skill_id → path traversal / directory deletion prevention
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad_id", [
    ".",           # resolves to base dir itself
    "..",          # parent traversal
    "../sibling",  # relative traversal
    "../../etc",   # deep traversal
    "",            # empty string
    "/etc/passwd", # absolute path
    "a",           # too short (< 2 chars)
    "-leading",    # starts with dash
    "a" * 82,      # exceeds 80-char limit
])
def test_delete_rejects_adversarial_skill_id(tmp_path, bad_id):
    from services.api.teacher_skill_service import delete_teacher_skill
    deps = _make_deps(tmp_path)
    with pytest.raises(ValueError):
        delete_teacher_skill(deps, skill_id=bad_id)


@pytest.mark.parametrize("bad_id", [".", "..", "../x", "", "-bad"])
def test_update_rejects_adversarial_skill_id(tmp_path, bad_id):
    from services.api.teacher_skill_service import update_teacher_skill
    deps = _make_deps(tmp_path)
    with pytest.raises(ValueError):
        update_teacher_skill(deps, skill_id=bad_id, title="hacked")


def test_ensure_safe_path_rejects_dot(tmp_path):
    """skill_id='.' must NOT pass _ensure_safe_path (would delete entire dir)."""
    from services.api.teacher_skill_service import _ensure_safe_path
    base = tmp_path / "skills"
    base.mkdir()
    with pytest.raises(ValueError, match="path traversal"):
        _ensure_safe_path(base, base / ".")


def test_update_nonexistent_skill(tmp_path):
    from services.api.teacher_skill_service import update_teacher_skill
    deps = _make_deps(tmp_path)
    result = update_teacher_skill(deps, skill_id="no-such-skill", title="x")
    assert result["ok"] is False
    assert "not found" in result.get("error", "")
