from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml  # type: ignore

from .spec import SkillRoutingSpec, SkillSpec, parse_skill_spec

_log = logging.getLogger(__name__)

_SKILL_INCLUDE_MAX_FILE_CHARS = 16_000
_SKILL_INCLUDE_MAX_TOTAL_CHARS = 48_000



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
_CACHE_GEN = 0  # incremented on clear_cache(); stale builds check this before writing


def _normalize_path(value: Path) -> Path:
    try:
        return value.resolve()
    except Exception:
        _log.debug("operation failed", exc_info=True)
        return value


def _parse_yaml_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
    """Parse optional YAML frontmatter delimited by ``---`` lines."""
    # Normalize Windows line endings before parsing
    content = content.replace("\r\n", "\n").replace("\r", "\n")
    stripped = content.strip()
    if not stripped.startswith("---"):
        return {}, content
    lines = stripped.split("\n")
    end_idx = -1
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx < 0:
        return {}, content
    fm_text = "\n".join(lines[1:end_idx])
    body = "\n".join(lines[end_idx + 1:]).strip()
    try:
        fm = yaml.safe_load(fm_text)
    except Exception:
        _log.debug("operation failed", exc_info=True)
        return {}, content
    if not isinstance(fm, dict):
        return {}, content
    return fm, body


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_str_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        s = value.strip()
        return [s] if s else []
    if not isinstance(value, list):
        return []
    out: List[str] = []
    for item in value:
        if item is None:
            continue
        s = str(item).strip()
        if s:
            out.append(s)
    return out


def _collect_skill_includes(folder: Path, fm: Dict[str, Any]) -> str:
    include_keys = ("includes", "references")
    include_paths: List[str] = []
    for key in include_keys:
        include_paths.extend(_as_str_list(fm.get(key)))

    if not include_paths:
        return ""

    base = _normalize_path(folder)
    chunks: List[str] = []
    total_chars = 0

    for rel in include_paths:
        rel_text = str(rel).strip()
        if not rel_text:
            continue
        rel_path = Path(rel_text)
        if rel_path.is_absolute():
            _log.warning("skip absolute include path: %s", rel_text)
            continue
        target = _normalize_path(folder / rel_path)
        if target == base or base not in target.parents:
            _log.warning("skip include outside skill dir: %s", rel_text)
            continue
        if not target.exists() or not target.is_file():
            _log.warning("skip missing include path: %s", rel_text)
            continue
        try:
            text = target.read_text(encoding="utf-8").strip()
        except Exception:
            _log.warning("failed to read include path: %s", rel_text, exc_info=True)
            continue
        if not text:
            continue
        if len(text) > _SKILL_INCLUDE_MAX_FILE_CHARS:
            text = text[:_SKILL_INCLUDE_MAX_FILE_CHARS]

        block = f"[Reference: {rel_path.as_posix()}]\n{text}"
        remain = _SKILL_INCLUDE_MAX_TOTAL_CHARS - total_chars
        if remain <= 0:
            break
        if len(block) > remain:
            block = block[:remain]
        chunks.append(block)
        total_chars += len(block)

    return "\n\n".join(chunks)


def _resolve_source_dirs(skills_dir: Path, teacher_skills_dir: Optional[Path] = None) -> List[Path]:
    sources: List[Path] = []

    # Teacher skills dir has lowest priority (scanned first, overridden by later)
    if teacher_skills_dir is not None:
        sources.append(_normalize_path(teacher_skills_dir))

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
            _log.debug("numeric conversion failed", exc_info=True)
            spec_mtime = 0
        try:
            skill_md_mtime = int(skill_md_path.stat().st_mtime_ns) if skill_md_path.exists() else 0
        except Exception:
            _log.debug("numeric conversion failed", exc_info=True)
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
        # Use title words as fallback keywords.
        # For CJK text (no spaces), use the full title as a single keyword
        # since substring matching handles it. Also extract any space-separated
        # segments that are >= 2 chars.
        title_words = [w.strip() for w in spec.title.split() if len(w.strip()) >= 2]
        if not title_words and spec.title.strip():
            # CJK or single-word title: use the full title as keyword
            title_words = [spec.title.strip()]
        keywords = title_words if title_words else [spec.skill_id]
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
            _log.debug("file read failed", exc_info=True)
            return None, SkillLoadError(skill_id=skill_id, path=str(spec_path), message=f"YAML parse failed: {exc}")
        if not isinstance(raw, dict):
            return None, SkillLoadError(skill_id=skill_id, path=str(spec_path), message="skill.yaml must be a mapping")
        try:
            spec = parse_skill_spec(skill_id=skill_id, source_path=str(spec_path), raw=raw)
            spec = _ensure_minimal_routing(spec)
            return spec, None
        except Exception as exc:
            _log.debug("operation failed", exc_info=True)
            return None, SkillLoadError(skill_id=skill_id, path=str(spec_path), message=f"invalid skill spec: {exc}")

    skill_md_path = folder / "SKILL.md"
    if skill_md_path.exists():
        try:
            content = skill_md_path.read_text(encoding="utf-8").strip()
        except Exception as exc:
            _log.debug("file read failed", exc_info=True)
            return None, SkillLoadError(skill_id=skill_id, path=str(skill_md_path), message=f"SKILL.md read failed: {exc}")

        fm, body = _parse_yaml_frontmatter(content)

        # Derive title from frontmatter or first heading
        title = str(fm.get("name") or fm.get("title") or "").strip()
        if not title:
            for line in body.splitlines():
                stripped_line = line.strip()
                if stripped_line.startswith("#"):
                    title = stripped_line.lstrip("#").strip()
                    if "\\n" in title:
                        title = title.split("\\n", 1)[0].strip()
                    break
        title = title or skill_id

        desc = str(fm.get("description") or fm.get("desc") or "").strip()
        explicit_instructions = str(fm.get("instructions") or "").strip()
        instructions = body if body else (explicit_instructions or desc)
        include_text = _collect_skill_includes(folder, fm)
        if include_text:
            if instructions:
                instructions = f"{instructions}\n\n{include_text}"
            else:
                instructions = include_text
        # For backward compat: if no explicit desc in frontmatter, use body as desc
        if not desc and body:
            desc = body

        keywords = _as_str_list(fm.get("keywords"))

        allowed_roles_raw = fm.get("allowed_roles") or fm.get("allowed-roles")
        allowed_roles_list: List[str] = _as_str_list(allowed_roles_raw)

        ui_raw = _as_dict(fm.get("ui"))
        prompts_list: List[str] = _as_str_list(fm.get("prompts")) or _as_str_list(ui_raw.get("prompts"))
        examples_list: List[str] = _as_str_list(fm.get("examples")) or _as_str_list(ui_raw.get("examples"))

        routing_raw = _as_dict(fm.get("routing"))
        if not routing_raw and keywords:
            routing_raw = {"keywords": keywords}

        agent_raw = _as_dict(fm.get("agent"))
        if not agent_raw:
            # Allow top-level advanced fields for markdown-only skills.
            top_prompt_modules = _as_str_list(fm.get("prompt_modules") or fm.get("promptModules"))
            top_context_providers = _as_str_list(fm.get("context_providers") or fm.get("contextProviders"))
            top_tools = _as_dict(fm.get("tools"))
            top_budgets = _as_dict(fm.get("budgets"))
            top_model_policy = _as_dict(fm.get("model_policy") or fm.get("modelPolicy"))
            if top_prompt_modules:
                agent_raw["prompt_modules"] = top_prompt_modules
            if top_context_providers:
                agent_raw["context_providers"] = top_context_providers
            if top_tools:
                agent_raw["tools"] = top_tools
            if top_budgets:
                agent_raw["budgets"] = top_budgets
            if top_model_policy:
                agent_raw["model_policy"] = top_model_policy

        derived_raw: Dict[str, Any] = {
            "schema_version": fm.get("schema_version") or fm.get("schemaVersion") or 1,
            "title": title,
            "description": desc,
            "instructions": instructions,
            "agent": agent_raw if agent_raw else {
                "prompt_modules": [],
                "context_providers": [],
                "tools": {},
                "budgets": {},
                "model_policy": {},
            },
            "routing": routing_raw,
        }
        if allowed_roles_list:
            derived_raw["allowed_roles"] = allowed_roles_list
        if prompts_list or examples_list:
            derived_raw["ui"] = {}
            if prompts_list:
                derived_raw["ui"]["prompts"] = prompts_list
            if examples_list:
                derived_raw["ui"]["examples"] = examples_list

        try:
            spec = parse_skill_spec(skill_id=skill_id, source_path=str(skill_md_path), raw=derived_raw)
            spec = _ensure_minimal_routing(spec)
            return spec, None
        except Exception as exc:
            _log.debug("operation failed", exc_info=True)
            return None, SkillLoadError(skill_id=skill_id, path=str(skill_md_path), message=f"invalid SKILL.md derived spec: {exc}")

    return None, SkillLoadError(skill_id=skill_id, path=str(spec_path), message="skill.yaml not found")


def load_skills(skills_dir: Path, teacher_skills_dir: Optional[Path] = None) -> LoadedSkills:
    source_dirs = _resolve_source_dirs(skills_dir, teacher_skills_dir=teacher_skills_dir)
    key = "||".join(str(_normalize_path(src)) for src in source_dirs)
    sig = _signature(source_dirs)

    with _CACHE_LOCK:
        cached = _CACHE.get(key)
        if cached and cached[0] == sig:
            return cached[1]
        gen_at_start = _CACHE_GEN

    # Build source markers for source_type tagging.
    teacher_dir_resolved = _normalize_path(teacher_skills_dir) if teacher_skills_dir else None
    primary_dir_resolved = _normalize_path(skills_dir)
    claude_dir_resolved = _normalize_path(Path(os.path.expanduser("~")) / ".claude" / "skills")

    skills: Dict[str, SkillSpec] = {}
    errors: List[SkillLoadError] = []
    found_any_dir = False

    for source_dir in source_dirs:
        if not source_dir.exists() or not source_dir.is_dir():
            continue
        found_any_dir = True
        resolved_source = _normalize_path(source_dir)
        for folder in sorted(source_dir.iterdir(), key=lambda p: p.name):
            if not folder.is_dir():
                continue
            skill_id = folder.name
            spec, err = _load_skill_spec_from_folder(skill_id, folder)
            if err is not None:
                errors.append(err)
                continue
            if spec is not None:
                # Tag source_type based on which directory the skill came from.
                source_type = "system"
                if teacher_dir_resolved and resolved_source == teacher_dir_resolved:
                    source_type = "teacher"
                elif resolved_source == claude_dir_resolved and resolved_source != primary_dir_resolved:
                    source_type = "claude"
                spec = replace(spec, source_type=source_type)
                skills[skill_id] = spec

    if not found_any_dir:
        errors.append(SkillLoadError(skill_id="", path=key, message="skills dir not found"))

    loaded = LoadedSkills(skills=skills, errors=errors)
    with _CACHE_LOCK:
        # Only write if no clear_cache() happened while we were building
        if _CACHE_GEN == gen_at_start:
            _CACHE[key] = (sig, loaded)
    return loaded


def clear_cache() -> None:
    """Clear the skill loader cache. Call after CRUD operations on teacher skills."""
    global _CACHE_GEN
    with _CACHE_LOCK:
        _CACHE.clear()
        _CACHE_GEN += 1
