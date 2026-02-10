from __future__ import annotations

import os
import threading
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml  # type: ignore

from .spec import SkillRoutingSpec, SkillSpec, parse_skill_spec


@dataclass(frozen=True)
class SkillLoadError:
    skill_id: str
    path: str
    message: str

    def as_dict(self) -> Dict[str, str]:
        return {"skill_id": self.skill_id, "path": self.path, "message": self.message}


@dataclass(frozen=True)
class LoadedSkills:
    skills: Dict[str, SkillSpec]
    errors: List[SkillLoadError]


_CACHE_LOCK = threading.Lock()
_CACHE: Dict[str, Tuple[Tuple[Tuple[str, Tuple[Tuple[str, int], ...]], ...], LoadedSkills]] = {}


def _normalize_path(value: Path) -> Path:
    try:
        return value.resolve()
    except Exception:
        return value


def _resolve_source_dirs(skills_dir: Path) -> List[Path]:
    sources: List[Path] = []
    primary = _normalize_path(skills_dir)
    sources.append(primary)

    home = Path(os.path.expanduser("~"))
    claude_skills = _normalize_path(home / ".claude" / "skills")
    if claude_skills != primary:
        sources.append(claude_skills)

    return sources


def _dir_signature(skills_dir: Path) -> Tuple[Tuple[str, int], ...]:
    entries: List[Tuple[str, int]] = []
    if not skills_dir.exists() or not skills_dir.is_dir():
        return tuple()
    for folder in skills_dir.iterdir():
        if not folder.is_dir():
            continue
        spec_path = folder / "skill.yaml"
        skill_md_path = folder / "SKILL.md"
        try:
            spec_mtime = int(spec_path.stat().st_mtime_ns) if spec_path.exists() else 0
        except Exception:
            spec_mtime = 0
        try:
            skill_md_mtime = int(skill_md_path.stat().st_mtime_ns) if skill_md_path.exists() else 0
        except Exception:
            skill_md_mtime = 0
        entries.append((folder.name, max(spec_mtime, skill_md_mtime)))
    return tuple(sorted(entries))


def _signature(source_dirs: List[Path]) -> Tuple[Tuple[str, Tuple[Tuple[str, int], ...]], ...]:
    signed: List[Tuple[str, Tuple[Tuple[str, int], ...]]] = []
    for src in source_dirs:
        signed.append((str(_normalize_path(src)), _dir_signature(src)))
    return tuple(signed)




def _ensure_minimal_routing(spec: SkillSpec) -> SkillSpec:
    routing = spec.routing
    keywords = list(getattr(routing, "keywords", []) or [])
    intents = list(getattr(routing, "intents", []) or [])
    changed = False

    if not keywords:
        keywords = [spec.skill_id]
        changed = True
    if not intents:
        intents = ["generic"]
        changed = True

    if not changed:
        return spec

    normalized_routing = SkillRoutingSpec(
        keywords=keywords,
        negative_keywords=list(getattr(routing, "negative_keywords", []) or []),
        intents=intents,
        keyword_weights=dict(getattr(routing, "keyword_weights", {}) or {}),
        min_score=int(getattr(routing, "min_score", 3) or 3),
        min_margin=int(getattr(routing, "min_margin", 1) or 1),
        confidence_floor=float(getattr(routing, "confidence_floor", 0.28) or 0.28),
        match_mode=str(getattr(routing, "match_mode", "substring") or "substring"),
    )
    return replace(spec, routing=normalized_routing)


def _load_skill_spec_from_folder(skill_id: str, folder: Path) -> Tuple[Optional[SkillSpec], Optional[SkillLoadError]]:
    spec_path = folder / "skill.yaml"
    if spec_path.exists():
        try:
            raw = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
        except Exception as exc:
            return None, SkillLoadError(skill_id=skill_id, path=str(spec_path), message=f"YAML parse failed: {exc}")
        if not isinstance(raw, dict):
            return None, SkillLoadError(skill_id=skill_id, path=str(spec_path), message="skill.yaml must be a mapping")
        try:
            spec = parse_skill_spec(skill_id=skill_id, source_path=str(spec_path), raw=raw)
            spec = _ensure_minimal_routing(spec)
            return spec, None
        except Exception as exc:
            return None, SkillLoadError(skill_id=skill_id, path=str(spec_path), message=f"invalid skill spec: {exc}")

    skill_md_path = folder / "SKILL.md"
    if skill_md_path.exists():
        try:
            content = skill_md_path.read_text(encoding="utf-8").strip()
        except Exception as exc:
            return None, SkillLoadError(skill_id=skill_id, path=str(skill_md_path), message=f"SKILL.md read failed: {exc}")

        lines = [line.strip() for line in content.splitlines() if line.strip()]
        title = skill_id
        for line in lines:
            if line.startswith("#"):
                title = line.lstrip("#").strip() or skill_id
                if "\\n" in title:
                    title = title.split("\\n", 1)[0].strip() or title
                break

        raw: Dict[str, Any] = {
            "schema_version": 1,
            "title": title,
            "description": content,
            "agent": {
                "prompt_modules": [],
                "context_providers": [],
                "tools": {},
                "budgets": {},
                "model_policy": {},
            },
            "routing": {},
        }
        try:
            spec = parse_skill_spec(skill_id=skill_id, source_path=str(skill_md_path), raw=raw)
            spec = _ensure_minimal_routing(spec)
            return spec, None
        except Exception as exc:
            return None, SkillLoadError(skill_id=skill_id, path=str(skill_md_path), message=f"invalid SKILL.md derived spec: {exc}")

    return None, SkillLoadError(skill_id=skill_id, path=str(spec_path), message="skill.yaml not found")


def load_skills(skills_dir: Path) -> LoadedSkills:
    source_dirs = _resolve_source_dirs(skills_dir)
    key = "||".join(str(_normalize_path(src)) for src in source_dirs)
    sig = _signature(source_dirs)

    with _CACHE_LOCK:
        cached = _CACHE.get(key)
        if cached and cached[0] == sig:
            return cached[1]

    skills: Dict[str, SkillSpec] = {}
    errors: List[SkillLoadError] = []
    found_any_dir = False

    for source_dir in source_dirs:
        if not source_dir.exists() or not source_dir.is_dir():
            continue
        found_any_dir = True
        for folder in sorted(source_dir.iterdir(), key=lambda p: p.name):
            if not folder.is_dir():
                continue
            skill_id = folder.name
            spec, err = _load_skill_spec_from_folder(skill_id, folder)
            if err is not None:
                errors.append(err)
                continue
            if spec is not None:
                skills[skill_id] = spec

    if not found_any_dir:
        errors.append(SkillLoadError(skill_id="", path=key, message="skills dir not found"))

    loaded = LoadedSkills(skills=skills, errors=errors)
    with _CACHE_LOCK:
        _CACHE[key] = (sig, loaded)
    return loaded
