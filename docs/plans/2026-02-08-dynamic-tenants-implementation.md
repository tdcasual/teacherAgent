# Dynamic Tenants (In-Process) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add dynamic in-process multi-tenancy to the API so one Python process can serve multiple isolated tenants via `/t/{tenant_id}/...`, with tenant configs managed at runtime via `/admin/tenants/...` protected by `X-Admin-Key`.

**Architecture:** Introduce a root ASGI dispatcher (`services/api/app.py:app`) that:
1) routes `/admin/tenants/...` to an admin router (root-only),
2) routes `/t/{tenant_id}/...` to a per-tenant FastAPI app created on-demand,
3) routes all non-`/t/` traffic to a default tenant app (backward compatible).

Tenant apps are created by `create_tenant_app(settings, global_limits)` and MUST isolate:
- `DATA_DIR` / `UPLOADS_DIR` (filesystem),
- queues, locks, caches, inflight counters,
- background workers (chat/upload/exam/profile update).

Concurrency limits are enforced as: **tenant semaphores → global semaphores** (fixed ordering to avoid deadlocks).
Tenant default limits:
- `llm_total=30`
- `llm_student=2`
- `llm_teacher=10`
- `ocr=5`

**Tech Stack:** Python 3.9, FastAPI / Starlette (ASGI), `sqlite3`, `pytest`.

---

## Preconditions

- Execute inside worktree: `/Users/lvxiaoer/Documents/New project/.worktrees/dynamic-tenants`.
- Set `API_WORKERS=1` for this in-process multi-tenant mode (multiple uvicorn workers would create multiple registries and break isolation).
- Set `TENANT_ADMIN_KEY` (required for any admin mutation endpoints).
- Set `TENANT_DB_PATH` (optional; default: `<repo>/data/_system/tenants.sqlite3`).

> Note: This plan includes “Commit” steps for humans; do not commit unless explicitly requested.

---

### Task 1: Add RED tests for tenant admin + dispatcher

**Files:**
- Create: `tests/test_tenant_admin_and_dispatcher.py`

**Step 1: Write the failing tests**

```python
import os
import importlib
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient


def load_app(tmp: Path, *, admin_key: str) -> object:
    os.environ["TENANT_ADMIN_KEY"] = admin_key
    os.environ["TENANT_DB_PATH"] = str(tmp / "tenants.sqlite3")
    os.environ["DIAG_LOG"] = "0"
    import services.api.app as app_mod
    importlib.reload(app_mod)
    return app_mod


def test_admin_requires_key():
    with TemporaryDirectory() as td:
        tmp = Path(td)
        app_mod = load_app(tmp, admin_key="k")
        client = TestClient(app_mod.app)
        res = client.put("/admin/tenants/t1", json={"data_dir": str(tmp / "t1_data"), "uploads_dir": str(tmp / "t1_up")})
        assert res.status_code == 401


def test_create_tenant_and_dispatch_health():
    with TemporaryDirectory() as td:
        tmp = Path(td)
        app_mod = load_app(tmp, admin_key="k")
        client = TestClient(app_mod.app)

        res = client.put(
            "/admin/tenants/t1",
            headers={"X-Admin-Key": "k"},
            json={"data_dir": str(tmp / "t1_data"), "uploads_dir": str(tmp / "t1_up")},
        )
        assert res.status_code == 200

        res2 = client.get("/t/t1/health")
        assert res2.status_code == 200
        assert res2.json().get("status") == "ok"


def test_tenant_data_dir_isolated_for_exams_list():
    with TemporaryDirectory() as td:
        tmp = Path(td)
        app_mod = load_app(tmp, admin_key="k")
        client = TestClient(app_mod.app)

        t1_data = tmp / "t1_data"
        t2_data = tmp / "t2_data"
        (t1_data / "exams" / "EX_T1").mkdir(parents=True)
        (t2_data / "exams" / "EX_T2").mkdir(parents=True)
        (t1_data / "exams" / "EX_T1" / "manifest.json").write_text('{"exam_id":"EX_T1"}', encoding="utf-8")
        (t2_data / "exams" / "EX_T2" / "manifest.json").write_text('{"exam_id":"EX_T2"}', encoding="utf-8")

        client.put("/admin/tenants/t1", headers={"X-Admin-Key": "k"}, json={"data_dir": str(t1_data), "uploads_dir": str(tmp / "t1_up")})
        client.put("/admin/tenants/t2", headers={"X-Admin-Key": "k"}, json={"data_dir": str(t2_data), "uploads_dir": str(tmp / "t2_up")})

        r1 = client.get("/t/t1/exams")
        r2 = client.get("/t/t2/exams")
        assert r1.status_code == 200 and r2.status_code == 200
        assert any(x.get("exam_id") == "EX_T1" for x in (r1.json().get("exams") or []))
        assert not any(x.get("exam_id") == "EX_T2" for x in (r1.json().get("exams") or []))
        assert any(x.get("exam_id") == "EX_T2" for x in (r2.json().get("exams") or []))
```

**Step 2: Run tests to verify RED**

Run: `python3 -m pytest -q tests/test_tenant_admin_and_dispatcher.py`  
Expected: FAIL (admin endpoints/dispatcher not implemented).

**Step 3: Commit (optional)**

```bash
git add tests/test_tenant_admin_and_dispatcher.py
git commit -m "test: specify tenant admin + dispatcher behavior"
```

---

### Task 2: Implement SQLite `TenantConfigStore`

**Files:**
- Create: `services/api/tenant_config_store.py`

**Step 1: Write failing unit tests (small)**

Create `tests/test_tenant_config_store.py` that covers:
- `upsert()` then `get()` returns config
- `delete()` makes `get()` return none
- `list()` returns all enabled tenants

**Step 2: Run to verify RED**

Run: `python3 -m pytest -q tests/test_tenant_config_store.py`  
Expected: FAIL (`ModuleNotFoundError`).

**Step 3: Minimal implementation**

Implementation requirements:
- Use `sqlite3` only (no external deps)
- Enable WAL mode (best-effort)
- Schema:
  - `tenant_id TEXT PRIMARY KEY`
  - `data_dir TEXT NOT NULL`
  - `uploads_dir TEXT NOT NULL`
  - `enabled INTEGER NOT NULL`
  - `updated_at TEXT NOT NULL`
  - `extra_json TEXT NOT NULL DEFAULT '{}'`

**Step 4: Verify GREEN**

Run: `python3 -m pytest -q tests/test_tenant_config_store.py`  
Expected: PASS.

---

### Task 3: Implement admin router (`/admin/tenants/...`) with `X-Admin-Key`

**Files:**
- Create: `services/api/tenant_admin_api.py`

**Behavior:**
- Reject if `TENANT_ADMIN_KEY` unset.
- Reject if header missing/mismatch (`401`).
- `PUT /admin/tenants/{tenant_id}`: upsert config; then `registry.replace(tenant_id)` so it’s immediately live.
- `GET /admin/tenants`: list configs (+ optionally loaded status).
- `DELETE /admin/tenants/{tenant_id}`: disable + unload.

**Step 1: Run Task 1 tests**

Run: `python3 -m pytest -q tests/test_tenant_admin_and_dispatcher.py::test_admin_requires_key`  
Expected: still FAIL until dispatcher wiring exists.

---

### Task 4: Add `TenantRegistry` + root ASGI dispatcher

**Files:**
- Create: `services/api/tenant_registry.py`
- Modify: `services/api/app.py` (become root entrypoint; preserve legacy exports used by tests)

**Minimal registry contract:**
- `get_or_create(tenant_id) -> TenantHandle`
- `replace(tenant_id) -> TenantHandle` (rebuild from latest config)
- `unload(tenant_id)` (stop workers, remove from memory)

**Dispatcher rules:**
- `/admin/...` handled by root admin app/router
- `/t/{tenant_id}/...` forwarded to tenant app with rewritten path
- everything else forwarded to default tenant (env-based) app

**Step 1: Run Task 1 tests to verify GREEN**

Run: `python3 -m pytest -q tests/test_tenant_admin_and_dispatcher.py`  
Expected: PASS for admin auth + `/t/{tenant}/health` + `/t/{tenant}/exams`.

---

### Task 5: Refactor tenant app construction (from singleton `services/api/app.py`)

**Files:**
- Create: `services/api/tenant_app_factory.py`
- Modify: `services/api/app.py` (move business/worker state out; leave as thin entrypoint + legacy convenience exports)

**Target:**
- `create_tenant_app(settings, *, global_limits) -> FastAPI`
- No module-level tenant state in `services/api/app.py` except the default singleton that wraps `create_tenant_app()`
- Tenant worker loops MUST support stop events so `unload()` is real (no orphan threads)

**Strategy:**
- Identify all module-level tenant state (queues/locks/caches/semaphores/logger/gateway) and move into a `TenantState` object.
- Update workers to loop while `not stop_event.is_set()` (exit cleanly after queue drain or after `stop_event`).
- Use existing service modules (`*_service.py`) via deps dataclasses; keep API response shapes unchanged.

**Verification:**
- Re-run existing app tests that import `services.api.app` (at least):
  - `python3 -m pytest -q tests/test_app_modularization_guardrails.py`
  - `python3 -m pytest -q tests/test_tool_registry_sync.py::ToolRegistrySyncTest::test_registry_covers_teacher_allowed_tools`

---

### Task 6: Enforce global + tenant concurrency limits

**Files:**
- Create: `services/api/global_limits.py`
- Modify: `services/api/tenant_app_factory.py` (wrap existing `_limit()` usage)

**Rules:**
- Always acquire in fixed order: tenant → global, and within each: total → role.
- Default tenant limits read from tenant config (defaults: `30/2/10/5`), global limits read from env (existing variables).

**Tests:**
- Add a small unit test that asserts acquisition ordering via a fake semaphore wrapper (no threads).

---

## Done Definition

- `/t/{tenant_id}/...` works for core endpoints (at least: `/health`, `/exams`).
- Tenants are created/updated/disabled only via `/admin/tenants/...` and require `X-Admin-Key`.
- Tenant `DATA_DIR/UPLOADS_DIR` are isolated per tenant.
- Tenant unload does not leak worker threads (stop works).
- Legacy behavior preserved for default tenant at root paths (no `/t/` prefix).
- Tests pass for both new tenant tests and key existing suites.

