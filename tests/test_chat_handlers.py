import pytest
from fastapi import HTTPException

from services.api.api_models import ChatMessage, ChatRequest, ChatStartRequest
from services.api.handlers import chat_handlers


def _build_deps(**overrides):
    async def run_in_threadpool(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    def compute_chat_reply_sync(_req):
        return ("ok", "student", "last-user")

    def detect_math_delimiters(_text):
        return False

    def detect_latex_tokens(_text):
        return False

    def diag_log(_event, _payload):
        pass

    def build_interaction_note(_last_user, _reply, assignment_id=None):
        return "note"

    def enqueue_profile_update(_payload):
        pass

    def student_profile_update(_payload):
        return {"ok": True}

    def get_chat_status(_job_id):
        return {"status": "ok"}

    async def start_chat_api(_req):
        return {"ok": True}

    deps = chat_handlers.ChatHandlerDeps(
        compute_chat_reply_sync=compute_chat_reply_sync,
        detect_math_delimiters=detect_math_delimiters,
        detect_latex_tokens=detect_latex_tokens,
        diag_log=diag_log,
        build_interaction_note=build_interaction_note,
        enqueue_profile_update=enqueue_profile_update,
        student_profile_update=student_profile_update,
        profile_update_async=True,
        run_in_threadpool=run_in_threadpool,
        get_chat_status=get_chat_status,
        start_chat_api=start_chat_api,
    )
    for key, value in overrides.items():
        setattr(deps, key, value)
    return deps


@pytest.mark.anyio
async def test_chat_status_not_found():
    def get_chat_status(_job_id):
        raise FileNotFoundError("missing")

    deps = _build_deps(get_chat_status=get_chat_status)

    with pytest.raises(HTTPException) as exc:
        await chat_handlers.chat_status("job-1", deps=deps)

    assert exc.value.status_code == 404


@pytest.mark.anyio
async def test_chat_student_profile_update_async():
    calls = {"enqueue": None, "profile": 0}

    def enqueue_profile_update(payload):
        calls["enqueue"] = payload

    def student_profile_update(_payload):
        calls["profile"] += 1
        return {"ok": True}

    deps = _build_deps(
        enqueue_profile_update=enqueue_profile_update,
        student_profile_update=student_profile_update,
        profile_update_async=True,
    )

    req = ChatRequest(
        messages=[ChatMessage(role="user", content="hi")],
        student_id="s1",
        assignment_id="a1",
    )

    result = await chat_handlers.chat(req, deps=deps)

    assert result.reply == "ok"
    assert calls["enqueue"] == {"student_id": "s1", "interaction_note": "note"}
    assert calls["profile"] == 0


@pytest.mark.anyio
async def test_chat_start_awaits_async_impl():
    deps = _build_deps()
    req = ChatStartRequest(
        request_id="r1",
        messages=[ChatMessage(role="user", content="hi")],
    )

    result = await chat_handlers.chat_start(req, deps=deps)
    assert result == {"ok": True}
