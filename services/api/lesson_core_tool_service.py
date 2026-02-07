from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List


@dataclass(frozen=True)
class LessonCaptureDeps:
    is_safe_tool_id: Callable[[Any], bool]
    resolve_app_path: Callable[[Any, bool], Any]
    app_root: Any
    run_script: Callable[[List[str]], Any]


def lesson_capture(args: Dict[str, Any], *, deps: LessonCaptureDeps) -> Dict[str, Any]:
    lesson_id = str(args.get("lesson_id") or "").strip()
    topic = str(args.get("topic") or "").strip()
    if not deps.is_safe_tool_id(lesson_id):
        return {"error": "invalid_lesson_id"}
    if not topic:
        return {"error": "missing_topic"}

    sources = args.get("sources")
    if not isinstance(sources, list) or not sources:
        return {"error": "sources must be a non-empty array of file paths"}

    resolved_sources: List[str] = []
    for source in sources:
        path = deps.resolve_app_path(source, must_exist=True)
        if not path:
            return {"error": "source_not_found_or_outside_app_root", "source": str(source)}
        resolved_sources.append(str(path))

    script = deps.app_root / "skills" / "physics-lesson-capture" / "scripts" / "lesson_capture.py"
    cmd = ["python3", str(script), "--lesson-id", lesson_id, "--topic", topic, "--sources", *resolved_sources]

    if args.get("class_name"):
        cmd += ["--class-name", str(args.get("class_name"))]
    if args.get("discussion_notes"):
        discussion_notes = deps.resolve_app_path(args.get("discussion_notes"), must_exist=True)
        if not discussion_notes:
            return {"error": "discussion_notes_not_found_or_outside_app_root"}
        cmd += ["--discussion-notes", str(discussion_notes)]
    if args.get("lesson_plan"):
        lesson_plan = deps.resolve_app_path(args.get("lesson_plan"), must_exist=True)
        if not lesson_plan:
            return {"error": "lesson_plan_not_found_or_outside_app_root"}
        cmd += ["--lesson-plan", str(lesson_plan)]
    if args.get("force_ocr"):
        cmd += ["--force-ocr"]
    if args.get("ocr_mode"):
        cmd += ["--ocr-mode", str(args.get("ocr_mode"))]
    if args.get("language"):
        cmd += ["--language", str(args.get("language"))]
    if args.get("out_base"):
        out_base = deps.resolve_app_path(args.get("out_base"), must_exist=False)
        if not out_base:
            return {"error": "out_base_outside_app_root"}
        cmd += ["--out-base", str(out_base)]

    output = deps.run_script(cmd)
    return {"ok": True, "output": output, "lesson_id": lesson_id}
