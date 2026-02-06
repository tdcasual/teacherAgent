from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml  # type: ignore

from .spec import SkillSpec, parse_skill_spec


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
_CACHE: Dict[str, Tuple[Tuple[Tuple[str, int], ...], LoadedSkills]] = {}


def _signature(skills_dir: Path) -> Tuple[Tuple[str, int], ...]:
    entries: List[Tuple[str, int]] = []
    if not skills_dir.exists():
        return tuple()
    for folder in skills_dir.iterdir():
        if not folder.is_dir():
            continue
        spec_path = folder / "skill.yaml"
        try:
            mtime_ns = int(spec_path.stat().st_mtime_ns) if spec_path.exists() else 0
        except Exception:
            mtime_ns = 0
        entries.append((folder.name, mtime_ns))
    return tuple(sorted(entries))


def load_skills(skills_dir: Path) -> LoadedSkills:
    key = str(skills_dir.resolve())
    sig = _signature(skills_dir)
    with _CACHE_LOCK:
        cached = _CACHE.get(key)
        if cached and cached[0] == sig:
            return cached[1]

    skills: Dict[str, SkillSpec] = {}
    errors: List[SkillLoadError] = []

    if not skills_dir.exists() or not skills_dir.is_dir():
        loaded = LoadedSkills(skills={}, errors=[SkillLoadError(skill_id="", path=key, message="skills dir not found")])
        with _CACHE_LOCK:
            _CACHE[key] = (sig, loaded)
        return loaded

    for folder in sorted(skills_dir.iterdir(), key=lambda p: p.name):
        if not folder.is_dir():
            continue
        skill_id = folder.name
        spec_path = folder / "skill.yaml"
        if not spec_path.exists():
            errors.append(SkillLoadError(skill_id=skill_id, path=str(spec_path), message="skill.yaml not found"))
            continue
        try:
            raw = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(SkillLoadError(skill_id=skill_id, path=str(spec_path), message=f"YAML parse failed: {exc}"))
            continue
        if not isinstance(raw, dict):
            errors.append(SkillLoadError(skill_id=skill_id, path=str(spec_path), message="skill.yaml must be a mapping"))
            continue
        try:
            spec = parse_skill_spec(skill_id=skill_id, source_path=str(spec_path), raw=raw)
            skills[skill_id] = spec
        except Exception as exc:
            errors.append(SkillLoadError(skill_id=skill_id, path=str(spec_path), message=f"invalid skill spec: {exc}"))

    loaded = LoadedSkills(skills=skills, errors=errors)
    with _CACHE_LOCK:
        _CACHE[key] = (sig, loaded)
    return loaded

