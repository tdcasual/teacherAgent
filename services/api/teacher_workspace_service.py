from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class TeacherWorkspaceDeps:
    teacher_workspace_dir: Callable[[str], Path]
    teacher_daily_memory_dir: Callable[[str], Path]


def ensure_teacher_workspace(teacher_id: str, *, deps: TeacherWorkspaceDeps) -> Path:
    base = deps.teacher_workspace_dir(teacher_id)
    base.mkdir(parents=True, exist_ok=True)
    deps.teacher_daily_memory_dir(teacher_id).mkdir(parents=True, exist_ok=True)
    proposals = base / "proposals"
    proposals.mkdir(parents=True, exist_ok=True)

    defaults: Dict[str, str] = {
        "AGENTS.md": (
            "# Teacher Agent Workspace Rules\n"
            "\n"
            "This workspace stores long-term preferences and work logs for the teacher assistant.\n"
            "\n"
            "## Memory Policy\n"
            "- Only write stable preferences/constraints to MEMORY.md after explicit teacher confirmation.\n"
            "- Write daily notes to memory/YYYY-MM-DD.md freely (short, factual).\n"
            "- Never store secrets (API keys, passwords, tokens).\n"
        ),
        "SOUL.md": (
            "# Persona\n"
            "- Be proactive but not pushy.\n"
            "- Prefer checklists and concrete next actions.\n"
            "- When unsure about a preference, ask.\n"
        ),
        "USER.md": (
            "# Teacher Profile\n"
            "- name: (unknown)\n"
            "- school/class: (unknown)\n"
            "- preferences:\n"
            "  - output_style: concise\n"
            "  - default_language: zh\n"
        ),
        "MEMORY.md": (
            "# Long-Term Memory (Curated)\n"
            "\n"
            "Keep this file short and high-signal.\n"
            "\n"
            "## Confirmed Preferences\n"
            "- (none)\n"
        ),
        "HEARTBEAT.md": (
            "# Heartbeat Checklist\n"
            "- [ ] Review low-confidence OCR grading items\n"
            "- [ ] Check students with repeated weak KP\n"
            "- [ ] Prepare tomorrow's pre-class checklist\n"
        ),
    }

    for name, content in defaults.items():
        path = base / name
        if not path.exists():
            path.write_text(content, encoding="utf-8")

    return base


def teacher_read_text(path: Path, max_chars: int = 8000) -> str:
    if not path.exists():
        return ""
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        _log.warning("failed to read teacher file %s", path, exc_info=True)
        return ""
    if max_chars and len(text) > max_chars:
        return text[:max_chars] + "…"
    return text
