# Runtime & Queue Decoupling Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move queue backend selection, inline backend wiring, and chat lane store initialization out of `app_core.py`, and centralize runtime start/stop for cleaner isolation and testing.

**Architecture:** Add small factory modules for queue backend caching and chat lane store creation. Introduce a runtime manager to wire master-key validation + queue runtime start/stop. `app_core.py` becomes a thin adapter that supplies inline backend factories and delegates runtime control to the new modules.

**Tech Stack:** Python 3.11, FastAPI, pytest (anyio)

---

### Task 1: Add queue backend factory + inline backend wrapper

**Files:**
- Create: `/Users/lvxiaoer/Documents/New project/services/api/queue_inline_backend.py`
- Create: `/Users/lvxiaoer/Documents/New project/services/api/queue_backend_factory.py`
- Test: `/Users/lvxiaoer/Documents/New project/tests/test_queue_backend_factory.py`

**Step 1: Write the failing test**

Create `/Users/lvxiaoer/Documents/New project/tests/test_queue_backend_factory.py`:

```python
from services.api.queue_backend_factory import get_app_queue_backend, reset_queue_backend


class DummyBackend:
    name = "dummy"

    def __init__(self, label: str):
        self.label = label

    def enqueue_upload_job(self, job_id: str) -> None:
        return None

    def enqueue_exam_job(self, job_id: str) -> None:
        return None

    def enqueue_profile_update(self, payload: dict) -> None:
        return None

    def enqueue_chat_job(self, job_id: str, lane_id=None) -> dict:
        return {"job_id": job_id, "lane_id": lane_id}

    def scan_pending_upload_jobs(self) -> int:
        return 0

    def scan_pending_exam_jobs(self) -> int:
        return 0

    def scan_pending_chat_jobs(self) -> int:
        return 0

    def start(self) -> None:
        return None

    def stop(self) -> None:
        return None


def test_get_app_queue_backend_uses_inline_in_pytest():
    created = []

    def inline_factory():
        backend = DummyBackend("inline")
        created.append(backend)
        return backend

    backend = get_app_queue_backend(
        tenant_id="t1",
        is_pytest=True,
        inline_backend_factory=inline_factory,
        get_backend=lambda **_kwargs: DummyBackend("rq"),
    )

    assert backend is created[0]
    assert backend.label == "inline"


def test_get_app_queue_backend_caches_and_resets():
    created = []

    def inline_factory():
        backend = DummyBackend(f"inline-{len(created)}")
        created.append(backend)
        return backend

    backend_1 = get_app_queue_backend(
        tenant_id=None,
        is_pytest=True,
        inline_backend_factory=inline_factory,
        get_backend=lambda **_kwargs: DummyBackend("rq"),
    )
    backend_2 = get_app_queue_backend(
        tenant_id=None,
        is_pytest=True,
        inline_backend_factory=inline_factory,
        get_backend=lambda **_kwargs: DummyBackend("rq"),
    )

    assert backend_1 is backend_2

    reset_queue_backend()

    backend_3 = get_app_queue_backend(
        tenant_id=None,
        is_pytest=True,
        inline_backend_factory=inline_factory,
        get_backend=lambda **_kwargs: DummyBackend("rq"),
    )

    assert backend_3 is not backend_1
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_queue_backend_factory.py -v`
Expected: FAIL (module not found)

**Step 3: Write minimal implementation**

Create `/Users/lvxiaoer/Documents/New project/services/api/queue_inline_backend.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional


@dataclass
class InlineQueueBackend:
    enqueue_upload_job_fn: Callable[[str], None]
    enqueue_exam_job_fn: Callable[[str], None]
    enqueue_profile_update_fn: Callable[[Dict[str, Any]], None]
    enqueue_chat_job_fn: Callable[[str, Optional[str]], Dict[str, Any]]
    scan_pending_upload_jobs_fn: Callable[[], int]
    scan_pending_exam_jobs_fn: Callable[[], int]
    scan_pending_chat_jobs_fn: Callable[[], int]
    start_fn: Callable[[], None]
    stop_fn: Callable[[], None]
    name: str = "inline-test"

    def enqueue_upload_job(self, job_id: str) -> None:
        return self.enqueue_upload_job_fn(job_id)

    def enqueue_exam_job(self, job_id: str) -> None:
        return self.enqueue_exam_job_fn(job_id)

    def enqueue_profile_update(self, payload: Dict[str, Any]) -> None:
        return self.enqueue_profile_update_fn(payload)

    def enqueue_chat_job(self, job_id: str, lane_id: Optional[str] = None) -> Dict[str, Any]:
        return self.enqueue_chat_job_fn(job_id, lane_id)

    def scan_pending_upload_jobs(self) -> int:
        return int(self.scan_pending_upload_jobs_fn() or 0)

    def scan_pending_exam_jobs(self) -> int:
        return int(self.scan_pending_exam_jobs_fn() or 0)

    def scan_pending_chat_jobs(self) -> int:
        return int(self.scan_pending_chat_jobs_fn() or 0)

    def start(self) -> None:
        return self.start_fn()

    def stop(self) -> None:
        return self.stop_fn()
```

Create `/Users/lvxiaoer/Documents/New project/services/api/queue_backend_factory.py`:

```python
from __future__ import annotations

from typing import Callable, Optional

from .queue_backend import QueueBackend, get_queue_backend


_QUEUE_BACKEND: Optional[QueueBackend] = None


def get_app_queue_backend(
    *,
    tenant_id: Optional[str],
    is_pytest: bool,
    inline_backend_factory: Callable[[], QueueBackend],
    get_backend: Callable[..., QueueBackend] = get_queue_backend,
) -> QueueBackend:
    global _QUEUE_BACKEND
    if _QUEUE_BACKEND is None:
        _QUEUE_BACKEND = inline_backend_factory() if is_pytest else get_backend(tenant_id=tenant_id)
    return _QUEUE_BACKEND


def reset_queue_backend() -> None:
    global _QUEUE_BACKEND
    _QUEUE_BACKEND = None
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_queue_backend_factory.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add /Users/lvxiaoer/Documents/New\ project/services/api/queue_inline_backend.py \
  /Users/lvxiaoer/Documents/New\ project/services/api/queue_backend_factory.py \
  /Users/lvxiaoer/Documents/New\ project/tests/test_queue_backend_factory.py
git commit -m "feat: add queue backend factory"
```

---

### Task 2: Add chat lane store factory

**Files:**
- Create: `/Users/lvxiaoer/Documents/New project/services/api/chat_lane_store_factory.py`
- Test: `/Users/lvxiaoer/Documents/New project/tests/test_chat_lane_store_factory.py`

**Step 1: Write the failing test**

Create `/Users/lvxiaoer/Documents/New project/tests/test_chat_lane_store_factory.py`:

```python
from services.api.chat_lane_store import MemoryLaneStore
from services.api.chat_lane_store_factory import get_chat_lane_store, reset_chat_lane_stores


def test_chat_lane_store_factory_caches_per_tenant():
    store_1 = get_chat_lane_store(
        tenant_id="t1",
        is_pytest=True,
        redis_url="redis://localhost:6379/0",
        debounce_ms=10,
        claim_ttl_sec=5,
    )
    store_2 = get_chat_lane_store(
        tenant_id="t1",
        is_pytest=True,
        redis_url="redis://localhost:6379/0",
        debounce_ms=10,
        claim_ttl_sec=5,
    )
    store_3 = get_chat_lane_store(
        tenant_id="t2",
        is_pytest=True,
        redis_url="redis://localhost:6379/0",
        debounce_ms=10,
        claim_ttl_sec=5,
    )

    assert store_1 is store_2
    assert store_1 is not store_3
    assert isinstance(store_1, MemoryLaneStore)


def test_chat_lane_store_factory_reset():
    store_1 = get_chat_lane_store(
        tenant_id="t1",
        is_pytest=True,
        redis_url="redis://localhost:6379/0",
        debounce_ms=0,
        claim_ttl_sec=1,
    )

    reset_chat_lane_stores()

    store_2 = get_chat_lane_store(
        tenant_id="t1",
        is_pytest=True,
        redis_url="redis://localhost:6379/0",
        debounce_ms=0,
        claim_ttl_sec=1,
    )

    assert store_1 is not store_2
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_chat_lane_store_factory.py -v`
Expected: FAIL (module not found)

**Step 3: Write minimal implementation**

Create `/Users/lvxiaoer/Documents/New project/services/api/chat_lane_store_factory.py`:

```python
from __future__ import annotations

from typing import Dict

from .chat_lane_store import ChatLaneStore, MemoryLaneStore


_CHAT_LANE_STORES: Dict[str, ChatLaneStore] = {}


def get_chat_lane_store(
    *,
    tenant_id: str,
    is_pytest: bool,
    redis_url: str,
    debounce_ms: int,
    claim_ttl_sec: int,
) -> ChatLaneStore:
    tenant_key = str(tenant_id or "default").strip() or "default"
    store = _CHAT_LANE_STORES.get(tenant_key)
    if store is None:
        if is_pytest:
            store = MemoryLaneStore(
                debounce_ms=debounce_ms,
                claim_ttl_sec=claim_ttl_sec,
            )
        else:
            from .chat_redis_lane_store import RedisLaneStore
            from .redis_clients import get_redis_client

            store = RedisLaneStore(
                redis_client=get_redis_client(redis_url, decode_responses=True),
                tenant_id=tenant_key,
                claim_ttl_sec=claim_ttl_sec,
                debounce_ms=debounce_ms,
            )
        _CHAT_LANE_STORES[tenant_key] = store
    return store


def reset_chat_lane_stores() -> None:
    _CHAT_LANE_STORES.clear()
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_chat_lane_store_factory.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add /Users/lvxiaoer/Documents/New\ project/services/api/chat_lane_store_factory.py \
  /Users/lvxiaoer/Documents/New\ project/tests/test_chat_lane_store_factory.py
git commit -m "feat: add chat lane store factory"
```

---

### Task 3: Add runtime manager + wire app_core/runtime_state

**Files:**
- Create: `/Users/lvxiaoer/Documents/New project/services/api/runtime_manager.py`
- Modify: `/Users/lvxiaoer/Documents/New project/services/api/app_core.py`
- Modify: `/Users/lvxiaoer/Documents/New project/services/api/runtime_state.py`
- Modify: `/Users/lvxiaoer/Documents/New project/tests/test_runtime_state.py`
- Test: `/Users/lvxiaoer/Documents/New project/tests/test_runtime_manager.py`

**Step 1: Write the failing test**

Create `/Users/lvxiaoer/Documents/New project/tests/test_runtime_manager.py`:

```python
from services.api.runtime_manager import RuntimeManagerDeps, start_tenant_runtime, stop_tenant_runtime


def test_start_and_stop_runtime_wire_backend_and_validate():
    calls = {}

    def validate_master_key_policy(*, getenv):
        calls["validated"] = True

    def inline_backend_factory():
        return "inline-backend"

    def get_backend(**kwargs):
        calls["backend_args"] = kwargs
        return "backend"

    def start_runtime(*, backend, is_pytest):
        calls["start"] = (backend, is_pytest)

    def stop_runtime(*, backend):
        calls["stop"] = backend

    deps = RuntimeManagerDeps(
        tenant_id="t1",
        is_pytest=True,
        validate_master_key_policy=validate_master_key_policy,
        inline_backend_factory=inline_backend_factory,
        get_backend=get_backend,
        start_runtime=start_runtime,
        stop_runtime=stop_runtime,
    )

    start_tenant_runtime(deps=deps)
    stop_tenant_runtime(deps=deps)

    assert calls["validated"] is True
    assert calls["backend_args"]["tenant_id"] == "t1"
    assert calls["backend_args"]["is_pytest"] is True
    assert calls["start"] == ("backend", True)
    assert calls["stop"] == "backend"
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_runtime_manager.py -v`
Expected: FAIL (module not found)

**Step 3: Write minimal implementation**

Create `/Users/lvxiaoer/Documents/New project/services/api/runtime_manager.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional
import os

from .queue_backend import QueueBackend
from .queue_backend_factory import get_app_queue_backend
from .queue_runtime import start_runtime as _start_runtime
from .queue_runtime import stop_runtime as _stop_runtime


@dataclass
class RuntimeManagerDeps:
    tenant_id: Optional[str]
    is_pytest: bool
    validate_master_key_policy: Callable[..., None]
    inline_backend_factory: Callable[[], QueueBackend]
    get_backend: Callable[..., QueueBackend] = get_app_queue_backend
    start_runtime: Callable[..., None] = _start_runtime
    stop_runtime: Callable[..., None] = _stop_runtime
    getenv: Callable[[str, Optional[str]], str] = os.getenv


def start_tenant_runtime(*, deps: RuntimeManagerDeps) -> None:
    deps.validate_master_key_policy(getenv=deps.getenv)
    backend = deps.get_backend(
        tenant_id=deps.tenant_id,
        is_pytest=deps.is_pytest,
        inline_backend_factory=deps.inline_backend_factory,
    )
    deps.start_runtime(backend=backend, is_pytest=deps.is_pytest)


def stop_tenant_runtime(*, deps: RuntimeManagerDeps) -> None:
    backend = deps.get_backend(
        tenant_id=deps.tenant_id,
        is_pytest=deps.is_pytest,
        inline_backend_factory=deps.inline_backend_factory,
    )
    deps.stop_runtime(backend=backend)
```

**Step 4: Update app_core to use factories and runtime manager**

Modify `/Users/lvxiaoer/Documents/New project/services/api/app_core.py`:

1) Update imports near the top:

```python
from .queue_backend_factory import get_app_queue_backend
from .queue_inline_backend import InlineQueueBackend
from .chat_lane_store_factory import get_chat_lane_store
from .runtime_manager import RuntimeManagerDeps, start_tenant_runtime as _start_tenant_runtime
from .runtime_manager import stop_tenant_runtime as _stop_tenant_runtime
```

2) Replace `_chat_lane_store()` with:

```python
def _chat_lane_store():
    return get_chat_lane_store(
        tenant_id=str(TENANT_ID or "default").strip() or "default",
        is_pytest=_settings.is_pytest(),
        redis_url=REDIS_URL,
        debounce_ms=CHAT_LANE_DEBOUNCE_MS,
        claim_ttl_sec=CHAT_JOB_CLAIM_TTL_SEC,
    )
```

3) Add inline backend factory + helper (place near other helpers):

```python
def _inline_backend_factory():
    return InlineQueueBackend(
        enqueue_upload_job_fn=_enqueue_upload_job_inline,
        enqueue_exam_job_fn=_enqueue_exam_job_inline,
        enqueue_profile_update_fn=_enqueue_profile_update_inline,
        enqueue_chat_job_fn=_enqueue_chat_job_inline,
        scan_pending_upload_jobs_fn=_scan_pending_upload_jobs_inline,
        scan_pending_exam_jobs_fn=_scan_pending_exam_jobs_inline,
        scan_pending_chat_jobs_fn=_scan_pending_chat_jobs_inline,
        start_fn=_start_inline_workers,
        stop_fn=_stop_inline_workers,
    )


def _app_queue_backend():
    return get_app_queue_backend(
        tenant_id=TENANT_ID or None,
        is_pytest=_settings.is_pytest(),
        inline_backend_factory=_inline_backend_factory,
    )
```

4) Replace all `_queue_backend()` call sites with `_app_queue_backend()` (e.g. `enqueue_upload_job`, `scan_pending_upload_jobs`, `enqueue_exam_job`, `enqueue_chat_job`, `scan_pending_chat_jobs`, etc.).

5) Update runtime start/stop to delegate to runtime_manager:

```python
def start_tenant_runtime() -> None:
    _start_tenant_runtime(
        deps=RuntimeManagerDeps(
            tenant_id=TENANT_ID or None,
            is_pytest=_settings.is_pytest(),
            validate_master_key_policy=_validate_master_key_policy_impl,
            inline_backend_factory=_inline_backend_factory,
        )
    )


def stop_tenant_runtime() -> None:
    _stop_tenant_runtime(
        deps=RuntimeManagerDeps(
            tenant_id=TENANT_ID or None,
            is_pytest=_settings.is_pytest(),
            validate_master_key_policy=_validate_master_key_policy_impl,
            inline_backend_factory=_inline_backend_factory,
        )
    )
```

**Step 5: Update runtime_state reset hooks**

Modify `/Users/lvxiaoer/Documents/New project/services/api/runtime_state.py` to reset factory caches instead of module globals:

```python
from . import chat_lane_store_factory, queue_backend_factory


def reset_runtime_state(mod: Any, *, create_chat_idempotency_store) -> None:
    ...
    mod.CHAT_IDEMPOTENCY_STATE = create_chat_idempotency_store(mod.CHAT_JOB_DIR)
    chat_lane_store_factory.reset_chat_lane_stores()
    queue_backend_factory.reset_queue_backend()
    ...
```

Remove assignments to `mod._CHAT_LANE_STORES` and `mod._QUEUE_BACKEND`.

**Step 6: Update runtime_state test**

Modify `/Users/lvxiaoer/Documents/New project/tests/test_runtime_state.py` to assert factory caches are reset:

```python
from types import SimpleNamespace
from collections import deque

from services.api import runtime_state
from services.api import queue_backend_factory, chat_lane_store_factory


def test_reset_runtime_state_resets_queues_and_caches(tmp_path):
    mod = SimpleNamespace()
    mod.DATA_DIR = tmp_path / "data"
    mod.UPLOADS_DIR = tmp_path / "uploads"
    mod.UPLOAD_JOB_DIR = mod.UPLOADS_DIR / "assignment_jobs"
    mod.EXAM_UPLOAD_JOB_DIR = mod.UPLOADS_DIR / "exam_jobs"
    mod.CHAT_JOB_DIR = mod.UPLOADS_DIR / "chat_jobs"
    mod.CHAT_LANE_DEBOUNCE_MS = 0
    mod.CHAT_JOB_CLAIM_TTL_SEC = 600
    mod.OCR_MAX_CONCURRENCY = 2
    mod.LLM_MAX_CONCURRENCY = 3
    mod.LLM_MAX_CONCURRENCY_STUDENT = 1
    mod.LLM_MAX_CONCURRENCY_TEACHER = 1

    mod.UPLOAD_JOB_QUEUE = deque(["old"])

    backend = queue_backend_factory.get_app_queue_backend(
        tenant_id=None,
        is_pytest=True,
        inline_backend_factory=lambda: object(),
        get_backend=lambda **_kwargs: object(),
    )
    store = chat_lane_store_factory.get_chat_lane_store(
        tenant_id="default",
        is_pytest=True,
        redis_url="redis://localhost:6379/0",
        debounce_ms=0,
        claim_ttl_sec=600,
    )

    runtime_state.reset_runtime_state(mod, create_chat_idempotency_store=lambda _: object())

    assert list(mod.UPLOAD_JOB_QUEUE) == []
    assert mod.CHAT_IDEMPOTENCY_STATE is not None

    backend_after = queue_backend_factory.get_app_queue_backend(
        tenant_id=None,
        is_pytest=True,
        inline_backend_factory=lambda: object(),
        get_backend=lambda **_kwargs: object(),
    )
    store_after = chat_lane_store_factory.get_chat_lane_store(
        tenant_id="default",
        is_pytest=True,
        redis_url="redis://localhost:6379/0",
        debounce_ms=0,
        claim_ttl_sec=600,
    )

    assert backend_after is not backend
    assert store_after is not store
```

**Step 7: Run tests to verify changes**

Run:
- `python3 -m pytest tests/test_queue_backend_factory.py tests/test_chat_lane_store_factory.py tests/test_runtime_manager.py tests/test_runtime_state.py -v`
- `python3 -m pytest tests/test_app_queue_backend_mode.py -v`

Expected: PASS

**Step 8: Commit**

```bash
git add /Users/lvxiaoer/Documents/New\ project/services/api/runtime_manager.py \
  /Users/lvxiaoer/Documents/New\ project/services/api/app_core.py \
  /Users/lvxiaoer/Documents/New\ project/services/api/runtime_state.py \
  /Users/lvxiaoer/Documents/New\ project/tests/test_runtime_manager.py \
  /Users/lvxiaoer/Documents/New\ project/tests/test_runtime_state.py
git commit -m "refactor: centralize runtime and queue wiring"
```

---

### Task 4: Regression sweep

**Files:**
- None

**Step 1: Run core tests**

Run: `python3 -m pytest tests/test_settings.py tests/test_runtime_state.py tests/test_queue_runtime.py tests/test_queue_backend_factory.py tests/test_chat_lane_store_factory.py tests/test_runtime_manager.py tests/test_app_queue_backend_mode.py tests/test_tenant_admin_and_dispatcher.py -v`
Expected: PASS

**Step 2: Commit (if any test-only tweaks)**

```bash
git status -sb
```
