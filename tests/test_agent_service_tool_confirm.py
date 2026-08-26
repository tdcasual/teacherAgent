from __future__ import annotations

from pathlib import Path

from services.api.agent_service import AgentRuntimeDeps, run_agent_runtime


def _deps(tool_dispatch, call_llm):
    return AgentRuntimeDeps(
        app_root=Path("."),
        build_system_prompt=lambda role: f"system-{role or 'unknown'}",
        diag_log=lambda *_args, **_kwargs: None,
        load_skill_runtime=lambda role, skill_id: (None, None),
        allowed_tools=lambda role: {"student.profile.update", "exam.get"},
        max_tool_rounds=3,
        max_tool_calls=5,
        extract_min_chars_requirement=lambda text: None,
        extract_exam_id=lambda text: None,
        is_exam_analysis_request=lambda text: False,
        build_exam_longform_context=lambda exam_id: {},
        generate_longform_reply=lambda *args, **kwargs: "",
        call_llm=call_llm,
        tool_dispatch=tool_dispatch,
        teacher_tools_to_openai=lambda allowed, skill_runtime=None: [],
    )


def test_run_agent_runtime_pauses_without_appending_sentinel() -> None:
    dispatches: list[str] = []

    def fake_dispatch(name, args, role, skill_id=None, teacher_id=None):
        dispatches.append(name)
        return {
            "error": "confirmation_required",
            "confirm_id": "abc123",
            "tool": name,
            "preview": f"{name}: {args}",
            "exp": 9,
        }

    def fake_call_llm(messages, **kwargs):
        return {
            "choices": [
                {
                    "message": {
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "call-1",
                                "function": {
                                    "name": "student.profile.update",
                                    "arguments": '{"student_id":"S1"}',
                                },
                            },
                            {
                                "id": "call-2",
                                "function": {"name": "exam.get", "arguments": '{"exam_id":"E1"}'},
                            },
                        ],
                    }
                }
            ]
        }

    result = run_agent_runtime(
        [{"role": "user", "content": "更新画像"}],
        "teacher",
        deps=_deps(fake_dispatch, fake_call_llm),
        job_id="job-1",
        lane_id="lane-1",
        actor_id="teacher-1",
    )
    assert result.get("pause") == "confirmation_required"
    assert result.get("confirm_id") == "abc123"
    assert result.get("tool_call_id") == "call-1"
    assert "reply" not in result
    convo = result.get("convo") or []
    tool_messages = [item for item in convo if item.get("role") == "tool"]
    assert all("confirmation_required" not in str(item.get("content") or "") for item in tool_messages)
    sibling = [item for item in tool_messages if item.get("tool_call_id") == "call-2"]
    assert sibling
    assert "paused_for_sibling_confirm" in str(sibling[0].get("content") or "")
    assert dispatches == ["student.profile.update"]


def test_run_agent_runtime_resume_from_initial_convo_does_not_rebuild() -> None:
    llm_calls: list[int] = []

    def fake_call_llm(messages, **kwargs):
        llm_calls.append(len(messages))
        return {"choices": [{"message": {"content": "resumed reply"}}]}

    initial = [
        {"role": "system", "content": "keep-me"},
        {"role": "assistant", "tool_calls": [{"id": "call-1", "function": {"name": "student.profile.update"}}]},
        {"role": "tool", "tool_call_id": "call-1", "content": "{\"ok\": true}"},
    ]
    result = run_agent_runtime(
        [{"role": "user", "content": "ignored rebuild"}],
        "teacher",
        deps=_deps(lambda *a, **k: {"ok": True}, fake_call_llm),
        initial_convo=initial,
    )
    assert result.get("reply") == "resumed reply"
    assert llm_calls == [3]
