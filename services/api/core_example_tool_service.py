from __future__ import annotations

import csv
from dataclasses import dataclass
from typing import Any, Callable, Dict


@dataclass(frozen=True)
class CoreExampleToolDeps:
    data_dir: Any
    app_root: Any
    is_safe_tool_id: Callable[[Any], bool]
    resolve_app_path: Callable[[Any, bool], Any]
    run_script: Callable[[list[str]], Any]


def core_example_search(args: Dict[str, Any], *, deps: CoreExampleToolDeps) -> Dict[str, Any]:
    csv_path = deps.data_dir / "core_examples" / "examples.csv"
    if not csv_path.exists():
        return {"ok": True, "examples": []}
    kp_id = str(args.get("kp_id") or "").strip()
    example_id = str(args.get("example_id") or "").strip()
    results = []
    with csv_path.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if kp_id and row.get("kp_id") != kp_id:
                continue
            if example_id and row.get("example_id") != example_id:
                continue
            results.append(row)
    return {"ok": True, "examples": results}


def core_example_register(args: Dict[str, Any], *, deps: CoreExampleToolDeps) -> Dict[str, Any]:
    example_id = str(args.get("example_id") or "").strip()
    kp_id = str(args.get("kp_id") or "").strip()
    core_model = str(args.get("core_model") or "").strip()
    if not deps.is_safe_tool_id(example_id):
        return {"error": "invalid_example_id"}
    if not deps.is_safe_tool_id(kp_id):
        return {"error": "invalid_kp_id"}
    if not core_model:
        return {"error": "missing_core_model"}

    script = deps.app_root / "skills" / "physics-core-examples" / "scripts" / "register_core_example.py"
    cmd = ["python3", str(script), "--example-id", example_id, "--kp-id", kp_id, "--core-model", core_model]

    for key in (
        "difficulty",
        "source_ref",
        "tags",
        "from_lesson",
        "lesson_example_id",
        "lesson_figure",
    ):
        if args.get(key):
            cmd += [f"--{key.replace('_', '-')}", str(args.get(key))]

    for key in (
        "stem_file",
        "solution_file",
        "model_file",
        "figure_file",
        "discussion_file",
        "variant_file",
    ):
        if not args.get(key):
            continue
        path = deps.resolve_app_path(args.get(key), must_exist=True)
        if not path:
            return {"error": f"{key}_not_found_or_outside_app_root"}
        cmd += [f"--{key.replace('_', '-')}", str(path)]

    output = deps.run_script(cmd)
    return {"ok": True, "output": output, "example_id": example_id}


def core_example_render(args: Dict[str, Any], *, deps: CoreExampleToolDeps) -> Dict[str, Any]:
    example_id = str(args.get("example_id") or "").strip()
    if not deps.is_safe_tool_id(example_id):
        return {"error": "invalid_example_id"}
    script = deps.app_root / "skills" / "physics-core-examples" / "scripts" / "render_core_example_pdf.py"
    cmd = ["python3", str(script), "--example-id", example_id]
    if args.get("out"):
        path = deps.resolve_app_path(args.get("out"), must_exist=False)
        if not path:
            return {"error": "out_outside_app_root"}
        cmd += ["--out", str(path)]
    output = deps.run_script(cmd)
    return {"ok": True, "output": output, "example_id": example_id}
