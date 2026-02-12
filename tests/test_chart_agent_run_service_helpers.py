from __future__ import annotations

from typing import Any, Dict, List

from services.api.chart_agent_run_service import (
    ChartAgentRunDeps,
    _int_or_none,
    chart_agent_bool,
    chart_agent_default_code,
    chart_agent_engine,
    chart_agent_extract_python_code,
    chart_agent_generate_candidate,
    chart_agent_generate_candidate_opencode,
    chart_agent_opencode_overrides,
    chart_agent_packages,
    chart_agent_run,
)


def _base_deps(
    *,
    generate_candidate_fn,
    execute_chart_exec_fn,
    default_code: str = "print('default-code')",
) -> ChartAgentRunDeps:
    return ChartAgentRunDeps(
        safe_int_arg=lambda value, default, minimum, maximum: max(
            minimum, min(maximum, int(default if value is None else value))
        ),
        chart_bool=chart_agent_bool,
        chart_engine=chart_agent_engine,
        chart_packages=chart_agent_packages,
        chart_opencode_overrides=chart_agent_opencode_overrides,
        resolve_opencode_status=lambda app_root, overrides=None: {"enabled": False, "available": False},
        app_root="/tmp/app",
        uploads_dir="/tmp/uploads",
        generate_candidate=generate_candidate_fn,
        generate_candidate_opencode=lambda task, input_data, last_error, previous_code, attempt, max_retries, opencode_overrides: {},
        execute_chart_exec=execute_chart_exec_fn,
        default_code=lambda: default_code,
    )


def test_int_or_none_and_boolean_engine_helpers() -> None:
    assert _int_or_none(None) is None
    assert _int_or_none("12") == 12
    assert _int_or_none("bad") is None

    assert chart_agent_bool(True, False) is True
    assert chart_agent_bool(None, False) is False
    assert chart_agent_bool("YES") is True
    assert chart_agent_bool("  ", True) is True
    assert chart_agent_bool(0, True) is False
    assert chart_agent_engine("opencode") == "opencode"
    assert chart_agent_engine("auto") == "auto"
    assert chart_agent_engine("custom-engine") == "llm"


def test_opencode_overrides_and_package_normalization() -> None:
    args = {
        "opencode_model": "gpt-x",
        "opencode_profile": "teacher",
        "opencode_mode": "safe",
        "opencode_timeout_sec": "2",
        "opencode_enabled": "true",
        "opencode_max_retries": "99",
    }
    overrides = chart_agent_opencode_overrides(args)
    assert overrides["model"] == "gpt-x"
    assert overrides["profile"] == "teacher"
    assert overrides["mode"] == "safe"
    assert overrides["timeout_sec"] == 10
    assert overrides["enabled"] is True
    assert overrides["max_retries"] == 6
    assert chart_agent_opencode_overrides([]) == {}
    assert chart_agent_packages("numpy, pandas;numpy") == ["numpy", "pandas"]
    assert chart_agent_packages("numpy,, pandas") == ["numpy", "pandas"]
    assert chart_agent_packages(["Numpy", "numpy", "scipy"]) == ["Numpy", "scipy"]
    assert chart_agent_packages(123) == []


def test_extract_python_code_from_fence_or_plain_text() -> None:
    fenced = "before\n```python\nprint('hello')\n```\nafter"
    plain = "print('hello')\n"
    assert chart_agent_extract_python_code(fenced) == "print('hello')"
    assert chart_agent_extract_python_code(plain) == "print('hello')"
    assert "save_chart()" in chart_agent_default_code()


def test_generate_candidate_handles_llm_failure() -> None:
    def _call_llm(_messages, **_kwargs):
        raise RuntimeError("llm down")

    result = chart_agent_generate_candidate(
        task="画图",
        input_data={"x": 1},
        last_error="",
        previous_code="",
        attempt=1,
        max_retries=3,
        call_llm=_call_llm,
        parse_json_from_text=lambda text: {},
    )
    assert result["python_code"] == ""
    assert result["packages"] == []
    assert "llm_error:" in result["raw"]


def test_generate_candidate_truncates_payload_and_falls_back_to_code_extraction() -> None:
    captured: Dict[str, Any] = {}

    def _call_llm(messages, **_kwargs):
        captured["messages"] = messages
        return {"choices": [{"message": {"content": "```python\nprint('from-fence')\n```"}}]}

    result = chart_agent_generate_candidate(
        task="画图",
        input_data={"blob": "x" * 6001},
        last_error="",
        previous_code="",
        attempt=2,
        max_retries=3,
        call_llm=_call_llm,
        parse_json_from_text=lambda text: {},
    )
    user_prompt = captured["messages"][1]["content"]
    assert "...[truncated]" in user_prompt
    assert result["python_code"] == "print('from-fence')"
    assert result["packages"] == []


def test_generate_candidate_handles_unserializable_input_data() -> None:
    class NotJsonSerializable:
        def __str__(self) -> str:
            return "custom-object"

    captured: Dict[str, Any] = {}

    def _call_llm(messages, **_kwargs):
        captured["messages"] = messages
        return {"choices": [{"message": {"content": '{"python_code":"print(1)","packages":[],"summary":"ok"}'}}]}

    result = chart_agent_generate_candidate(
        task="画图",
        input_data=NotJsonSerializable(),
        last_error="",
        previous_code="",
        attempt=1,
        max_retries=2,
        call_llm=_call_llm,
        parse_json_from_text=lambda text: {"python_code": "print(1)", "packages": [], "summary": "ok"},
    )
    assert result["python_code"] == "print(1)"
    assert "custom-object" in captured["messages"][1]["content"]


def test_generate_candidate_opencode_maps_meta_fields() -> None:
    result = chart_agent_generate_candidate_opencode(
        task="画图",
        input_data={"a": 1},
        last_error="boom",
        previous_code="print(1)",
        attempt=1,
        max_retries=2,
        opencode_overrides={"model": "abc"},
        app_root="/tmp/app",
        run_opencode_codegen=lambda **kwargs: {
            "python_code": "print('ok')",
            "packages": "numpy,numpy",
            "summary": "done",
            "raw": "raw-text",
            "ok": True,
            "exit_code": 0,
            "duration_sec": 1.23,
            "stderr": "x" * 900,
            "command": ["opencode", "run"],
            "error": None,
        },
    )
    assert result["python_code"] == "print('ok')"
    assert result["packages"] == ["numpy"]
    assert result["summary"] == "done"
    assert result["meta"]["ok"] is True
    assert result["meta"]["exit_code"] == 0
    assert len(result["meta"]["stderr"]) == 800


def test_chart_agent_run_uses_default_code_and_returns_failure_after_retries() -> None:
    seen_exec_args: List[Dict[str, Any]] = []

    def _generate_candidate(task, input_data, last_error, previous_code, attempt, max_retries):
        return {
            "python_code": "",
            "packages": ["numpy"],
            "summary": f"attempt-{attempt}",
        }

    def _execute_chart_exec(args, app_root, uploads_dir):
        seen_exec_args.append(args)
        return {"ok": False, "run_id": "run-fail", "stderr": f"exec failed: {len(seen_exec_args)}"}

    deps = _base_deps(generate_candidate_fn=_generate_candidate, execute_chart_exec_fn=_execute_chart_exec)
    result = chart_agent_run(
        {
            "task": "测试失败路径",
            "packages": ["NumPy", "scipy"],
            "max_retries": 2,
            "save_as": "",
        },
        deps=deps,
    )
    assert result["ok"] is False
    assert result["error"] == "chart_agent_failed"
    assert result["max_retries"] == 2
    assert len(result["attempts"]) == 2
    assert result["attempts"][0]["code_preview"].startswith("print('default-code')")
    assert seen_exec_args[0]["save_as"] == "main.png"
    assert seen_exec_args[0]["packages"] == ["NumPy", "scipy"]
