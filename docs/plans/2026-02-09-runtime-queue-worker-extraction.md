# Runtime/Queue/Worker Extraction Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove runtime/queue/worker orchestration from `services/api/app_core.py` by relocating it into dedicated runtime/queue/workers packages and updating all call sites (no app_core wrappers).

**Architecture:** Create `services/api/runtime/`, `services/api/queue/`, and `services/api/workers/` packages. Move existing runtime/queue/worker modules into those packages, then extract inline worker loops and runtime lifecycle from `app_core.py` into dedicated modules. Update handlers, tests, and startup code to use the new entrypoints.

**Tech Stack:** Python 3, FastAPI, pytest, RQ.

---

### Task 1: Create queue package and move queue backend modules

**Files:**
- Create: `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/queue/__init__.py`
- Move: `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/queue_backend.py` -> `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/queue/queue_backend.py`
- Move: `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/queue_backend_factory.py` -> `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/queue/queue_backend_factory.py`
- Move: `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/queue_backend_rq.py` -> `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/queue/queue_backend_rq.py`
- Move: `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/queue_inline_backend.py` -> `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/queue/queue_inline_backend.py`
- Modify: `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/runtime_manager.py`
- Modify: `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/queue_runtime.py`
- Modify: `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/runtime_state.py`
- Modify: `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/app_core.py`
- Modify: `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_queue_backend_selection.py`
- Modify: `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_queue_backend_factory.py`

**Step 1: Write the failing test**

Update imports to point at the new package (this will fail until the package exists):

```python
# /Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_queue_backend_selection.py
from services.api.queue.queue_backend import get_queue_backend
from services.api.queue import queue_backend
```

```python
# /Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_queue_backend_factory.py
from services.api.queue.queue_backend_factory import get_app_queue_backend, reset_queue_backend
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest /Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_queue_backend_selection.py -v`

Expected: ImportError for `services.api.queue`.

**Step 3: Write minimal implementation**

- Create package:

```bash
mkdir -p /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/services/api/queue
printf "" > /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/services/api/queue/__init__.py
```

- Move modules:

```bash
git mv /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/services/api/queue_backend.py \
  /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/services/api/queue/queue_backend.py

git mv /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/services/api/queue_backend_factory.py \
  /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/services/api/queue/queue_backend_factory.py

git mv /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/services/api/queue_backend_rq.py \
  /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/services/api/queue/queue_backend_rq.py

git mv /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/services/api/queue_inline_backend.py \
  /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/services/api/queue/queue_inline_backend.py
```

- Update imports inside moved modules:

```python
# /Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/queue/queue_backend.py
from services.api import settings
from .queue_backend_rq import RqQueueBackend
```

```python
# /Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/queue/queue_backend_factory.py
from .queue_backend import QueueBackend, get_queue_backend
```

```python
# /Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/queue/queue_backend_rq.py
from .. import rq_tasks
```

- Update imports in existing modules that referenced old paths:

```python
# /Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/runtime_manager.py
from services.api.queue.queue_backend import QueueBackend
from services.api.queue.queue_backend_factory import get_app_queue_backend
```

```python
# /Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/queue_runtime.py
from services.api.queue.queue_backend import get_queue_backend
```

```python
# /Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/runtime_state.py
from services.api import chat_lane_store_factory
from services.api.queue import queue_backend_factory
```

```python
# /Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/app_core.py
from services.api.queue.queue_backend import rq_enabled as _rq_enabled_impl
from services.api.queue.queue_backend_factory import get_app_queue_backend
from services.api.queue.queue_inline_backend import InlineQueueBackend
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest /Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_queue_backend_selection.py -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/services/api/queue \
  /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/services/api/runtime_manager.py \
  /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/services/api/queue_runtime.py \
  /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/services/api/runtime_state.py \
  /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/services/api/app_core.py \
  /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_queue_backend_selection.py \
  /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_queue_backend_factory.py

git commit -m "refactor: move queue backend modules into queue package"
```

---

### Task 2: Move runtime modules into runtime package

**Files:**
- Create: `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/runtime/__init__.py`
- Move: `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/runtime_manager.py` -> `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/runtime/runtime_manager.py`
- Move: `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/runtime_state.py` -> `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/runtime/runtime_state.py`
- Move: `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/queue_runtime.py` -> `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/runtime/queue_runtime.py`
- Modify: `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/app_core.py`
- Modify: `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/tenant_app_factory.py`
- Modify: `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_runtime_manager.py`
- Modify: `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_runtime_state.py`
- Modify: `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_queue_runtime.py`

**Step 1: Write the failing test**

Update tests to import from `services.api.runtime`:

```python
# /Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_runtime_manager.py
from services.api.runtime.runtime_manager import RuntimeManagerDeps, start_tenant_runtime, stop_tenant_runtime
```

```python
# /Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_runtime_state.py
from services.api.runtime import runtime_state
from services.api.queue import queue_backend_factory
from services.api import chat_lane_store_factory
```

```python
# /Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_queue_runtime.py
from services.api.runtime import queue_runtime
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest /Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_runtime_manager.py -v`

Expected: ImportError for `services.api.runtime`.

**Step 3: Write minimal implementation**

- Create package and move modules:

```bash
mkdir -p /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/services/api/runtime
printf "" > /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/services/api/runtime/__init__.py

git mv /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/services/api/runtime_manager.py \
  /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/services/api/runtime/runtime_manager.py

git mv /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/services/api/runtime_state.py \
  /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/services/api/runtime/runtime_state.py

git mv /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/services/api/queue_runtime.py \
  /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/services/api/runtime/queue_runtime.py
```

- Update imports inside moved modules:

```python
# /Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/runtime/runtime_manager.py
from services.api.queue.queue_backend import QueueBackend
from services.api.queue.queue_backend_factory import get_app_queue_backend
from services.api.runtime.queue_runtime import start_runtime as _start_runtime
from services.api.runtime.queue_runtime import stop_runtime as _stop_runtime
```

```python
# /Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/runtime/queue_runtime.py
from services.api import settings
from services.api.queue.queue_backend import get_queue_backend
```

```python
# /Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/runtime/runtime_state.py
from services.api import chat_lane_store_factory
from services.api.queue import queue_backend_factory
```

- Update imports at call sites:

```python
# /Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/app_core.py
from services.api.runtime.runtime_manager import RuntimeManagerDeps, start_tenant_runtime as _start_tenant_runtime
from services.api.runtime.runtime_manager import stop_tenant_runtime as _stop_tenant_runtime
from services.api.runtime.runtime_state import reset_runtime_state as _reset_runtime_state
```

```python
# /Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/tenant_app_factory.py
from services.api.runtime.runtime_state import reset_runtime_state
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest /Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_runtime_manager.py -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/services/api/runtime \
  /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/services/api/app_core.py \
  /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/services/api/tenant_app_factory.py \
  /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_runtime_manager.py \
  /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_runtime_state.py \
  /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_queue_runtime.py

git commit -m "refactor: move runtime modules into runtime package"
```

---

### Task 3: Move worker modules into workers package

**Files:**
- Create: `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/workers/__init__.py`
- Move: `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/chat_worker_service.py` -> `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/workers/chat_worker_service.py`
- Move: `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/rq_tasks.py` -> `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/workers/rq_tasks.py`
- Move: `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/rq_worker.py` -> `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/workers/rq_worker.py`
- Move: `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/rq_tenant_runtime.py` -> `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/workers/rq_tenant_runtime.py`
- Modify: `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/queue/queue_backend_rq.py`
- Modify: `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/redis_clients.py`
- Modify: `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_chat_worker_service.py`
- Modify: `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/README.md`
- Modify: `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/docker-compose.yml`

**Step 1: Write the failing test**

Update tests to import from workers package:

```python
# /Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_chat_worker_service.py
from services.api.workers.chat_worker_service import ChatWorkerDeps, enqueue_chat_job, start_chat_worker
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest /Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_chat_worker_service.py -v`

Expected: ImportError for `services.api.workers`.

**Step 3: Write minimal implementation**

- Create package and move modules:

```bash
mkdir -p /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/services/api/workers
printf "" > /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/services/api/workers/__init__.py

git mv /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/services/api/chat_worker_service.py \
  /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/services/api/workers/chat_worker_service.py

git mv /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/services/api/rq_tasks.py \
  /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/services/api/workers/rq_tasks.py

git mv /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/services/api/rq_worker.py \
  /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/services/api/workers/rq_worker.py

git mv /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/services/api/rq_tenant_runtime.py \
  /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/services/api/workers/rq_tenant_runtime.py
```

- Update imports inside moved modules:

```python
# /Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/workers/rq_worker.py
from services.api.redis_clients import get_redis_client
from services.api.workers.rq_tasks import scan_pending_chat_jobs, scan_pending_exam_jobs, scan_pending_upload_jobs
```

```python
# /Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/workers/rq_tasks.py
from services.api.chat_redis_lane_store import ChatRedisLaneStore
from services.api.redis_clients import get_redis_client
from services.api.workers.rq_tenant_runtime import load_tenant_module
```

```python
# /Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/workers/rq_tenant_runtime.py
from services.api.tenant_config_store import TenantConfigStore
from services.api.tenant_registry import TenantRegistry
```

- Update queue backend RQ adapter to import new rq_tasks:

```python
# /Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/queue/queue_backend_rq.py
from services.api.workers import rq_tasks
```

- Update README and docker-compose:

```markdown
# /Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/README.md
- Worker 启动: `python -m services.api.workers.rq_worker`
```

```yaml
# /Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/docker-compose.yml
command: ["python3", "-m", "services.api.workers.rq_worker"]
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest /Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_chat_worker_service.py -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/services/api/workers \
  /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/services/api/queue/queue_backend_rq.py \
  /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/README.md \
  /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/docker-compose.yml \
  /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_chat_worker_service.py

git commit -m "refactor: move rq and chat worker modules into workers package"
```

---

### Task 4: Extract inline upload/exam/profile update workers from app_core

**Files:**
- Create: `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/workers/upload_worker_service.py`
- Create: `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/workers/exam_worker_service.py`
- Create: `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/workers/profile_update_worker_service.py`
- Create: `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/workers/inline_runtime.py`
- Modify: `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/app_core.py`
- Modify: `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_app_queue_backend_mode.py`
- Create: `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_inline_worker_services.py`

**Step 1: Write the failing test**

Add a minimal test to ensure inline workers can enqueue and start idempotently:

```python
# /Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_inline_worker_services.py
from collections import deque
import threading

from services.api.workers import upload_worker_service


def test_upload_inline_enqueue_sets_event(tmp_path):
    queue = deque()
    lock = threading.Lock()
    event = threading.Event()

    deps = upload_worker_service.UploadWorkerDeps(
        job_queue=queue,
        job_lock=lock,
        job_event=event,
        job_dir=tmp_path,
        stop_event=threading.Event(),
        worker_started_get=lambda: False,
        worker_started_set=lambda _: None,
        process_job=lambda _job_id: None,
        diag_log=lambda *_: None,
        sleep=lambda _: None,
        thread_factory=lambda **kwargs: None,
        rq_enabled=lambda: False,
    )

    upload_worker_service.enqueue_upload_job_inline("job-1", deps=deps)
    assert "job-1" in list(queue)
    assert event.is_set() is True
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest /Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_inline_worker_services.py -v`

Expected: ImportError or missing symbols.

**Step 3: Write minimal implementation**

Create worker service modules with deps similar to chat_worker_service. Example for upload worker:

```python
# /Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/workers/upload_worker_service.py
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Deque


@dataclass(frozen=True)
class UploadWorkerDeps:
    job_queue: Deque[str]
    job_lock: Any
    job_event: Any
    job_dir: Path
    stop_event: Any
    worker_started_get: Callable[[], bool]
    worker_started_set: Callable[[bool], None]
    process_job: Callable[[str], None]
    diag_log: Callable[[str, dict], None]
    sleep: Callable[[float], None]
    thread_factory: Callable[..., Any]
    rq_enabled: Callable[[], bool]


def enqueue_upload_job_inline(job_id: str, *, deps: UploadWorkerDeps) -> None:
    with deps.job_lock:
        if job_id not in deps.job_queue:
            deps.job_queue.append(job_id)
    deps.job_event.set()


def scan_pending_upload_jobs_inline(*, deps: UploadWorkerDeps) -> int:
    deps.job_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for job_path in deps.job_dir.glob("*/job.json"):
        try:
            data = json.loads(job_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        status = str(data.get("status") or "")
        job_id = str(data.get("job_id") or "")
        if status in {"queued", "processing"} and job_id:
            enqueue_upload_job_inline(job_id, deps=deps)
            count += 1
    return count


def upload_job_worker_loop(*, deps: UploadWorkerDeps) -> None:
    while not deps.stop_event.is_set():
        deps.job_event.wait(timeout=0.1)
        if deps.stop_event.is_set():
            break
        job_id = ""
        with deps.job_lock:
            if deps.job_queue:
                job_id = deps.job_queue.popleft()
            if not deps.job_queue:
                deps.job_event.clear()
        if not job_id:
            deps.sleep(0.1)
            continue
        try:
            deps.process_job(job_id)
        except Exception as exc:
            deps.diag_log("upload.job.failed", {"job_id": job_id, "error": str(exc)[:200]})


def start_upload_worker(*, deps: UploadWorkerDeps) -> None:
    if deps.rq_enabled():
        return
    if deps.worker_started_get():
        return
    deps.stop_event.clear()
    thread = deps.thread_factory(target=lambda: upload_job_worker_loop(deps=deps), daemon=True, name="upload-worker")
    if thread is not None:
        thread.start()
    deps.worker_started_set(True)


def stop_upload_worker(*, deps: UploadWorkerDeps, timeout_sec: float = 1.5) -> None:
    if deps.rq_enabled():
        return
    deps.stop_event.set()
    deps.job_event.set()
    deps.worker_started_set(False)
```

Create similar modules for exam and profile update, keeping logic identical to app_core (move code, do not change behavior).

Add deps builders in `app_core.py` to wire worker services (example for upload):

```python
# /Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/app_core.py
from services.api.workers.upload_worker_service import UploadWorkerDeps


def upload_worker_deps() -> UploadWorkerDeps:
    return UploadWorkerDeps(
        job_queue=UPLOAD_JOB_QUEUE,
        job_lock=UPLOAD_JOB_LOCK,
        job_event=UPLOAD_JOB_EVENT,
        job_dir=UPLOAD_JOB_DIR,
        stop_event=UPLOAD_JOB_STOP_EVENT,
        worker_started_get=lambda: bool(UPLOAD_JOB_WORKER_STARTED),
        worker_started_set=lambda value: _set_upload_worker_started(value),
        process_job=process_upload_job,
        diag_log=diag_log,
        sleep=time.sleep,
        thread_factory=lambda *args, **kwargs: threading.Thread(*args, **kwargs),
        rq_enabled=_rq_enabled,
    )
```

Create similar `exam_worker_deps()` and `profile_update_worker_deps()` helpers, and rename `_chat_worker_deps` to `chat_worker_deps` (or add a public alias) so bootstrap code can use it.

Add an inline worker orchestrator:

```python
# /Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/workers/inline_runtime.py
from __future__ import annotations

from services.api.workers.chat_worker_service import start_chat_worker, stop_chat_worker
from services.api.workers.exam_worker_service import start_exam_upload_worker, stop_exam_upload_worker
from services.api.workers.profile_update_worker_service import start_profile_update_worker, stop_profile_update_worker
from services.api.workers.upload_worker_service import start_upload_worker, stop_upload_worker


def start_inline_workers(*, upload_deps, exam_deps, profile_deps, chat_deps, profile_update_async: bool) -> None:
    start_upload_worker(deps=upload_deps)
    if profile_update_async:
        start_profile_update_worker(deps=profile_deps)
    start_exam_upload_worker(deps=exam_deps)
    start_chat_worker(deps=chat_deps)


def stop_inline_workers(*, upload_deps, exam_deps, profile_deps, chat_deps, profile_update_async: bool) -> None:
    stop_chat_worker(deps=chat_deps)
    stop_exam_upload_worker(deps=exam_deps)
    stop_upload_worker(deps=upload_deps)
    if profile_update_async:
        stop_profile_update_worker(deps=profile_deps)
```

Update `app_core.py` to remove the upload/exam/profile update worker functions and instead wire deps for the new modules.

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest /Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_inline_worker_services.py -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/services/api/workers/upload_worker_service.py \
  /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/services/api/workers/exam_worker_service.py \
  /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/services/api/workers/profile_update_worker_service.py \
  /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/services/api/app_core.py \
  /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_inline_worker_services.py

git commit -m "refactor: extract inline upload/exam/profile workers"
```

---

### Task 5: Move queue runtime wrappers and chat worker wiring out of app_core

**Files:**
- Modify: `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/runtime/queue_runtime.py`
- Create: `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/runtime/inline_backend_factory.py`
- Modify: `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/app_core.py`
- Modify: `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_chat_job_flow.py`
- Modify: `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_student_history_flow.py`
- Modify: `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_chat_lane_queue.py`
- Modify: `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_chat_status_flow.py`

**Step 1: Write the failing test**

Update tests to stop patching `app_mod.start_chat_worker` and instead patch worker module entrypoints:

```python
# /Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_chat_job_flow.py
from services.api.workers import chat_worker_service

app_mod = load_app(tmp)
chat_worker_service.start_chat_worker = lambda **_: None
app_mod.CHAT_JOB_WORKER_STARTED = True
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest /Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_chat_job_flow.py -v`

Expected: FAIL because app_core still exports wrapper functions and queue runtime wrappers are not yet in place.

**Step 3: Write minimal implementation**

- Expand `runtime/queue_runtime.py` to include enqueue and scan wrappers:

```python
# /Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/runtime/queue_runtime.py
from services.api.queue.queue_backend_factory import get_app_queue_backend
from services.api.queue.queue_inline_backend import InlineQueueBackend


def app_queue_backend(*, tenant_id, is_pytest, inline_backend_factory):
    return get_app_queue_backend(
        tenant_id=tenant_id,
        is_pytest=is_pytest,
        inline_backend_factory=inline_backend_factory,
    )


def enqueue_upload_job(job_id: str, *, backend) -> None:
    backend.enqueue_upload_job(job_id)


def enqueue_exam_job(job_id: str, *, backend) -> None:
    backend.enqueue_exam_job(job_id)


def enqueue_profile_update(payload: dict, *, backend) -> None:
    backend.enqueue_profile_update(payload)


def enqueue_chat_job(job_id: str, lane_id=None, *, backend):
    return backend.enqueue_chat_job(job_id, lane_id=lane_id)


def scan_pending_upload_jobs(*, backend) -> int:
    return int(backend.scan_pending_upload_jobs() or 0)


def scan_pending_exam_jobs(*, backend) -> int:
    return int(backend.scan_pending_exam_jobs() or 0)


def scan_pending_chat_jobs(*, backend) -> int:
    return int(backend.scan_pending_chat_jobs() or 0)
```

- Add an inline backend factory:

```python
# /Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/runtime/inline_backend_factory.py
from services.api.queue.queue_inline_backend import InlineQueueBackend


def build_inline_backend(
    *,
    enqueue_upload_job_fn,
    enqueue_exam_job_fn,
    enqueue_profile_update_fn,
    enqueue_chat_job_fn,
    scan_pending_upload_jobs_fn,
    scan_pending_exam_jobs_fn,
    scan_pending_chat_jobs_fn,
    start_fn,
    stop_fn,
):
    return InlineQueueBackend(
        enqueue_upload_job_fn=enqueue_upload_job_fn,
        enqueue_exam_job_fn=enqueue_exam_job_fn,
        enqueue_profile_update_fn=enqueue_profile_update_fn,
        enqueue_chat_job_fn=enqueue_chat_job_fn,
        scan_pending_upload_jobs_fn=scan_pending_upload_jobs_fn,
        scan_pending_exam_jobs_fn=scan_pending_exam_jobs_fn,
        scan_pending_chat_jobs_fn=scan_pending_chat_jobs_fn,
        start_fn=start_fn,
        stop_fn=stop_fn,
    )
```

- Update `app_core.py` to remove `enqueue_*`, `scan_pending_*`, and chat worker wrapper functions. Replace call sites in deps builders to call `runtime.queue_runtime` with a backend from `app_queue_backend`.

- Update tests to patch `services.api.workers.chat_worker_service` and to set worker-started flags via `app_mod.CHAT_JOB_WORKER_STARTED`.

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest /Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_chat_job_flow.py -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/services/api/runtime/queue_runtime.py \
  /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/services/api/app_core.py \
  /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_chat_job_flow.py \
  /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_student_history_flow.py \
  /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_chat_lane_queue.py \
  /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_chat_status_flow.py

git commit -m "refactor: move chat queue/worker wrappers out of app_core"
```

---

### Task 6: Move runtime lifecycle (lifespan/start/stop) out of app_core

**Files:**
- Create: `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/runtime/lifecycle.py`
- Create: `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/runtime/bootstrap.py`
- Modify: `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/app.py`
- Modify: `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/app_core.py`
- Modify: `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/tenant_app_factory.py`
- Modify: `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_app_queue_backend_mode.py`

**Step 1: Write the failing test**

Update `test_app_queue_backend_mode.py` to patch the new lifecycle entrypoint:

```python
# /Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_app_queue_backend_mode.py
from services.api.runtime import lifecycle

monkeypatch.setattr(lifecycle, "start_inline_workers", fake_start, raising=False)
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest /Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_app_queue_backend_mode.py -v`

Expected: ImportError or missing lifecycle module.

**Step 3: Write minimal implementation**

Create a lifecycle module that owns app lifespan and inline worker start/stop orchestration:

```python
# /Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/runtime/lifecycle.py
from __future__ import annotations

from contextlib import asynccontextmanager

from services.api.runtime.bootstrap import start_runtime, stop_runtime


@asynccontextmanager
async def app_lifespan(_app):
    start_runtime()
    try:
        yield
    finally:
        stop_runtime()
```

Add a bootstrap module that wires default deps (no app_core wrappers):

```python
# /Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/runtime/bootstrap.py
from services.api import settings
from services.api.runtime.runtime_manager import RuntimeManagerDeps, start_tenant_runtime, stop_tenant_runtime
from services.api.runtime.inline_backend_factory import build_inline_backend
from services.api.teacher_provider_registry_service import validate_master_key_policy
from services.api.workers import chat_worker_service, exam_worker_service, profile_update_worker_service, upload_worker_service
from services.api.workers.inline_runtime import start_inline_workers, stop_inline_workers
from services.api import app_core as app_mod


def _inline_backend_factory():
    upload_deps = app_mod.upload_worker_deps()
    exam_deps = app_mod.exam_worker_deps()
    profile_deps = app_mod.profile_update_worker_deps()
    chat_deps = app_mod.chat_worker_deps()
    return build_inline_backend(
        enqueue_upload_job_fn=lambda job_id: upload_worker_service.enqueue_upload_job_inline(job_id, deps=upload_deps),
        enqueue_exam_job_fn=lambda job_id: exam_worker_service.enqueue_exam_job_inline(job_id, deps=exam_deps),
        enqueue_profile_update_fn=lambda payload: profile_update_worker_service.enqueue_profile_update_inline(payload, deps=profile_deps),
        enqueue_chat_job_fn=lambda job_id, lane_id=None: chat_worker_service.enqueue_chat_job(job_id, deps=chat_deps, lane_id=lane_id),
        scan_pending_upload_jobs_fn=lambda: upload_worker_service.scan_pending_upload_jobs_inline(deps=upload_deps),
        scan_pending_exam_jobs_fn=lambda: exam_worker_service.scan_pending_exam_jobs_inline(deps=exam_deps),
        scan_pending_chat_jobs_fn=lambda: chat_worker_service.scan_pending_chat_jobs(deps=chat_deps),
        start_fn=lambda: start_inline_workers(
            upload_deps=upload_deps,
            exam_deps=exam_deps,
            profile_deps=profile_deps,
            chat_deps=chat_deps,
            profile_update_async=app_mod.PROFILE_UPDATE_ASYNC,
        ),
        stop_fn=lambda: stop_inline_workers(
            upload_deps=upload_deps,
            exam_deps=exam_deps,
            profile_deps=profile_deps,
            chat_deps=chat_deps,
            profile_update_async=app_mod.PROFILE_UPDATE_ASYNC,
        ),
    )


def start_runtime() -> None:
    deps = RuntimeManagerDeps(
        tenant_id=app_mod.TENANT_ID or None,
        is_pytest=settings.is_pytest(),
        validate_master_key_policy=validate_master_key_policy,
        inline_backend_factory=_inline_backend_factory,
    )
    start_tenant_runtime(deps=deps)


def stop_runtime() -> None:
    deps = RuntimeManagerDeps(
        tenant_id=app_mod.TENANT_ID or None,
        is_pytest=settings.is_pytest(),
        validate_master_key_policy=validate_master_key_policy,
        inline_backend_factory=_inline_backend_factory,
    )
    stop_tenant_runtime(deps=deps)
```

Update `services/api/app.py` to use the new lifespan:

```python
from services.api.runtime.lifecycle import app_lifespan
app = FastAPI(title="Physics Agent API", version="0.2.0", lifespan=app_lifespan)
```

Remove `_app_lifespan`, `start_tenant_runtime`, `stop_tenant_runtime`, `_start_inline_workers`, `_stop_inline_workers` from `app_core.py`.

Update `tenant_app_factory.py` to call `services.api.runtime.runtime_manager.start_tenant_runtime` directly instead of module attributes.

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest /Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_app_queue_backend_mode.py -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/services/api/runtime/lifecycle.py \
  /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/services/api/app.py \
  /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/services/api/app_core.py \
  /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/services/api/tenant_app_factory.py \
  /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_app_queue_backend_mode.py

git commit -m "refactor: move runtime lifecycle out of app_core"
```

---

### Task 7: Cleanup app_core and run regression

**Files:**
- Modify: `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/services/api/app_core.py`
- Modify: `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_student_history_flow.py`
- Modify: `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_chat_job_flow.py`
- Modify: `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_chat_lane_queue.py`
- Modify: `/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_chat_status_flow.py`

**Step 1: Write the failing test**

Add a guard test to assert `app_core` no longer exports runtime/worker wrappers:

```python
# /Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_app_core_surface.py
import services.api.app as app_mod


def test_app_core_does_not_export_worker_wrappers():
    assert not hasattr(app_mod, "start_chat_worker")
    assert not hasattr(app_mod, "start_upload_worker")
    assert not hasattr(app_mod, "start_exam_upload_worker")
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest /Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_app_core_surface.py -v`

Expected: FAIL until wrappers are removed.

**Step 3: Write minimal implementation**

- Remove leftover runtime/queue/worker wrapper functions and imports from `app_core.py`.
- Update any remaining call sites to use `services.api.runtime` or `services.api.workers` modules.

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest /Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_app_core_surface.py -v`

Expected: PASS.

**Step 5: Full regression**

Run:

`python3 -m pytest /Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_settings.py \
/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_runtime_state.py \
/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_queue_runtime.py \
/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_assignment_io_handlers.py \
/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_app_queue_backend_mode.py \
/Users/lvxiaoer/Documents/New project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_tenant_admin_and_dispatcher.py -v`

Expected: PASS.

**Step 6: Commit**

```bash
git add /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/services/api/app_core.py \
  /Users/lvxiaoer/Documents/New\ project/.worktrees/codex/runtime-queue-worker-extraction/tests/test_app_core_surface.py

git commit -m "refactor: remove runtime/queue/worker surface from app_core"
```
