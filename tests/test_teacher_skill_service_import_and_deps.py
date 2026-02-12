from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any, List

import pytest

from services.api import teacher_skill_service as svc


class _FakeResp:
    def __init__(self, *, url: str, data: bytes) -> None:
        self.url = url
        self._data = data

    def read(self, _size: int = -1) -> bytes:
        return self._data

    def __enter__(self) -> "_FakeResp":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class _CacheProbe:
    def __init__(self) -> None:
        self.calls = 0

    def clear(self) -> None:
        self.calls += 1


def _make_deps(tmp_path: Path) -> tuple[svc.TeacherSkillDeps, _CacheProbe]:
    probe = _CacheProbe()
    skills_dir = tmp_path / "teacher_skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    deps = svc.TeacherSkillDeps(teacher_skills_dir=skills_dir, clear_skill_cache=probe.clear)
    return deps, probe


def test_github_url_to_raw_accepts_raw_host_without_skill_suffix() -> None:
    out = svc._github_url_to_raw("https://raw.githubusercontent.com/u/r/main/skill-dir")
    assert out.endswith("/skill-dir/SKILL.md")


def test_github_url_to_raw_rejects_unsupported_github_path() -> None:
    with pytest.raises(ValueError, match="unsupported GitHub URL format"):
        svc._github_url_to_raw("https://github.com/u/r/issues/123")


def test_download_skill_md_success(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = b"# Skill\n\nbody"

    def _urlopen(_req: Any, timeout: int = 15) -> _FakeResp:
        assert timeout == 15
        return _FakeResp(url="https://raw.githubusercontent.com/u/r/main/SKILL.md", data=payload)

    monkeypatch.setattr(svc.urllib.request, "urlopen", _urlopen)
    text = svc._download_skill_md("https://raw.githubusercontent.com/u/r/main/SKILL.md")
    assert text == payload.decode("utf-8")


def test_download_skill_md_rejects_redirect_host(monkeypatch: pytest.MonkeyPatch) -> None:
    def _urlopen(_req: Any, timeout: int = 15) -> _FakeResp:
        return _FakeResp(url="https://evil.example.com/payload", data=b"x")

    monkeypatch.setattr(svc.urllib.request, "urlopen", _urlopen)
    with pytest.raises(ValueError, match="redirect to disallowed host"):
        svc._download_skill_md("https://raw.githubusercontent.com/u/r/main/SKILL.md")


def test_download_skill_md_rejects_oversized(monkeypatch: pytest.MonkeyPatch) -> None:
    too_big = b"x" * (256 * 1024 + 1)

    monkeypatch.setattr(
        svc.urllib.request,
        "urlopen",
        lambda _req, timeout=15: _FakeResp(
            url="https://raw.githubusercontent.com/u/r/main/SKILL.md", data=too_big
        ),
    )
    with pytest.raises(ValueError, match="exceeds 256 KB"):
        svc._download_skill_md("https://raw.githubusercontent.com/u/r/main/SKILL.md")


def test_download_skill_md_wraps_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def _urlopen(_req: Any, timeout: int = 15) -> _FakeResp:
        raise svc.urllib.error.HTTPError("u", 404, "not found", hdrs=None, fp=None)

    monkeypatch.setattr(svc.urllib.request, "urlopen", _urlopen)
    with pytest.raises(ValueError, match="HTTP 404"):
        svc._download_skill_md("https://raw.githubusercontent.com/u/r/main/SKILL.md")


def test_download_skill_md_wraps_unknown_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        svc.urllib.request,
        "urlopen",
        lambda _req, timeout=15: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    with pytest.raises(ValueError, match="download failed"):
        svc._download_skill_md("https://raw.githubusercontent.com/u/r/main/SKILL.md")


@pytest.mark.parametrize(
    "url,expected",
    [
        (
            "https://github.com/u/repo/tree/dev/path/to/skill",
            ("u", "repo", "dev", "path/to/skill"),
        ),
        ("https://github.com/u/repo", ("u", "repo", "main", "")),
    ],
)
def test_parse_github_url(url: str, expected: tuple[str, str, str, str]) -> None:
    assert svc._parse_github_url(url) == expected


def test_parse_github_url_rejects_invalid() -> None:
    with pytest.raises(ValueError, match="unsupported GitHub URL format"):
        svc._parse_github_url("https://example.com/u/repo")


def test_download_github_directory_happy_path_with_recursion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root_payload = [
        {"name": ".hidden", "type": "file", "download_url": "https://raw.githubusercontent.com/u/r/main/.x"},
        {"name": "SKILL.md", "type": "file", "download_url": "https://raw.githubusercontent.com/u/r/main/SKILL.md"},
        {"name": "forms.md", "type": "file", "download_url": "https://raw.githubusercontent.com/u/r/main/forms.md"},
        {"name": "badhost.md", "type": "file", "download_url": "https://evil.example.com/file"},
        {"name": "empty.md", "type": "file"},
        {"name": "scripts", "type": "dir"},
    ]
    child_payload = [{"name": "helper.py", "type": "file", "download_url": "https://github.com/u/r/raw/main/helper.py"}]

    def _urlopen(req: Any, timeout: int = 15) -> _FakeResp:
        url = req.full_url if hasattr(req, "full_url") else str(req)
        if "contents/path?ref=main" in url:
            return _FakeResp(url=url, data=json.dumps(root_payload).encode("utf-8"))
        if "contents/path/scripts?ref=main" in url:
            return _FakeResp(url=url, data=json.dumps(child_payload).encode("utf-8"))
        if url.endswith("forms.md"):
            return _FakeResp(url=url, data=b"form")
        if url.endswith("helper.py"):
            return _FakeResp(url=url, data=b"print('ok')\n")
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr(svc.urllib.request, "urlopen", _urlopen)

    out = svc._download_github_directory("u", "r", "main", "path", tmp_path)

    assert out == 2
    assert (tmp_path / "forms.md").read_text(encoding="utf-8") == "form"
    assert (tmp_path / "scripts" / "helper.py").read_text(encoding="utf-8") == "print('ok')\n"


def test_download_github_directory_listing_failure_returns_zero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        svc.urllib.request,
        "urlopen",
        lambda req, timeout=15: (_ for _ in ()).throw(RuntimeError("api down")),
    )
    assert svc._download_github_directory("u", "r", "main", "x", tmp_path) == 0


def test_download_github_directory_non_list_payload_returns_zero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        svc.urllib.request,
        "urlopen",
        lambda req, timeout=15: _FakeResp(url=req.full_url, data=b'{"not":"list"}'),
    )
    assert svc._download_github_directory("u", "r", "main", "x", tmp_path) == 0


def test_download_github_directory_file_download_failure_is_skipped(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = [{"name": "forms.md", "type": "file", "download_url": "https://raw.githubusercontent.com/u/r/main/forms.md"}]

    def _urlopen(req: Any, timeout: int = 15) -> _FakeResp:
        url = req.full_url if hasattr(req, "full_url") else str(req)
        if "api.github.com" in url:
            return _FakeResp(url=url, data=json.dumps(payload).encode("utf-8"))
        raise RuntimeError("download failed")

    monkeypatch.setattr(svc.urllib.request, "urlopen", _urlopen)
    assert svc._download_github_directory("u", "r", "main", "x", tmp_path) == 0


def test_infer_skill_id_from_url_variants() -> None:
    assert svc._infer_skill_id_from_url("https://github.com/u/r/tree/main/skills/My Skill/") == "my-skill"
    out = svc._infer_skill_id_from_url("https://github.com/u/r/tree/main/skills/demo/SKILL.md")
    assert out == "demo"


def test_rebuild_skill_md_content() -> None:
    content = svc._rebuild_skill_md_content({"title": "T", "allowed_roles": ["teacher"]}, "Body")
    assert content.startswith("---\n")
    assert "title: T" in content
    assert content.endswith("\n")


def test_import_skill_from_github_injects_roles_and_companions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deps, probe = _make_deps(tmp_path)
    skill_md = "---\ntitle: Imported Skill\n---\n\nBody\n\npip install pandas\n"

    monkeypatch.setattr(svc, "_download_skill_md", lambda raw_url: skill_md)
    monkeypatch.setattr(svc, "_download_github_directory", lambda user, repo, branch, path, dest: 2)
    monkeypatch.setattr(svc, "_parse_github_url", lambda url: ("u", "r", "main", "skills/imported"))
    monkeypatch.setattr(svc, "_auto_generate_requirements", lambda skill_dir, body: 1)

    out = svc.import_skill_from_github(deps, "https://github.com/u/r/tree/main/skills/imported")

    assert out["ok"] is True
    assert out["skill_id"] == "imported-skill"
    assert out["companion_files"] == 2
    assert out["auto_deps"] == 1
    assert probe.calls == 1
    md = (deps.teacher_skills_dir / "imported-skill" / "SKILL.md").read_text(encoding="utf-8")
    assert "allowed_roles" in md


def test_import_skill_from_github_uses_heading_when_frontmatter_title_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deps, _probe = _make_deps(tmp_path)
    skill_md = "---\ndescription: Demo\n---\n\n# Heading Skill\nBody"

    monkeypatch.setattr(svc, "_download_skill_md", lambda raw_url: skill_md)
    monkeypatch.setattr(svc, "_download_github_directory", lambda *args, **kwargs: 0)
    monkeypatch.setattr(svc, "_parse_github_url", lambda url: ("u", "r", "main", "skills/x"))
    monkeypatch.setattr(svc, "_auto_generate_requirements", lambda *_: 0)

    out = svc.import_skill_from_github(deps, "https://github.com/u/r/tree/main/skills/x")
    assert out["ok"] is True
    assert out["title"] == "Heading Skill"


def test_import_skill_from_github_exists_without_overwrite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deps, _probe = _make_deps(tmp_path)
    existing = deps.teacher_skills_dir / "imported-skill"
    existing.mkdir(parents=True)

    monkeypatch.setattr(svc, "_download_skill_md", lambda raw_url: "---\ntitle: Imported Skill\n---\nBody")

    out = svc.import_skill_from_github(deps, "https://github.com/u/r/tree/main/skills/imported")

    assert out["ok"] is False
    assert out["exists"] is True


def test_import_skill_from_github_overwrite_replaces_existing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deps, _probe = _make_deps(tmp_path)
    existing = deps.teacher_skills_dir / "imported-skill"
    existing.mkdir(parents=True)
    (existing / "old.txt").write_text("old", encoding="utf-8")

    monkeypatch.setattr(svc, "_download_skill_md", lambda raw_url: "---\ntitle: Imported Skill\n---\nNew body")
    monkeypatch.setattr(svc, "_download_github_directory", lambda *args, **kwargs: 0)
    monkeypatch.setattr(svc, "_parse_github_url", lambda url: ("u", "r", "main", "skills/imported"))
    monkeypatch.setattr(svc, "_auto_generate_requirements", lambda *_: 0)

    out = svc.import_skill_from_github(
        deps,
        "https://github.com/u/r/tree/main/skills/imported",
        overwrite=True,
    )

    assert out["ok"] is True
    assert (existing / "old.txt").exists() is False
    assert (existing / "SKILL.md").exists()


def test_import_skill_from_github_companion_failure_is_non_fatal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deps, _probe = _make_deps(tmp_path)

    monkeypatch.setattr(svc, "_download_skill_md", lambda raw_url: "---\ntitle: Imported Skill\n---\nBody")
    monkeypatch.setattr(
        svc,
        "_parse_github_url",
        lambda url: (_ for _ in ()).throw(ValueError("bad url")),
    )
    monkeypatch.setattr(svc, "_auto_generate_requirements", lambda *_: 0)

    out = svc.import_skill_from_github(deps, "https://github.com/u/r/tree/main/skills/imported")
    assert out["ok"] is True
    assert out["companion_files"] == 0


def test_preview_github_skill_prefers_frontmatter_title(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        svc,
        "_download_skill_md",
        lambda raw_url: "---\ntitle: Demo\nkeywords:\n  - a\n  - b\n---\nBody",
    )

    out = svc.preview_github_skill(
        deps=svc.TeacherSkillDeps(teacher_skills_dir=Path("."), clear_skill_cache=lambda: None),
        github_url="https://github.com/u/r/tree/main/skills/demo",
    )

    assert out["ok"] is True
    assert out["title"] == "Demo"
    assert out["keywords"] == ["a", "b"]


def test_preview_github_skill_uses_heading_then_slug(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(svc, "_download_skill_md", lambda raw_url: "---\n---\n# Heading Demo\nBody")

    out = svc.preview_github_skill(
        deps=svc.TeacherSkillDeps(teacher_skills_dir=Path("."), clear_skill_cache=lambda: None),
        github_url="https://github.com/u/r/tree/main/skills/demo",
    )
    assert out["title"] == "Heading Demo"

    monkeypatch.setattr(svc, "_download_skill_md", lambda raw_url: "---\n---\nNo heading")
    monkeypatch.setattr(svc, "_infer_skill_id_from_url", lambda url: "fallback-skill")

    out2 = svc.preview_github_skill(
        deps=svc.TeacherSkillDeps(teacher_skills_dir=Path("."), clear_skill_cache=lambda: None),
        github_url="https://github.com/u/r/tree/main/skills/demo",
    )
    assert out2["title"] == "fallback-skill"


def test_extract_pip_packages_from_text_filters_flags_stdlib_and_dedup() -> None:
    text = """
    pip install -U numpy pandas==2.1 os bad/name numpy
    pip3 install scipy matplotlib
    """
    out = svc._extract_pip_packages_from_text(text)
    assert out == ["numpy", "pandas==2.1", "scipy", "matplotlib"]


def test_auto_generate_requirements_writes_and_respects_existing(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "forms.md").write_text("pip install pandas", encoding="utf-8")

    count = svc._auto_generate_requirements(skill_dir, "pip install numpy")
    assert count == 2
    req = (skill_dir / "requirements.txt").read_text(encoding="utf-8")
    assert req.splitlines() == ["numpy", "pandas"]

    # Existing requirements should not be overwritten.
    count2 = svc._auto_generate_requirements(skill_dir, "pip install seaborn")
    assert count2 == 0
    req2 = (skill_dir / "requirements.txt").read_text(encoding="utf-8")
    assert req2.splitlines() == ["numpy", "pandas"]


def test_auto_generate_requirements_handles_empty_and_read_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("pip install ignored", encoding="utf-8")
    bad = skill_dir / "broken.md"
    bad.write_text("pip install numpy", encoding="utf-8")

    orig_read_text = Path.read_text

    def _patched_read_text(path: Path, *args: Any, **kwargs: Any) -> str:
        if path == bad:
            raise OSError("cannot read")
        return orig_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _patched_read_text)

    # no packages in body, SKILL.md should be ignored, broken.md read error should be tolerated
    assert svc._auto_generate_requirements(skill_dir, "no install command here") == 0
    assert (skill_dir / "requirements.txt").exists() is False


def test_read_skill_dependencies_requirements_priority_and_frontmatter_fallback(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir(parents=True)

    (skill_dir / "requirements.txt").write_text("# note\nnumpy\npandas==2.1  # pin\ninvalid pkg\n", encoding="utf-8")
    out = svc._read_skill_dependencies(skill_dir, {"dependencies": ["scipy"]})
    assert out == ["numpy", "pandas==2.1"]

    (skill_dir / "requirements.txt").unlink()
    out2 = svc._read_skill_dependencies(skill_dir, {"dependencies": ["scipy", "bad pkg"]})
    assert out2 == ["scipy"]

    out3 = svc._read_skill_dependencies(skill_dir, {"dependencies": "numpy, pandas>=2.0, bad pkg"})
    assert out3 == ["numpy", "pandas>=2.0"]


def test_check_package_installed_import_name_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: List[str] = []

    def _import_module(name: str) -> Any:
        captured.append(name)
        if name == "docx":
            return object()
        raise ImportError("missing")

    monkeypatch.setattr("importlib.import_module", _import_module)

    assert svc._check_package_installed("python-docx") is True
    assert svc._check_package_installed("scikit-learn") is False
    assert captured[0] == "docx"
    assert captured[1] == "sklearn"


def test_check_skill_dependencies_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    deps, _probe = _make_deps(tmp_path)

    out_missing = svc.check_skill_dependencies(deps, "missing-skill")
    assert out_missing["ok"] is False

    skill_dir = deps.teacher_skills_dir / "demo-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\n---\nBody", encoding="utf-8")
    (skill_dir / "requirements.txt").write_text("numpy\nseaborn\n", encoding="utf-8")

    monkeypatch.setattr(svc, "_check_package_installed", lambda pkg: pkg == "numpy")

    out = svc.check_skill_dependencies(deps, "demo-skill")
    assert out["ok"] is True
    assert out["packages"] == ["numpy", "seaborn"]
    assert out["missing"] == ["seaborn"]
    assert out["all_installed"] is False


def test_check_skill_dependencies_no_packages(tmp_path: Path) -> None:
    deps, _probe = _make_deps(tmp_path)
    skill_dir = deps.teacher_skills_dir / "demo-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\n---\nBody", encoding="utf-8")

    out = svc.check_skill_dependencies(deps, "demo-skill")
    assert out == {"ok": True, "packages": [], "missing": [], "all_installed": True}


def test_install_skill_dependencies_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    deps, _probe = _make_deps(tmp_path)

    # not found
    not_found = svc.install_skill_dependencies(deps, "missing-skill")
    assert not_found["ok"] is False

    skill_dir = deps.teacher_skills_dir / "demo-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\n---\nBody", encoding="utf-8")

    # no packages
    monkeypatch.setattr(svc, "_read_skill_dependencies", lambda *_: [])
    no_pkgs = svc.install_skill_dependencies(deps, "demo-skill", packages=None)
    assert no_pkgs["ok"] is True
    assert no_pkgs["message"] == "no dependencies to install"

    # unsafe package
    unsafe = svc.install_skill_dependencies(deps, "demo-skill", packages=["bad pkg"])
    assert unsafe["ok"] is False

    # all installed
    monkeypatch.setattr(svc, "_check_package_installed", lambda pkg: True)
    all_ok = svc.install_skill_dependencies(deps, "demo-skill", packages=["numpy"])
    assert all_ok == {"ok": True, "installed": [], "message": "all dependencies already installed"}

    # subprocess non-zero
    monkeypatch.setattr(svc, "_check_package_installed", lambda pkg: False)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout="", stderr="boom"),
    )
    failed = svc.install_skill_dependencies(deps, "demo-skill", packages=["numpy"])
    assert failed["ok"] is False
    assert failed["installed"] == []

    # timeout
    def _raise_timeout(*args: Any, **kwargs: Any) -> Any:
        raise subprocess.TimeoutExpired(cmd="pip", timeout=120)

    monkeypatch.setattr(subprocess, "run", _raise_timeout)
    timed_out = svc.install_skill_dependencies(deps, "demo-skill", packages=["numpy"])
    assert timed_out["ok"] is False
    assert "timed out" in timed_out["error"]

    # generic exception
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("subprocess broken")),
    )
    errored = svc.install_skill_dependencies(deps, "demo-skill", packages=["numpy"])
    assert errored["ok"] is False
    assert "subprocess broken" in errored["error"]

    # success
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="ok", stderr=""),
    )
    success = svc.install_skill_dependencies(deps, "demo-skill", packages=["numpy", "pandas"])
    assert success == {"ok": True, "installed": ["numpy", "pandas"]}
