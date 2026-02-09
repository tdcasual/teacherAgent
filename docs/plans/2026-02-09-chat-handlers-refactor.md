# Chat Handlers Extraction Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move chat HTTP handlers and closely related logic into `handlers/chat_handlers.py` while keeping `app_core.py` focused on dependency wiring.

**Architecture:** Introduce a `ChatHandlerDeps` dataclass that carries the specific callables and flags used by chat handlers. `app_core` builds deps and delegates `chat`, `chat_start`, and `chat_status` to the handlers module, preserving route names.

**Tech Stack:** Python 3.11, FastAPI, pytest (anyio)

---

### Task 1: Add chat handlers module + tests

**Files:**
- Create: `/Users/lvxiaoer/Documents/New project/services/api/handlers/__init__.py`
- Create: `/Users/lvxiaoer/Documents/New project/services/api/handlers/chat_handlers.py`
- Create: `/Users/lvxiaoer/Documents/New project/tests/test_chat_handlers.py`

**Step 1: Write the failing test**

Create `/Users/lvxiaoer/Documents/New project/tests/test_chat_handlers.py`:

```python
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
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_chat_handlers.py -v`
Expected: FAIL (module/function missing)

**Step 3: Implement chat handlers**

Create `/Users/lvxiaoer/Documents/New project/services/api/handlers/chat_handlers.py`:

```python
from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Callable, Optional, Tuple

from fastapi import HTTPException

from ..api_models import ChatRequest, ChatResponse, ChatStartRequest


@dataclass
class ChatHandlerDeps:
    compute_chat_reply_sync: Callable[[ChatRequest], Tuple[str, Optional[str], str]]
    detect_math_delimiters: Callable[[str], bool]
    detect_latex_tokens: Callable[[str], bool]
    diag_log: Callable[[str, dict], None]
    build_interaction_note: Callable[[str, str, Optional[str]], str]
    enqueue_profile_update: Callable[[dict], None]
    student_profile_update: Callable[[dict], dict]
    profile_update_async: bool
    run_in_threadpool: Callable[..., Any]
    get_chat_status: Callable[[str], Any]
    start_chat_api: Callable[[ChatStartRequest], Any]


def _is_awaitable(value: Any) -> bool:
    return inspect.isawaitable(value)


async def chat(req: ChatRequest, *, deps: ChatHandlerDeps) -> ChatResponse:
    reply_text, role_hint, last_user_text = await deps.run_in_threadpool(deps.compute_chat_reply_sync, req)
    if role_hint == "student" and req.student_id and reply_text != "正在生成上一条回复，请稍候再试。":
        try:
            has_math = deps.detect_math_delimiters(reply_text)
            has_latex = deps.detect_latex_tokens(reply_text)
            deps.diag_log(
                "student_chat.out",
                {
                    "student_id": req.student_id,
                    "assignment_id": req.assignment_id,
                    "has_math_delim": has_math,
                    "has_latex_tokens": has_latex,
                    "reply_preview": reply_text[:500],
                },
            )
            note = deps.build_interaction_note(last_user_text, reply_text, assignment_id=req.assignment_id)
            payload = {"student_id": req.student_id, "interaction_note": note}
            if deps.profile_update_async:
                deps.enqueue_profile_update(payload)
            else:
                await deps.run_in_threadpool(deps.student_profile_update, payload)
        except Exception as exc:
            deps.diag_log("student.profile.update_failed", {"student_id": req.student_id, "error": str(exc)[:200]})
    return ChatResponse(reply=reply_text, role=role_hint)


async def chat_start(req: ChatStartRequest, *, deps: ChatHandlerDeps):
    result = deps.start_chat_api(req)
    if _is_awaitable(result):
        return await result
    return result


async def chat_status(job_id: str, *, deps: ChatHandlerDeps):
    try:
        result = deps.get_chat_status(job_id)
        if _is_awaitable(result):
            return await result
        return result
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="job not found")
```

Create `/Users/lvxiaoer/Documents/New project/services/api/handlers/__init__.py` (empty file).

**Step 4: Run tests to verify pass**

Run: `python3 -m pytest tests/test_chat_handlers.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add /Users/lvxiaoer/Documents/New\ project/services/api/handlers/__init__.py \
  /Users/lvxiaoer/Documents/New\ project/services/api/handlers/chat_handlers.py \
  /Users/lvxiaoer/Documents/New\ project/tests/test_chat_handlers.py
git commit -m "refactor: add chat handlers module"
```

---

### Task 2: Delegate app_core chat endpoints to handlers

**Files:**
- Modify: `/Users/lvxiaoer/Documents/New project/services/api/app_core.py`

**Step 1: Write failing test (if needed)**

No new test required if Task 1 tests are green; keep existing route tests unchanged.

**Step 2: Update app_core to use handlers**

In `/Users/lvxiaoer/Documents/New project/services/api/app_core.py`:

- Import `chat_handlers`.
- Add a deps builder:

```python
from .handlers import chat_handlers


def _chat_handlers_deps():
    return chat_handlers.ChatHandlerDeps(
        compute_chat_reply_sync=_compute_chat_reply_sync,
        detect_math_delimiters=detect_math_delimiters,
        detect_latex_tokens=detect_latex_tokens,
        diag_log=diag_log,
        build_interaction_note=build_interaction_note,
        enqueue_profile_update=enqueue_profile_update,
        student_profile_update=student_profile_update,
        profile_update_async=PROFILE_UPDATE_ASYNC,
        run_in_threadpool=run_in_threadpool,
        get_chat_status=lambda job_id: _get_chat_status_impl(job_id, deps=_chat_status_deps()),
        start_chat_api=lambda req: _start_chat_api_impl(req, deps=_chat_api_deps()),
    )
```

- Replace bodies of `chat`, `chat_start`, `chat_status` with delegations:

```python
async def chat(req: ChatRequest):
    return await chat_handlers.chat(req, deps=_chat_handlers_deps())

async def chat_start(req: ChatStartRequest):
    return await chat_handlers.chat_start(req, deps=_chat_handlers_deps())

async def chat_status(job_id: str):
    return await chat_handlers.chat_status(job_id, deps=_chat_handlers_deps())
```

**Step 3: Run targeted tests**

Run:
- `python3 -m pytest tests/test_chat_handlers.py -v`
- `python3 -m pytest tests/test_app_queue_backend_mode.py -v`

Expected: PASS

**Step 4: Commit**

```bash
git add /Users/lvxiaoer/Documents/New\ project/services/api/app_core.py
git commit -m "refactor: delegate chat endpoints to handlers"
```

---

### Task 3: Regression sweep

**Files:**
- None

**Step 1: Run core tests**

Run: `python3 -m pytest tests/test_settings.py tests/test_runtime_state.py tests/test_queue_runtime.py tests/test_chat_handlers.py tests/test_app_queue_backend_mode.py tests/test_tenant_admin_and_dispatcher.py -v`
Expected: PASS

**Step 2: Commit (if any test-only tweaks)**

```bash
git status -sb
```

---

Plan complete and saved to `/Users/lvxiaoer/Documents/New project/.worktrees/codex/phase2-chat-handlers/docs/plans/2026-02-09-chat-handlers-refactor.md`.

Two execution options:

1. Subagent-Driven (this session) — I dispatch a fresh subagent per task and review between tasks
2. Parallel Session (separate) — Open a new session using executing-plans and run the plan step-by-step

Which approach?
