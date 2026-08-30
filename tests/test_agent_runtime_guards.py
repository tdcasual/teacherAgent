from pathlib import Path

from services.api.agent_runtime_guards import maybe_guard_teacher_subject_total
from services.api.agent_service import AgentRuntimeDeps


def test_maybe_guard_teacher_subject_total_is_noop():
    logs = []
    deps = AgentRuntimeDeps(
        app_root=Path("."),
        build_system_prompt=lambda role: f"system-{role or 'unknown'}",
        diag_log=lambda event, payload=None: logs.append((event, payload or {})),
        load_skill_runtime=lambda role, skill_id: (None, None),
        allowed_tools=lambda role: set(),
        max_tool_rounds=3,
        max_tool_calls=5,
        extract_min_chars_requirement=lambda text: None,
        generate_longform_reply=lambda *args, **kwargs: "",
        call_llm=lambda *args, **kwargs: {"choices": [{"message": {"content": ""}}]},
        tool_dispatch=lambda name, args, role, skill_id=None, teacher_id=None: {"ok": True},
        teacher_tools_to_openai=lambda allowed, skill_runtime=None: [],
    )

    result = maybe_guard_teacher_subject_total(
        deps,
        messages=[{"role": "user", "content": "分析EX20260209_9b92e1的物理成绩"}],
        last_user_text="分析EX20260209_9b92e1的物理成绩",
    )

    assert result is None
    assert logs == []
