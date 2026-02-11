"""CRUD + GitHub import for lightweight teacher skills."""
from __future__ import annotations

import re
import shutil
import urllib.request
import urllib.error
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import yaml  # type: ignore


@dataclass(frozen=True)
class TeacherSkillDeps:
    teacher_skills_dir: Path
    clear_skill_cache: Callable[[], None]


def _slugify(title: str) -> str:
    """Generate a filesystem-safe, ASCII-only skill_id from a title."""
    import hashlib
    raw = title.strip().lower()
    # Keep only ASCII alphanumerics and hyphens
    slug = re.sub(r"[^a-z0-9-]+", "-", raw).strip("-")
    # If slug is too short (e.g. all-CJK title), use hash with a readable prefix
    if len(slug) < 4:
        digest = hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()[:10]
        slug = f"skill-{digest}" if not slug else f"{slug}-{digest}"
    return slug


def _build_skill_md(
    title: str,
    description: str,
    keywords: List[str],
    examples: List[str],
    allowed_roles: List[str],
) -> str:
    """Build a SKILL.md with YAML frontmatter + body."""
    fm: Dict[str, Any] = {"title": title}
    if keywords:
        fm["keywords"] = keywords
    if examples:
        fm["examples"] = examples
    if allowed_roles:
        fm["allowed_roles"] = allowed_roles
    fm_text = yaml.dump(fm, allow_unicode=True, default_flow_style=False, sort_keys=False).rstrip("\n")
    return f"---\n{fm_text}\n---\n\n{description}\n"


_SKILL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{1,80}$")


def _validate_skill_id(skill_id: str) -> None:
    """Reject skill_id values that are not safe filesystem names."""
    if not _SKILL_ID_RE.match(skill_id):
        raise ValueError(f"invalid skill_id: {skill_id!r}")


def _ensure_safe_path(base: Path, target: Path) -> None:
    """Ensure target resolves strictly inside base to prevent path traversal."""
    resolved_base = base.resolve()
    resolved_target = target.resolve()
    if resolved_target == resolved_base or resolved_base not in resolved_target.parents:
        raise ValueError("path traversal detected")


def create_teacher_skill(
    deps: TeacherSkillDeps,
    title: str,
    description: str,
    keywords: Optional[List[str]] = None,
    examples: Optional[List[str]] = None,
    allowed_roles: Optional[List[str]] = None,
) -> Dict[str, Any]:
    skill_id = _slugify(title)
    _validate_skill_id(skill_id)
    skill_dir = deps.teacher_skills_dir / skill_id
    # Prevent overwriting an existing teacher skill with a different title
    if skill_dir.exists():
        return {"ok": False, "error": f"技能 ID '{skill_id}' 已存在，请更换标题"}
    skill_dir.mkdir(parents=True, exist_ok=True)
    content = _build_skill_md(
        title=title,
        description=description,
        keywords=keywords or [],
        examples=examples or [],
        allowed_roles=allowed_roles or ["teacher"],
    )
    (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")
    deps.clear_skill_cache()
    return {"ok": True, "skill_id": skill_id}


def update_teacher_skill(
    deps: TeacherSkillDeps,
    skill_id: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    keywords: Optional[List[str]] = None,
    examples: Optional[List[str]] = None,
    allowed_roles: Optional[List[str]] = None,
) -> Dict[str, Any]:
    _validate_skill_id(skill_id)
    skill_dir = deps.teacher_skills_dir / skill_id
    _ensure_safe_path(deps.teacher_skills_dir, skill_dir)
    if not skill_dir.exists():
        return {"ok": False, "error": "skill not found"}
    md_path = skill_dir / "SKILL.md"
    # Read existing to preserve fields not being updated
    existing_title = skill_id
    existing_desc = ""
    existing_kw: List[str] = []
    existing_ex: List[str] = []
    existing_roles: List[str] = ["teacher"]
    if md_path.exists():
        from .skills.loader import _parse_yaml_frontmatter
        raw_content = md_path.read_text(encoding="utf-8")
        fm, body = _parse_yaml_frontmatter(raw_content)
        existing_title = str(fm.get("title") or skill_id)
        existing_desc = body or ""
        kw_raw = fm.get("keywords")
        if isinstance(kw_raw, list):
            existing_kw = [str(k) for k in kw_raw]
        ex_raw = fm.get("examples")
        if isinstance(ex_raw, list):
            existing_ex = [str(e) for e in ex_raw]
        roles_raw = fm.get("allowed_roles")
        if isinstance(roles_raw, list):
            existing_roles = [str(r) for r in roles_raw]
    content = _build_skill_md(
        title=title if title is not None else existing_title,
        description=description if description is not None else existing_desc,
        keywords=keywords if keywords is not None else existing_kw,
        examples=examples if examples is not None else existing_ex,
        allowed_roles=allowed_roles if allowed_roles is not None else existing_roles,
    )
    md_path.write_text(content, encoding="utf-8")
    deps.clear_skill_cache()
    return {"ok": True, "skill_id": skill_id}


def delete_teacher_skill(
    deps: TeacherSkillDeps,
    skill_id: str,
) -> Dict[str, Any]:
    _validate_skill_id(skill_id)
    skill_dir = deps.teacher_skills_dir / skill_id
    _ensure_safe_path(deps.teacher_skills_dir, skill_dir)
    if not skill_dir.exists():
        return {"ok": False, "error": "skill not found"}
    shutil.rmtree(skill_dir)
    deps.clear_skill_cache()
    return {"ok": True, "skill_id": skill_id}


def _github_url_to_raw(github_url: str) -> str:
    """Convert a GitHub URL to a raw.githubusercontent.com URL for SKILL.md."""
    url = github_url.strip()
    # Validate hostname to prevent SSRF
    parsed = urllib.parse.urlparse(url)
    allowed_hosts = {"github.com", "raw.githubusercontent.com"}
    if parsed.hostname not in allowed_hosts:
        raise ValueError(f"only github.com URLs are supported, got: {parsed.hostname}")
    # Already a raw URL
    if parsed.hostname == "raw.githubusercontent.com":
        if not url.endswith("/SKILL.md"):
            url = url.rstrip("/") + "/SKILL.md"
        return url
    # github.com/<user>/<repo>/tree/<branch>/<path> or /blob/<branch>/<path>
    m = re.match(
        r"https?://github\.com/([^/]+)/([^/]+)/(?:tree|blob)/([^/]+)/(.+)",
        url,
    )
    if m:
        user, repo, branch, path = m.groups()
        path = path.rstrip("/")
        if not path.endswith("SKILL.md"):
            path = path + "/SKILL.md"
        return f"https://raw.githubusercontent.com/{user}/{repo}/{branch}/{path}"
    # github.com/<user>/<repo> (root)
    m2 = re.match(r"https?://github\.com/([^/]+)/([^/]+)/?$", url)
    if m2:
        user, repo = m2.groups()
        return f"https://raw.githubusercontent.com/{user}/{repo}/main/SKILL.md"
    raise ValueError(f"unsupported GitHub URL format: {url}")


def _download_skill_md(raw_url: str) -> str:
    """Download SKILL.md content from a raw URL."""
    MAX_SIZE = 256 * 1024  # 256 KB limit
    allowed_hosts = {"github.com", "raw.githubusercontent.com"}
    req = urllib.request.Request(raw_url, headers={"User-Agent": "PhysicsTeacherBot/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            # Validate final URL after redirects to prevent SSRF
            final_host = urllib.parse.urlparse(resp.url).hostname
            if final_host not in allowed_hosts:
                raise ValueError(f"redirect to disallowed host: {final_host}")
            data = resp.read(MAX_SIZE + 1)
            if len(data) > MAX_SIZE:
                raise ValueError("SKILL.md exceeds 256 KB size limit")
            return data.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raise ValueError(f"download failed: HTTP {exc.code}") from exc
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"download failed: {exc}") from exc


def _infer_skill_id_from_url(github_url: str) -> str:
    """Infer a skill_id from the last meaningful path segment of a GitHub URL."""
    url = github_url.strip().rstrip("/")
    if url.endswith("/SKILL.md"):
        url = url[: -len("/SKILL.md")]
    parts = url.rstrip("/").split("/")
    last = parts[-1] if parts else "imported-skill"
    return _slugify(last)


def import_skill_from_github(
    deps: TeacherSkillDeps,
    github_url: str,
) -> Dict[str, Any]:
    raw_url = _github_url_to_raw(github_url)
    content = _download_skill_md(raw_url)
    from .skills.loader import _parse_yaml_frontmatter
    fm, body = _parse_yaml_frontmatter(content)
    title = str(fm.get("name") or fm.get("title") or "").strip()
    skill_id = _slugify(title) if title else _infer_skill_id_from_url(github_url)
    _validate_skill_id(skill_id)
    if not title:
        for line in body.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                title = stripped.lstrip("#").strip()
                break
    title = title or skill_id
    skill_dir = deps.teacher_skills_dir / skill_id
    _ensure_safe_path(deps.teacher_skills_dir, skill_dir)
    # Reject overwrite unless the caller explicitly allows it
    if skill_dir.exists():
        return {"ok": False, "error": f"技能 '{skill_id}' 已存在，如需覆盖请先删除", "skill_id": skill_id}
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")
    deps.clear_skill_cache()
    desc = str(fm.get("description") or fm.get("desc") or "").strip()
    preview = (body[:200] + "...") if len(body) > 200 else body
    return {"ok": True, "skill_id": skill_id, "title": title, "preview": preview, "desc": desc}


def preview_github_skill(
    deps: TeacherSkillDeps,
    github_url: str,
) -> Dict[str, Any]:
    raw_url = _github_url_to_raw(github_url)
    content = _download_skill_md(raw_url)
    from .skills.loader import _parse_yaml_frontmatter
    fm, body = _parse_yaml_frontmatter(content)
    title = str(fm.get("name") or fm.get("title") or "").strip()
    if not title:
        for line in body.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                title = stripped.lstrip("#").strip()
                break
    title = title or _infer_skill_id_from_url(github_url)
    desc = str(fm.get("description") or fm.get("desc") or "").strip()
    keywords = []
    kw_raw = fm.get("keywords")
    if isinstance(kw_raw, list):
        keywords = [str(k).strip() for k in kw_raw if str(k).strip()]
    preview = (body[:300] + "...") if len(body) > 300 else body
    return {"ok": True, "title": title, "desc": desc, "keywords": keywords, "preview": preview}
