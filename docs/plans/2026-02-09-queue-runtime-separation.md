# Queue Runtime Separation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extract queue runtime orchestration from `app_core.py` into a dedicated module and keep `app_core` focused on API handlers and wiring.

**Architecture:** Introduce `queue_runtime.py` to manage backend start/stop and Redis readiness checks. `app_core.start_tenant_runtime()` and `stop_tenant_runtime()` delegate to this module. Existing inline worker helpers remain in `app_core` for now, but are called through the runtime module when needed.

**Tech Stack:** Python 3.11, FastAPI, pytest

---

### Task 1: Add queue_runtime module + tests

**Files:**
- Create: `/Users/lvxiaoer/Documents/New project/services/api/queue_runtime.py`
- Create: `/Users/lvxiaoer/Documents/New project/tests/test_queue_runtime.py`

**Step 1: Write the failing test**

Create `/Users/lvxiaoer/Documents/New project/tests/test_queue_runtime.py`:

```python
class StubBackend:
    def __init__(self):
        self.started = 0
        self.stopped = 0

    def start(self):
        self.started += 1

    def stop(self):
        self.stopped += 1


def test_start_runtime_calls_require_redis_when_not_pytest():
    from services.api import queue_runtime

    backend = StubBackend()
    called = {"redis": 0}

    def require_redis():
        called["redis"] += 1

    queue_runtime.start_runtime(backend=backend, require_redis=require_redis, is_pytest=False)

    assert backend.started == 1
    assert called["redis"] == 1


def test_start_runtime_skips_require_redis_in_pytest():
    from services.api import queue_runtime

    backend = StubBackend()
    called = {"redis": 0}

    def require_redis():
        called["redis"] += 1

    queue_runtime.start_runtime(backend=backend, require_redis=require_redis, is_pytest=True)

    assert backend.started == 1
    assert called["redis"] == 0


def test_stop_runtime_calls_backend_stop():
    from services.api import queue_runtime

    backend = StubBackend()
    queue_runtime.stop_runtime(backend=backend)

    assert backend.stopped == 1
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_queue_runtime.py -v`
Expected: FAIL (module/function missing)

**Step 3: Implement queue_runtime**

Create `/Users/lvxiaoer/Documents/New project/services/api/queue_runtime.py`:

```python
from __future__ import annotations

from typing import Callable, Optional

from . import settings
from .queue_backend import get_queue_backend


def start_runtime(
    *,
    backend=None,
    require_redis: Optional[Callable[[], None]] = None,
    is_pytest: Optional[bool] = None,
) -> None:
    if backend is None:
        backend = get_queue_backend(tenant_id=settings.tenant_id() or None)
    if require_redis is None:
        from .rq_tasks import require_redis
    if is_pytest is None:
        is_pytest = settings.is_pytest()
    if not is_pytest:
        require_redis()
    backend.start()


def stop_runtime(*, backend=None) -> None:
    if backend is None:
        backend = get_queue_backend(tenant_id=settings.tenant_id() or None)
    backend.stop()
```

**Step 4: Run tests to verify pass**

Run: `python3 -m pytest tests/test_queue_runtime.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add /Users/lvxiaoer/Documents/New\ project/services/api/queue_runtime.py \
  /Users/lvxiaoer/Documents/New\ project/tests/test_queue_runtime.py
git commit -m "refactor: add queue runtime orchestrator"
```

---

### Task 2: Delegate app_core runtime start/stop to queue_runtime

**Files:**
- Modify: `/Users/lvxiaoer/Documents/New project/services/api/app_core.py`
- Modify: `/Users/lvxiaoer/Documents/New project/tests/test_app_queue_backend_mode.py`

**Step 1: Write failing test (if needed)**

If any behavior changes are needed, adjust tests first. Minimal change should keep existing tests passing. If you add a new assertion, do it here.

**Step 2: Update app_core to use queue_runtime**

In `/Users/lvxiaoer/Documents/New project/services/api/app_core.py`:

- Import `queue_runtime.start_runtime` and `queue_runtime.stop_runtime`.
- Replace `start_tenant_runtime()` body with:

```python
from .queue_runtime import start_runtime as _start_runtime


def start_tenant_runtime() -> None:
    _validate_master_key_policy_impl(getenv=os.getenv)
    _start_runtime(backend=_queue_backend(), is_pytest=_settings.is_pytest())
```

- Replace `stop_tenant_runtime()` body with:

```python
from .queue_runtime import stop_runtime as _stop_runtime


def stop_tenant_runtime() -> None:
    _stop_runtime(backend=_queue_backend())
```

**Step 3: Run targeted tests**

Run: `python3 -m pytest tests/test_app_queue_backend_mode.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add /Users/lvxiaoer/Documents/New\ project/services/api/app_core.py \
  /Users/lvxiaoer/Documents/New\ project/tests/test_app_queue_backend_mode.py
git commit -m "refactor: delegate runtime start/stop to queue_runtime"
```

---

### Task 3: Regression sweep

**Files:**
- None

**Step 1: Run core tests**

Run: `python3 -m pytest tests/test_settings.py tests/test_runtime_state.py tests/test_queue_runtime.py tests/test_app_queue_backend_mode.py tests/test_tenant_admin_and_dispatcher.py -v`
Expected: PASS

**Step 2: Commit (if any test-only tweaks)**

```bash
git status -sb
```

---

Plan complete and saved to `/Users/lvxiaoer/Documents/New project/.worktrees/codex/stage0-runtime-state/docs/plans/2026-02-09-queue-runtime-separation.md`.

Two execution options:

1. Subagent-Driven (this session) — I dispatch a fresh subagent per task and review between tasks
2. Parallel Session (separate) — Open a new session using executing-plans and run the plan step-by-step

Which approach?
