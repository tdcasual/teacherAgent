# API Composition Root Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make `services/api/app.py` a true composition root by removing inline workers and in-process queues, enforcing RQ+Redis, and extracting HTTP routing into router modules while preserving existing job/status contracts.

**Architecture:** API only wires routers/deps and performs sync request handling (write job.json + enqueue). Workers handle all async processing via RQ and Redis-backed lane serialisation. Multi-tenant dispatcher remains, but tenant startup never starts workers.

**Tech Stack:** FastAPI, RQ, Redis, pytest.

---

### Task 1: Enforce RQ-only backend and hard-fail without Redis

**Files:**
- Modify: `services/api/queue_backend.py`
- Modify: `services/api/rq_tasks.py`
- Test: `tests/test_queue_backend_selection.py`
- Test: `tests/test_app_queue_backend_mode.py`

**Step 1: Write the failing test**

Add to `tests/test_queue_backend_selection.py`:
```python
def test_rq_required_when_no_inline_backend(monkeypatch):
    monkeypatch.delenv("RQ_BACKEND_ENABLED", raising=False)
    monkeypatch.delenv("JOB_QUEUE_BACKEND", raising=False)
    from services.api import queue_backend
    try:
        queue_backend.get_queue_backend(tenant_id=None, inline_backend=None)
    except RuntimeError as exc:
        assert "rq" in str(exc).lower()
    else:
        assert False, "expected RuntimeError when rq not enabled"
```

Add to `tests/test_app_queue_backend_mode.py`:
```python
def test_rq_required_in_api_startup(monkeypatch):
    monkeypatch.delenv("RQ_BACKEND_ENABLED", raising=False)
    monkeypatch.delenv("JOB_QUEUE_BACKEND", raising=False)
    from services.api import app as app_mod
    try:
        app_mod.start_tenant_runtime()
    except RuntimeError as exc:
        assert "rq" in str(exc).lower()
    else:
        assert False, "expected RuntimeError when rq not enabled"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_queue_backend_selection.py::test_rq_required_when_no_inline_backend -q`
Expected: FAIL (no RuntimeError yet)

Run: `pytest tests/test_app_queue_backend_mode.py::test_rq_required_in_api_startup -q`
Expected: FAIL

**Step 3: Write minimal implementation**

In `services/api/queue_backend.py`:
- Remove inline fallback when RQ not enabled.
- Raise `RuntimeError("RQ backend required")` if `rq_enabled()` is false.

In `services/api/rq_tasks.py`:
- Validate `REDIS_URL` is set and `get_redis_client` can connect (ping) before enqueue/worker start.
- Raise `RuntimeError("Redis required")` on failure.

In `services/api/app.py` (temporarily; final split in later tasks):
- Update `start_tenant_runtime()` to call a new `require_rq_backend()` helper which raises on missing RQ/Redis.

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_queue_backend_selection.py::test_rq_required_when_no_inline_backend -q`
Expected: PASS

Run: `pytest tests/test_app_queue_backend_mode.py::test_rq_required_in_api_startup -q`
Expected: PASS

**Step 5: Commit**

```bash
git add services/api/queue_backend.py services/api/rq_tasks.py services/api/app.py tests/test_queue_backend_selection.py tests/test_app_queue_backend_mode.py
git commit -m "feat(api): require rq+redis backend"
```

---

### Task 2: Remove inline worker startup from API lifespan

**Files:**
- Modify: `services/api/app.py`
- Test: `tests/test_app_queue_backend_mode.py`

**Step 1: Write the failing test**

Add to `tests/test_app_queue_backend_mode.py`:
```python
def test_lifespan_does_not_start_workers(monkeypatch):
    from services.api import app as app_mod
    called = {"start": 0}
    def fake_start():
        called["start"] += 1
    monkeypatch.setattr(app_mod, "_start_inline_workers", fake_start, raising=False)
    # simulate lifespan start/stop
    import asyncio
    async def run():
        async with app_mod._app_lifespan(app_mod.app):
            pass
    asyncio.run(run())
    assert called["start"] == 0
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_app_queue_backend_mode.py::test_lifespan_does_not_start_workers -q`
Expected: FAIL (lifespan still starts workers)

**Step 3: Write minimal implementation**

In `services/api/app.py`:
- Remove `_start_inline_workers` and `_stop_inline_workers` usage from `start_tenant_runtime` and lifespan.
- Ensure `start_tenant_runtime()` only validates backend and does not start any worker threads.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_app_queue_backend_mode.py::test_lifespan_does_not_start_workers -q`
Expected: PASS

**Step 5: Commit**

```bash
git add services/api/app.py tests/test_app_queue_backend_mode.py
git commit -m "refactor(api): remove inline worker startup"
```

---

### Task 3: Make chat lane serialisation Redis-only

**Files:**
- Modify: `services/api/app.py`
- Modify: `services/api/chat_redis_lane_store.py`
- Test: `tests/test_chat_lane_store_memory.py`

**Step 1: Write the failing test**

Update `tests/test_chat_lane_store_memory.py` to expect no in-memory fallback:
```python
def test_chat_lane_store_requires_redis(monkeypatch):
    from services.api import app as app_mod
    monkeypatch.setattr(app_mod, "_rq_enabled", lambda: True)
    store = app_mod._chat_lane_store()
    assert store is not None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_chat_lane_store_memory.py::test_chat_lane_store_requires_redis -q`
Expected: FAIL if still using memory fallback

**Step 3: Write minimal implementation**

In `services/api/app.py`:
- Remove in-memory lane maps and code paths guarded by `_rq_enabled()`.
- Always use `ChatRedisLaneStore` for lane load/enqueue/finish.

In `services/api/chat_redis_lane_store.py`:
- Ensure redis client errors are surfaced clearly.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_chat_lane_store_memory.py::test_chat_lane_store_requires_redis -q`
Expected: PASS

**Step 5: Commit**

```bash
git add services/api/app.py services/api/chat_redis_lane_store.py tests/test_chat_lane_store_memory.py
git commit -m "refactor(chat): redis-only lane store"
```

---

### Task 4: Extract routers and slim app.py to composition root

**Files:**
- Create: `services/api/routers/health.py`
- Create: `services/api/routers/exam.py`
- Create: `services/api/routers/assignment.py`
- Create: `services/api/routers/chat.py`
- Create: `services/api/routers/profile.py`
- Create: `services/api/routers/uploads.py`
- Create: `services/api/routers/tenant_admin.py`
- Modify: `services/api/app.py`
- Modify: `services/api/app_routes.py` (or remove if replaced)
- Test: `tests/test_app_routes_registration.py`

**Step 1: Write the failing test**

Update `tests/test_app_routes_registration.py`:
```python
def test_health_router_included():
    from services.api import app as app_mod
    from fastapi.testclient import TestClient
    client = TestClient(app_mod.app)
    res = client.get("/health")
    assert res.status_code == 200
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_app_routes_registration.py::test_health_router_included -q`
Expected: FAIL after removing old route registration

**Step 3: Write minimal implementation**

- Move route functions from `app.py` into router modules grouped by domain.
- In each router module, create `router = APIRouter()` and attach route handlers.
- Keep handlers thin: parse/validate, save uploads, write job.json, enqueue, return response.
- In `app.py`, include routers and wire deps only.
- Ensure dynamic tenant wiring remains at bottom.

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_app_routes_registration.py::test_health_router_included -q`
Expected: PASS

**Step 5: Commit**

```bash
git add services/api/app.py services/api/routers tests/test_app_routes_registration.py
git commit -m "refactor(api): extract routers and slim app"
```

---

### Task 5: Remove inline queue backend and update tests

**Files:**
- Modify: `services/api/queue_backend.py`
- Delete or isolate: `services/api/queue_backend_inline.py`
- Modify: `services/api/app.py`
- Update tests as needed

**Step 1: Write the failing test**

Add to `tests/test_queue_backend_selection.py`:
```python
def test_inline_backend_removed(monkeypatch):
    monkeypatch.setenv("JOB_QUEUE_BACKEND", "inline")
    from services.api import queue_backend
    try:
        queue_backend.get_queue_backend(tenant_id=None, inline_backend=None)
    except RuntimeError:
        pass
    else:
        assert False, "inline backend should be removed"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_queue_backend_selection.py::test_inline_backend_removed -q`
Expected: FAIL

**Step 3: Write minimal implementation**

- Remove inline backend selection entirely from `queue_backend.py`.
- Remove references in `app.py` to inline backend helpers.
- If `queue_backend_inline.py` is no longer used, delete it.

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_queue_backend_selection.py::test_inline_backend_removed -q`
Expected: PASS

**Step 5: Commit**

```bash
git add services/api/queue_backend.py services/api/app.py tests/test_queue_backend_selection.py
if [ -f services/api/queue_backend_inline.py ]; then git rm services/api/queue_backend_inline.py; fi
git commit -m "refactor(queue): remove inline backend"
```

---

### Task 6: Update docs & worker entry guidance

**Files:**
- Modify: `README.md`
- Modify: `services/api/requirements.txt` (if needed)

**Step 1: Write the failing test**

_No test required for docs._

**Step 2: Write minimal documentation**

- Document requirement: API must have `REDIS_URL` and `JOB_QUEUE_BACKEND=rq`.
- Provide worker startup command (`python -m services.api.rq_worker`).
- Mention RQ scan pending option (`RQ_SCAN_PENDING_ON_START=1`).

**Step 3: Commit**

```bash
git add README.md services/api/requirements.txt
git commit -m "docs: require rq+redis and worker startup"
```

---

**Plan complete.**
