from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

APP_ROOT = Path(__file__).resolve().parents[2]
PROMPTS_DIR = Path(os.getenv("PROMPTS_DIR", APP_ROOT / "prompts"))
DEFAULT_PROMPT_VERSION = os.getenv("PROMPT_VERSION", "v1")
PROMPT_DEBUG = os.getenv("PROMPT_DEBUG", "").lower() in {"1", "true", "yes", "on"}


def resolve_role_key(role_hint: Optional[str]) -> str:
    if role_hint == "teacher":
        return "teacher"
    if role_hint == "student":
        return "student"
    return "unknown"


@lru_cache(maxsize=32)
def load_manifest(version: str) -> Dict[str, List[str]]:
    manifest_path = (PROMPTS_DIR / version / "manifest.json").resolve()
    if not manifest_path.exists():
        raise FileNotFoundError(f"prompt manifest not found: {manifest_path}")
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("prompt manifest must be a JSON object")
    manifest: Dict[str, List[str]] = {}
    for key, value in raw.items():
        if not isinstance(key, str):
            continue
        if not isinstance(value, list):
            continue
        manifest[key] = [str(item) for item in value]
    return manifest


def _read_module(version: str, relpath: str) -> str:
    base = (PROMPTS_DIR / version).resolve()
    target = (base / relpath).resolve()
    # Prevent path traversal.
    if base not in target.parents and target != base:
        raise ValueError(f"invalid prompt module path: {relpath}")
    if not target.exists():
        raise FileNotFoundError(f"prompt module not found: {target}")
    return target.read_text(encoding="utf-8").strip()


@lru_cache(maxsize=64)
def compile_system_prompt(
    role_hint: Optional[str],
    version: Optional[str] = None,
    debug: Optional[bool] = None,
) -> Tuple[str, List[str]]:
    version_final = version or DEFAULT_PROMPT_VERSION
    debug_final = PROMPT_DEBUG if debug is None else debug
    manifest = load_manifest(version_final)
    role_key = resolve_role_key(role_hint)
    modules = manifest.get(role_key) or manifest.get("unknown") or []
    if not modules:
        raise ValueError(f"no prompt modules configured for role={role_key} in version={version_final}")

    used: List[str] = []
    parts: List[str] = []
    for rel in modules:
        content = _read_module(version_final, rel)
        if not content:
            continue
        used.append(rel)
        if debug_final:
            parts.append(f"【MODULE: {rel}】\n{content}")
        else:
            parts.append(content)

    prompt = "\n\n".join(parts).strip()
    if prompt:
        prompt += "\n"
    return prompt, used

