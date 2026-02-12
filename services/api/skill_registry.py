from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

_log = logging.getLogger(__name__)

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    _log.debug("import failed", exc_info=True)
    yaml = None


@dataclass(frozen=True)
class SkillEntry:
    id: str
    title: str
    desc: str
    prompts: List[str]
    examples: List[str]
    allowed_roles: List[str]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "desc": self.desc,
            "prompts": self.prompts,
            "examples": self.examples,
            "allowed_roles": self.allowed_roles,
        }


def _as_str_list(value: Any) -> List[str]:
    if not value:
        return []
    if isinstance(value, str):
        s = value.strip()
        return [s] if s else []
    if isinstance(value, list):
        out: List[str] = []
        for item in value:
            if item is None:
                continue
            s = str(item).strip()
            if s:
                out.append(s)
        return out
    return []


def _load_yaml(path: Path) -> Dict[str, Any]:
    if yaml is None:
        return {}
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        _log.warning("failed to parse skill YAML at %s", path, exc_info=True)
        return {}
    return raw if isinstance(raw, dict) else {}


def load_skill_entry(skill_dir: Path) -> Optional[SkillEntry]:
    if not skill_dir.is_dir():
        return None

    skill_id = skill_dir.name
    spec_path = skill_dir / "skill.yaml"
    if not spec_path.exists():
        return None
    spec = _load_yaml(spec_path)

    title = str(spec.get("title") or spec.get("display_name") or "").strip()
    desc = str(spec.get("desc") or spec.get("description") or "").strip()
    allowed_roles = _as_str_list(spec.get("allowed_roles"))

    ui = spec.get("ui") if isinstance(spec.get("ui"), dict) else {}
    prompts = _as_str_list(ui.get("prompts") if isinstance(ui, dict) else spec.get("prompts"))
    examples = _as_str_list(ui.get("examples") if isinstance(ui, dict) else spec.get("examples"))

    title_final = title if title else "未命名技能"
    desc_final = desc if desc else ""

    return SkillEntry(
        id=skill_id,
        title=title_final,
        desc=desc_final,
        prompts=prompts,
        examples=examples,
        allowed_roles=allowed_roles,
    )


def list_skill_entries(skills_dir: Path) -> List[SkillEntry]:
    if not skills_dir.exists() or not skills_dir.is_dir():
        return []

    items: List[SkillEntry] = []
    for folder in sorted(skills_dir.iterdir(), key=lambda p: p.name):
        entry = load_skill_entry(folder)
        if entry is None:
            continue
        items.append(entry)
    return items
