from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional


@dataclass(frozen=True)
class LessonCaptureDeps:
    is_safe_tool_id: Callable[[Any], bool]
    resolve_app_path: Callable[..., Any]
    app_root: Any
    run_script: Callable[[List[str]], Any]


def _resolve_sources(args: Dict[str, Any], *, deps: LessonCaptureDeps) -> tuple[List[str], Optional[Dict[str, Any]]]:
    sources = args.get("sources")
    if not isinstance(sources, list) or not sources:
        return [], {"error": "sources must be a non-empty array of file paths"}

    resolved_sources: List[str] = []
    for source in sources:
        path = deps.resolve_app_path(source, must_exist=True)
        if not path:
            return [], {"error": "source_not_found_or_outside_app_root", "source": str(source)}
        resolved_sources.append(str(path))
    return resolved_sources, None


def _append_optional_path_arg(
    cmd: List[str],
    args: Dict[str, Any],
    *,
    key: str,
    flag: str,
    error: str,
    must_exist: bool,
    deps: LessonCaptureDeps,
) -> Optional[Dict[str, Any]]:
    value = args.get(key)
    if not value:
        return None
    resolved = deps.resolve_app_path(value, must_exist=must_exist)
    if not resolved:
        return {"error": error}
    cmd += [flag, str(resolved)]
    return None


def _append_optional_value_arg(cmd: List[str], args: Dict[str, Any], *, key: str, flag: str) -> None:
    value = args.get(key)
    if value:
        cmd += [flag, str(value)]


def lesson_capture(args: Dict[str, Any], *, deps: LessonCaptureDeps) -> Dict[str, Any]:
    lesson_id = str(args.get("lesson_id") or "").strip()
    topic = str(args.get("topic") or "").strip()
    if not deps.is_safe_tool_id(lesson_id):
        return {"error": "invalid_lesson_id"}
    if not topic:
        return {"error": "missing_topic"}

    resolved_sources, source_error = _resolve_sources(args, deps=deps)
    if source_error:
        return source_error

    script = deps.app_root / "skills" / "physics-lesson-capture" / "scripts" / "lesson_capture.py"
    cmd = ["python3", str(script), "--lesson-id", lesson_id, "--topic", topic, "--sources", *resolved_sources]

    _append_optional_value_arg(cmd, args, key="class_name", flag="--class-name")
    for path_key, flag, error, must_exist in (
        ("discussion_notes", "--discussion-notes", "discussion_notes_not_found_or_outside_app_root", True),
        ("lesson_plan", "--lesson-plan", "lesson_plan_not_found_or_outside_app_root", True),
        ("out_base", "--out-base", "out_base_outside_app_root", False),
    ):
        path_error = _append_optional_path_arg(
            cmd,
            args,
            key=path_key,
            flag=flag,
            error=error,
            must_exist=must_exist,
            deps=deps,
        )
        if path_error:
            return path_error
    if args.get("force_ocr"):
        cmd += ["--force-ocr"]
    _append_optional_value_arg(cmd, args, key="ocr_mode", flag="--ocr-mode")
    _append_optional_value_arg(cmd, args, key="language", flag="--language")

    output = deps.run_script(cmd)
    return {"ok": True, "output": output, "lesson_id": lesson_id}
