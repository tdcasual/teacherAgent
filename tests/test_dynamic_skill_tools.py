from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from services.api.dynamic_skill_tools import (
    clear_dynamic_tools_cache,
    compile_skill_dynamic_tools,
    dispatch_dynamic_tool,
    load_dynamic_tools_for_skill_source,
)
from services.api.tool_dispatch_service import ToolDispatchDeps, tool_dispatch


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_compile_and_hot_load_dynamic_tools(tmp_path: Path) -> None:
    teacher_root = tmp_path / "teacher_skills"
    skill_dir = teacher_root / "dyn-skill"
    _write(skill_dir / "SKILL.md", "---\ntitle: Dyn\n---\nbody\n")
    _write(
        skill_dir / "scripts" / "quiz.py",
        "import json\nprint(json.dumps({'ok': True, 'data': {'msg': 'ok'}}))\n",
    )
    _write(
        skill_dir / "tool-manifest.yaml",
        "\n".join(
            [
                "version: 1",
                "runtime:",
                "  default_timeout_sec: 15",
                "tools:",
                "  - name: teacher.quiz.generate",
                "    description: gen",
                "    input_schema:",
                "      type: object",
                "      properties:",
                "        topic: { type: string }",
                "      required: [topic]",
                "      additionalProperties: false",
                "    executor:",
                "      type: script",
                "      entry: scripts/quiz.py",
            ]
        )
        + "\n",
    )

    report = compile_skill_dynamic_tools(skill_dir)
    assert report["compiled_ok"] == 1
    assert (skill_dir / "dynamic_tools.json").exists()
    assert (skill_dir / "dynamic_tools.lock.json").exists()
    assert (skill_dir / "dynamic_tools.report.json").exists()

    loaded = load_dynamic_tools_for_skill_source(str(skill_dir / "SKILL.md"))
    assert "teacher.quiz.generate" in loaded
    clear_dynamic_tools_cache(skill_dir)


def test_dispatch_dynamic_script_retry_and_degrade(tmp_path: Path) -> None:
    teacher_root = tmp_path / "teacher_skills"
    skill_dir = teacher_root / "dyn-retry"
    _write(skill_dir / "SKILL.md", "---\ntitle: Dyn\n---\nbody\n")
    _write(
        skill_dir / "scripts" / "ok.py",
        "\n".join(
            [
                "import json,sys",
                "topic = ''",
                "if '--topic' in sys.argv:",
                "    idx = sys.argv.index('--topic')",
                "    topic = sys.argv[idx+1] if idx + 1 < len(sys.argv) else ''",
                "print(json.dumps({'ok': True, 'data': {'topic': topic}}))",
            ]
        )
        + "\n",
    )
    _write(skill_dir / "scripts" / "bad.py", "import sys\nprint('boom')\nsys.exit(2)\n")
    _write(
        skill_dir / "tool-manifest.yaml",
        "\n".join(
            [
                "tools:",
                "  - name: teacher.ok.tool",
                "    input_schema:",
                "      type: object",
                "      properties: { topic: { type: string } }",
                "      required: [topic]",
                "    executor:",
                "      type: script",
                "      entry: scripts/ok.py",
                "      args_template: ['--topic', '{{args.topic}}']",
                "      retry: { max_attempts: 2, backoff_ms: 0 }",
                "  - name: teacher.bad.tool",
                "    input_schema: { type: object, properties: {}, additionalProperties: false }",
                "    executor:",
                "      type: script",
                "      entry: scripts/bad.py",
                "      retry: { max_attempts: 2, backoff_ms: 0 }",
            ]
        )
        + "\n",
    )

    ok_result = dispatch_dynamic_tool(
        name="teacher.ok.tool",
        args={"topic": "电学"},
        role="teacher",
        skill_id="dyn-retry",
        teacher_id="t1",
        teacher_skills_dir=teacher_root,
    )
    assert isinstance(ok_result, dict)
    assert ok_result.get("ok") is True
    assert ((ok_result.get("data") or {}).get("topic")) == "电学"

    bad_result = dispatch_dynamic_tool(
        name="teacher.bad.tool",
        args={},
        role="teacher",
        skill_id="dyn-retry",
        teacher_id="t1",
        teacher_skills_dir=teacher_root,
    )
    assert isinstance(bad_result, dict)
    assert bad_result.get("error") == "dynamic_tool_failed_after_retries"
    assert bad_result.get("_dynamic_tool_degraded") is True


def test_dispatch_dynamic_http_and_tool_dispatch_bridge(tmp_path: Path) -> None:
    teacher_root = tmp_path / "teacher_skills"
    skill_dir = teacher_root / "dyn-http"
    _write(skill_dir / "SKILL.md", "---\ntitle: Dyn\n---\nbody\n")
    _write(
        skill_dir / "tool-manifest.yaml",
        "\n".join(
            [
                "tools:",
                "  - name: teacher.http.search",
                "    input_schema:",
                "      type: object",
                "      properties: { q: { type: string } }",
                "      required: [q]",
                "      additionalProperties: false",
                "    executor:",
                "      type: http",
                "      method: POST",
                "      url: https://example.test/api/search",
                "      body_template:",
                "        query: '{{args.q}}'",
                "      retry: { max_attempts: 1, backoff_ms: 0 }",
            ]
        )
        + "\n",
    )

    class _FakeResp:
        status = 200
        headers = {"Content-Type": "application/json"}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self, _amt: int = -1):
            return json.dumps({"ok": True, "items": [1, 2]}).encode("utf-8")

    with patch("urllib.request.urlopen", return_value=_FakeResp()):
        result = dispatch_dynamic_tool(
            name="teacher.http.search",
            args={"q": "motion"},
            role="teacher",
            skill_id="dyn-http",
            teacher_id="t1",
            teacher_skills_dir=teacher_root,
        )
    assert isinstance(result, dict)
    assert result.get("ok") is True
    assert ((result.get("data") or {}).get("ok")) is True

    class _Registry:
        def get(self, _name: str):
            return None

        def validate_arguments(self, _name: str, _args: dict):
            return []

    deps = ToolDispatchDeps(
        tool_registry=_Registry(),
        list_exams=lambda: {},
        exam_get=lambda _x: {},
        exam_analysis_get=lambda _x: {},
        exam_analysis_charts_generate=lambda _x: {},
        exam_students_list=lambda _x, _y: {},
        exam_student_detail=lambda *_args, **_kwargs: {},
        exam_question_detail=lambda *_args, **_kwargs: {},
        exam_range_top_students=lambda *_args, **_kwargs: {},
        exam_range_summary_batch=lambda *_args, **_kwargs: {},
        exam_question_batch_detail=lambda *_args, **_kwargs: {},
        list_assignments=lambda: {},
        list_lessons=lambda: {},
        lesson_capture=lambda _x: {},
        student_search=lambda _x, _y: {},
        student_profile_get=lambda _x: {},
        student_profile_update=lambda _x: {},
        student_import=lambda _x: {},
        assignment_generate=lambda _x: {},
        assignment_render=lambda _x: {},
        save_assignment_requirements=lambda *_args, **_kwargs: {},
        parse_date_str=lambda _x: None,
        core_example_search=lambda _x: {},
        core_example_register=lambda _x: {},
        core_example_render=lambda _x: {},
        chart_agent_run=lambda _x: {},
        chart_exec=lambda _x: {},
        resolve_teacher_id=lambda _x: "teacher",
        ensure_teacher_workspace=lambda _x: Path("/tmp"),
        teacher_workspace_dir=lambda _x: Path("/tmp"),
        teacher_workspace_file=lambda _x, _y: Path("/tmp/a.md"),
        teacher_daily_memory_path=lambda _x, _y=None: Path("/tmp/daily.md"),
        teacher_read_text=lambda _x, max_chars=8000: "",
        teacher_memory_search=lambda _x, _y, _z=5: {},
        teacher_memory_propose=lambda *_args, **_kwargs: {},
        teacher_memory_apply=lambda *_args, **_kwargs: {},
        teacher_llm_routing_get=lambda _x: {},
        teacher_llm_routing_simulate=lambda _x: {},
        teacher_llm_routing_propose=lambda _x: {},
        teacher_llm_routing_apply=lambda _x: {},
        teacher_llm_routing_rollback=lambda _x: {},
        dynamic_tool_dispatch=lambda **kwargs: {"ok": True, "name": kwargs.get("name")},
    )
    out = tool_dispatch(
        "teacher.http.search",
        {"q": "a"},
        role="teacher",
        deps=deps,
        skill_id="dyn-http",
        teacher_id="t1",
    )
    assert out.get("ok") is True
