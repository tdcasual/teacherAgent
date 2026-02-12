"""CRUD + GitHub import for lightweight teacher skills."""
from __future__ import annotations

import json
import logging
import re
import shutil
import urllib.request
import urllib.error
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import yaml  # type: ignore

_log = logging.getLogger(__name__)


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


def _parse_github_url(github_url: str):
    """Parse a GitHub URL into (user, repo, branch, path) or raise ValueError."""
    url = github_url.strip()
    m = re.match(
        r"https?://github\.com/([^/]+)/([^/]+)/(?:tree|blob)/([^/]+)/(.+)",
        url,
    )
    if m:
        user, repo, branch, path = m.groups()
        return user, repo, branch, path.rstrip("/")
    m2 = re.match(r"https?://github\.com/([^/]+)/([^/]+)/?$", url)
    if m2:
        user, repo = m2.groups()
        return user, repo, "main", ""
    raise ValueError(f"unsupported GitHub URL format: {url}")


def _download_github_directory(user: str, repo: str, branch: str, path: str, dest_dir: Path) -> int:
    """Download all files from a GitHub directory using the API. Returns file count."""
    api_url = f"https://api.github.com/repos/{user}/{repo}/contents/{path}?ref={branch}"
    req = urllib.request.Request(api_url, headers={
        "User-Agent": "PhysicsTeacherBot/1.0",
        "Accept": "application/vnd.github.v3+json",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            entries = json.loads(resp.read(2 * 1024 * 1024).decode("utf-8"))
    except Exception as exc:
        _log.warning("GitHub API listing failed for %s/%s/%s: %s", user, repo, path, exc)
        return 0

    if not isinstance(entries, list):
        return 0

    count = 0
    for entry in entries:
        name = entry.get("name", "")
        entry_type = entry.get("type", "")
        if not name or name.startswith("."):
            continue
        # Skip SKILL.md — already handled separately
        if name == "SKILL.md":
            continue
        target = dest_dir / name
        if entry_type == "file":
            download_url = entry.get("download_url")
            if not download_url:
                continue
            # Validate host
            parsed = urllib.parse.urlparse(download_url)
            if parsed.hostname not in {"raw.githubusercontent.com", "github.com"}:
                continue
            try:
                file_req = urllib.request.Request(download_url, headers={"User-Agent": "PhysicsTeacherBot/1.0"})
                with urllib.request.urlopen(file_req, timeout=15) as file_resp:
                    data = file_resp.read(1024 * 1024)  # 1 MB per file limit
                target.write_bytes(data)
                count += 1
            except Exception as exc:
                _log.warning("failed to download companion file %s: %s", name, exc)
        elif entry_type == "dir":
            sub_path = f"{path}/{name}" if path else name
            target.mkdir(parents=True, exist_ok=True)
            count += _download_github_directory(user, repo, branch, sub_path, target)
    return count


def _infer_skill_id_from_url(github_url: str) -> str:
    """Infer a skill_id from the last meaningful path segment of a GitHub URL."""
    url = github_url.strip().rstrip("/")
    if url.endswith("/SKILL.md"):
        url = url[: -len("/SKILL.md")]
    parts = url.rstrip("/").split("/")
    last = parts[-1] if parts else "imported-skill"
    return _slugify(last)


def _rebuild_skill_md_content(fm: Dict[str, Any], body: str) -> str:
    """Rebuild SKILL.md content from frontmatter dict and body text."""
    fm_text = yaml.dump(fm, allow_unicode=True, default_flow_style=False, sort_keys=False).rstrip("\n")
    return f"---\n{fm_text}\n---\n\n{body}\n"


def import_skill_from_github(
    deps: TeacherSkillDeps,
    github_url: str,
    overwrite: bool = False,
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

    # Ensure allowed_roles defaults to ["teacher"] so the skill is visible
    roles_raw = fm.get("allowed_roles")
    if not isinstance(roles_raw, list) or not roles_raw:
        # Inject allowed_roles into frontmatter before saving
        fm["allowed_roles"] = ["teacher"]
        content = _rebuild_skill_md_content(fm, body)

    skill_dir = deps.teacher_skills_dir / skill_id
    _ensure_safe_path(deps.teacher_skills_dir, skill_dir)
    if skill_dir.exists():
        if not overwrite:
            return {"ok": False, "error": f"技能 '{skill_id}' 已存在，如需覆盖请先删除", "skill_id": skill_id, "exists": True}
        shutil.rmtree(skill_dir)
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")

    # Download companion files (forms.md, reference.md, scripts/, etc.)
    companion_count = 0
    try:
        user, repo, branch, path = _parse_github_url(github_url)
        companion_count = _download_github_directory(user, repo, branch, path, skill_dir)
    except Exception as exc:
        _log.warning("failed to download companion files for %s: %s", skill_id, exc)

    # Auto-generate requirements.txt from pip install commands in markdown
    auto_deps_count = _auto_generate_requirements(skill_dir, body)

    deps.clear_skill_cache()
    desc = str(fm.get("description") or fm.get("desc") or "").strip()
    preview = (body[:200] + "...") if len(body) > 200 else body
    return {"ok": True, "skill_id": skill_id, "title": title, "preview": preview, "desc": desc, "companion_files": companion_count, "auto_deps": auto_deps_count}


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


# ---------------------------------------------------------------------------
# Dependency management
# ---------------------------------------------------------------------------

# Only allow simple package specs (name, name==ver, name>=ver, etc.)
_SAFE_PKG_RE = re.compile(r"^[A-Za-z0-9_-]+([><=!~]+[A-Za-z0-9_.]+)?$")

# Match `pip install pkg1 pkg2` or `pip3 install pkg1 pkg2` patterns in markdown
_PIP_INSTALL_RE = re.compile(r"pip3?\s+install\s+([^\n`\"']+)", re.IGNORECASE)
# Common stdlib/builtin modules to exclude from auto-detection
_STDLIB_NAMES = {
    "os", "sys", "re", "json", "math", "time", "datetime", "pathlib",
    "typing", "collections", "functools", "itertools", "io", "logging",
    "subprocess", "shutil", "hashlib", "uuid", "threading", "copy",
    "dataclasses", "abc", "enum", "struct", "csv", "xml", "html",
    "http", "urllib", "email", "base64", "tempfile", "glob", "fnmatch",
    "textwrap", "string", "operator", "contextlib", "warnings",
}


def _extract_pip_packages_from_text(text: str) -> List[str]:
    """Extract pip package names from `pip install ...` commands in markdown text."""
    seen: set = set()
    pkgs: List[str] = []
    for m in _PIP_INSTALL_RE.finditer(text):
        raw = m.group(1).strip()
        # Split on whitespace to get individual packages
        for token in raw.split():
            # Skip flags like --quiet, -U, etc.
            if token.startswith("-"):
                continue
            # Strip trailing punctuation from markdown
            token = token.rstrip(".,;:)")
            pkg = token.strip()
            if not pkg or not _SAFE_PKG_RE.match(pkg):
                continue
            name_lower = re.split(r"[><=!~]", pkg)[0].strip().lower()
            if name_lower in _STDLIB_NAMES or name_lower in seen:
                continue
            seen.add(name_lower)
            pkgs.append(pkg)
    return pkgs


def _auto_generate_requirements(skill_dir: Path, body: str) -> int:
    """Scan SKILL.md body + companion .md files for pip install commands.
    Write requirements.txt if packages found. Returns count of packages."""
    all_text = body
    # Also scan companion markdown files
    for md_file in skill_dir.glob("*.md"):
        if md_file.name == "SKILL.md":
            continue
        try:
            all_text += "\n" + md_file.read_text(encoding="utf-8")
        except Exception:
            pass
    pkgs = _extract_pip_packages_from_text(all_text)
    if not pkgs:
        return 0
    req_path = skill_dir / "requirements.txt"
    if req_path.exists():
        return 0  # Don't overwrite existing
    req_path.write_text("\n".join(pkgs) + "\n", encoding="utf-8")
    return len(pkgs)


def _read_skill_dependencies(skill_dir: Path, fm: Optional[Dict[str, Any]] = None) -> List[str]:
    """Collect pip dependencies from requirements.txt or frontmatter 'dependencies' field."""
    pkgs: List[str] = []
    # 1. requirements.txt takes priority
    req_path = skill_dir / "requirements.txt"
    if req_path.exists():
        for line in req_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Strip inline comments
            pkg = line.split("#")[0].strip()
            if pkg and _SAFE_PKG_RE.match(pkg):
                pkgs.append(pkg)
    # 2. Frontmatter 'dependencies' field
    if not pkgs and fm is not None:
        deps_raw = fm.get("dependencies")
        if isinstance(deps_raw, list):
            for item in deps_raw:
                pkg = str(item).strip()
                if pkg and _SAFE_PKG_RE.match(pkg):
                    pkgs.append(pkg)
        elif isinstance(deps_raw, str):
            for pkg in deps_raw.split(","):
                pkg = pkg.strip()
                if pkg and _SAFE_PKG_RE.match(pkg):
                    pkgs.append(pkg)
    return pkgs


def _check_package_installed(pkg_name: str) -> bool:
    """Check if a pip package is installed (by import name)."""
    import importlib
    # Strip version specifiers for import check
    name = re.split(r"[><=!~]", pkg_name)[0].strip()
    # Common name mappings (pip name -> import name)
    import_map = {
        "pypdf": "pypdf",
        "pdfplumber": "pdfplumber",
        "reportlab": "reportlab",
        "pytesseract": "pytesseract",
        "pdf2image": "pdf2image",
        "pypdfium2": "pypdfium2",
        "Pillow": "PIL",
        "pillow": "PIL",
        "scikit-learn": "sklearn",
        "python-docx": "docx",
        "beautifulsoup4": "bs4",
        "opencv-python": "cv2",
    }
    import_name = import_map.get(name, name.replace("-", "_"))
    try:
        importlib.import_module(import_name)
        return True
    except ImportError:
        return False


def check_skill_dependencies(
    deps: TeacherSkillDeps,
    skill_id: str,
) -> Dict[str, Any]:
    """Check which dependencies a skill needs and which are missing."""
    _validate_skill_id(skill_id)
    skill_dir = deps.teacher_skills_dir / skill_id
    if not skill_dir.exists():
        return {"ok": False, "error": "skill not found"}
    md_path = skill_dir / "SKILL.md"
    fm: Dict[str, Any] = {}
    if md_path.exists():
        from .skills.loader import _parse_yaml_frontmatter
        fm, _ = _parse_yaml_frontmatter(md_path.read_text(encoding="utf-8"))
    packages = _read_skill_dependencies(skill_dir, fm)
    if not packages:
        return {"ok": True, "packages": [], "missing": [], "all_installed": True}
    missing = [p for p in packages if not _check_package_installed(p)]
    return {
        "ok": True,
        "packages": packages,
        "missing": missing,
        "all_installed": len(missing) == 0,
    }


def install_skill_dependencies(
    deps: TeacherSkillDeps,
    skill_id: str,
    packages: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Install missing pip dependencies for a skill."""
    import subprocess
    import sys
    _validate_skill_id(skill_id)
    skill_dir = deps.teacher_skills_dir / skill_id
    if not skill_dir.exists():
        return {"ok": False, "error": "skill not found"}

    # If no explicit package list, detect from skill
    if packages is None:
        md_path = skill_dir / "SKILL.md"
        fm: Dict[str, Any] = {}
        if md_path.exists():
            from .skills.loader import _parse_yaml_frontmatter
            fm, _ = _parse_yaml_frontmatter(md_path.read_text(encoding="utf-8"))
        packages = _read_skill_dependencies(skill_dir, fm)

    if not packages:
        return {"ok": True, "installed": [], "message": "no dependencies to install"}

    # Validate all package names for safety
    for pkg in packages:
        if not _SAFE_PKG_RE.match(pkg):
            return {"ok": False, "error": f"unsafe package spec rejected: {pkg}"}

    # Only install missing packages
    to_install = [p for p in packages if not _check_package_installed(p)]
    if not to_install:
        return {"ok": True, "installed": [], "message": "all dependencies already installed"}

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet"] + to_install,
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            _log.warning("pip install failed for skill %s: %s", skill_id, result.stderr)
            return {"ok": False, "error": result.stderr.strip() or "pip install failed", "installed": []}
        return {"ok": True, "installed": to_install}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "pip install timed out (120s)"}
    except Exception as exc:
        _log.warning("pip install error for skill %s: %s", skill_id, exc)
        return {"ok": False, "error": str(exc)}
