# Stage 0 Runtime State & Settings Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Centralize API configuration in `settings.py`, extract resettable runtime state, and wire tenant resets to use the shared runtime state initializer with minimal regression tests.

**Architecture:** Introduce `runtime_state.py` to build/reset mutable globals for a module (queues, locks, caches, semaphores). `app_core.py` becomes a thin consumer of settings + runtime_state. `tenant_app_factory.py` calls `reset_runtime_state()` instead of manually reinitializing globals.

**Tech Stack:** Python 3.11, FastAPI, pytest/unittest

---

### Task 1: Centralize config accessors in settings

**Files:**
- Modify: `/Users/lvxiaoer/Documents/New project/services/api/settings.py`
- Modify: `/Users/lvxiaoer/Documents/New project/tests/test_settings.py`

**Step 1: Write failing test**

Update `/Users/lvxiaoer/Documents/New project/tests/test_settings.py` to assert defaults for new accessors:

```python
def test_settings_defaults_and_conversions(monkeypatch):
    monkeypatch.delenv("CHAT_WORKER_POOL_SIZE", raising=False)
    monkeypatch.delenv("TEACHER_MEMORY_AUTO_ENABLED", raising=False)
    monkeypatch.delenv("GRADE_COUNT_CONF_THRESHOLD", raising=False)
    monkeypatch.delenv("DEFAULT_TEACHER_ID", raising=False)

    from services.api import settings

    assert settings.chat_worker_pool_size() == 4
    assert settings.teacher_memory_auto_enabled() is True
    assert settings.grade_count_conf_threshold() == 0.6
    assert settings.default_teacher_id() == "teacher"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_settings.py::test_settings_defaults_and_conversions -v`
Expected: FAIL (missing accessor functions)

**Step 3: Implement accessors in settings.py**

Add helpers and accessors (explicit list below) in `/Users/lvxiaoer/Documents/New project/services/api/settings.py`:

```python
def env_int(name: str, default: int) -> int:
    return int(env_str(name, str(default)) or default)


def env_float(name: str, default: float) -> float:
    return float(env_str(name, str(default)) or default)


def env_bool(name: str, default: str = "") -> bool:
    return truthy(env_str(name, default))
```

Then implement accessors for every env read currently in `app_core.py`:

- `data_dir()` → `env_str("DATA_DIR", "")`
- `uploads_dir()` → `env_str("UPLOADS_DIR", "")`
- `llm_routing_path()` → `env_str("LLM_ROUTING_PATH", "")`
- `diag_log_enabled()` → `env_bool("DIAG_LOG", "")`
- `diag_log_path()` → `env_str("DIAG_LOG_PATH", "")`
- `chat_worker_pool_size()` → `max(1, env_int("CHAT_WORKER_POOL_SIZE", 4))`
- `chat_lane_max_queue()` → `max(1, env_int("CHAT_LANE_MAX_QUEUE", 6))`
- `chat_lane_debounce_ms()` → `max(0, env_int("CHAT_LANE_DEBOUNCE_MS", 500))`
- `chat_job_claim_ttl_sec()` → `max(10, env_int("CHAT_JOB_CLAIM_TTL_SEC", 600))`
- `session_index_max_items()` → `max(50, env_int("SESSION_INDEX_MAX_ITEMS", 500))`
- `teacher_session_compact_enabled()` → `env_bool("TEACHER_SESSION_COMPACT_ENABLED", "1")`
- `teacher_session_compact_main_only()` → `env_bool("TEACHER_SESSION_COMPACT_MAIN_ONLY", "1")`
- `teacher_session_compact_max_messages()` → `max(4, env_int("TEACHER_SESSION_COMPACT_MAX_MESSAGES", 160))`
- `teacher_session_compact_keep_tail(max_messages: int)` → clamp to `< max_messages` (same logic currently in app_core)
- `teacher_session_compact_min_interval_sec()` → `max(0, env_int("TEACHER_SESSION_COMPACT_MIN_INTERVAL_SEC", 60))`
- `teacher_session_compact_max_source_chars()` → `max(2000, env_int("TEACHER_SESSION_COMPACT_MAX_SOURCE_CHARS", 12000))`
- `teacher_session_context_include_summary()` → `env_bool("TEACHER_SESSION_CONTEXT_INCLUDE_SUMMARY", "1")`
- `teacher_session_context_summary_max_chars()` → `max(0, env_int("TEACHER_SESSION_CONTEXT_SUMMARY_MAX_CHARS", 1500))`
- `teacher_memory_auto_enabled()` → `env_bool("TEACHER_MEMORY_AUTO_ENABLED", "1")`
- `teacher_memory_auto_min_content_chars()` → `max(6, env_int("TEACHER_MEMORY_AUTO_MIN_CONTENT_CHARS", 12))`
- `teacher_memory_auto_max_proposals_per_day()` → `max(1, env_int("TEACHER_MEMORY_AUTO_MAX_PROPOSALS_PER_DAY", 8))`
- `teacher_memory_flush_enabled()` → `env_bool("TEACHER_MEMORY_FLUSH_ENABLED", "1")`
- `teacher_memory_flush_margin_messages()` → `max(1, env_int("TEACHER_MEMORY_FLUSH_MARGIN_MESSAGES", 24))`
- `teacher_memory_flush_max_source_chars()` → `max(500, env_int("TEACHER_MEMORY_FLUSH_MAX_SOURCE_CHARS", 2400))`
- `teacher_memory_auto_apply_enabled()` → `env_bool("TEACHER_MEMORY_AUTO_APPLY_ENABLED", "1")`
- `teacher_memory_auto_apply_targets_raw()` → `env_str("TEACHER_MEMORY_AUTO_APPLY_TARGETS", "DAILY,MEMORY")`
- `teacher_memory_auto_apply_strict()` → `env_bool("TEACHER_MEMORY_AUTO_APPLY_STRICT", "1")`
- `teacher_memory_auto_infer_enabled()` → `env_bool("TEACHER_MEMORY_AUTO_INFER_ENABLED", "1")`
- `teacher_memory_auto_infer_min_repeats()` → `max(2, env_int("TEACHER_MEMORY_AUTO_INFER_MIN_REPEATS", 2))`
- `teacher_memory_auto_infer_lookback_turns()` → `max(4, min(80, env_int("TEACHER_MEMORY_AUTO_INFER_LOOKBACK_TURNS", 24)))`
- `teacher_memory_auto_infer_min_chars()` → `max(8, env_int("TEACHER_MEMORY_AUTO_INFER_MIN_CHARS", 16))`
- `teacher_memory_auto_infer_min_priority()` → `max(0, min(100, env_int("TEACHER_MEMORY_AUTO_INFER_MIN_PRIORITY", 58)))`
- `teacher_memory_decay_enabled()` → `env_bool("TEACHER_MEMORY_DECAY_ENABLED", "1")`
- `teacher_memory_ttl_days_memory()` → `max(0, env_int("TEACHER_MEMORY_TTL_DAYS_MEMORY", 180))`
- `teacher_memory_ttl_days_daily()` → `max(0, env_int("TEACHER_MEMORY_TTL_DAYS_DAILY", 14))`
- `teacher_memory_context_max_entries()` → `max(4, env_int("TEACHER_MEMORY_CONTEXT_MAX_ENTRIES", 18))`
- `teacher_memory_search_filter_expired()` → `env_bool("TEACHER_MEMORY_SEARCH_FILTER_EXPIRED", "1")`
- `discussion_complete_marker()` → `env_str("DISCUSSION_COMPLETE_MARKER", "【个性化作业】")`
- `grade_count_conf_threshold()` → `env_float("GRADE_COUNT_CONF_THRESHOLD", 0.6)`
- `ocr_max_concurrency()` → `max(1, env_int("OCR_MAX_CONCURRENCY", 4))`
- `llm_max_concurrency()` → `max(1, env_int("LLM_MAX_CONCURRENCY", 8))`
- `llm_max_concurrency_student(total: int)` → `max(1, env_int("LLM_MAX_CONCURRENCY_STUDENT", total))`
- `llm_max_concurrency_teacher(total: int)` → `max(1, env_int("LLM_MAX_CONCURRENCY_TEACHER", total))`
- `chat_max_messages()` → `max(4, env_int("CHAT_MAX_MESSAGES", 14))`
- `chat_max_messages_student(base: int)` → `max(4, env_int("CHAT_MAX_MESSAGES_STUDENT", max(base, 40)))`
- `chat_max_messages_teacher(base: int)` → `max(4, env_int("CHAT_MAX_MESSAGES_TEACHER", max(base, 40)))`
- `chat_max_message_chars()` → `max(256, env_int("CHAT_MAX_MESSAGE_CHARS", 2000))`
- `chat_extra_system_max_chars()` → `max(512, env_int("CHAT_EXTRA_SYSTEM_MAX_CHARS", 6000))`
- `chat_max_tool_rounds()` → `max(1, env_int("CHAT_MAX_TOOL_ROUNDS", 5))`
- `chat_max_tool_calls()` → `max(1, env_int("CHAT_MAX_TOOL_CALLS", 12))`
- `chat_student_inflight_limit()` → `max(1, env_int("CHAT_STUDENT_INFLIGHT_LIMIT", 1))`
- `profile_cache_ttl_sec()` → `max(0, env_int("PROFILE_CACHE_TTL_SEC", 10))`
- `assignment_detail_cache_ttl_sec()` → `max(0, env_int("ASSIGNMENT_DETAIL_CACHE_TTL_SEC", 10))`
- `profile_update_async()` → `env_bool("PROFILE_UPDATE_ASYNC", "1")`
- `profile_update_queue_max()` → `max(10, env_int("PROFILE_UPDATE_QUEUE_MAX", 500))`
- `default_teacher_id()` → `env_str("DEFAULT_TEACHER_ID", "teacher")`
- `is_pytest()` → `bool(os.getenv("PYTEST_CURRENT_TEST"))`

**Step 4: Run tests to verify pass**

Run: `pytest tests/test_settings.py::test_settings_defaults_and_conversions -v`
Expected: PASS

**Step 5: Commit**

```bash
git add /Users/lvxiaoer/Documents/New\ project/services/api/settings.py \
  /Users/lvxiaoer/Documents/New\ project/tests/test_settings.py
git commit -m "refactor: add settings accessors for runtime config"
```

---

### Task 2: Add runtime_state module + tests

**Files:**
- Create: `/Users/lvxiaoer/Documents/New project/services/api/runtime_state.py`
- Create: `/Users/lvxiaoer/Documents/New project/tests/test_runtime_state.py`

**Step 1: Write failing test**

Create `/Users/lvxiaoer/Documents/New project/tests/test_runtime_state.py`:

```python
from types import SimpleNamespace
from collections import deque
from pathlib import Path

from services.api import runtime_state


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

    mod.UPLOAD_JOB_QUEUE = deque(["old"])  # prove reset clears
    runtime_state.reset_runtime_state(mod, create_chat_idempotency_store=lambda _: object())

    assert list(mod.UPLOAD_JOB_QUEUE) == []
    assert isinstance(mod.UPLOAD_JOB_LOCK, object)
    assert mod._QUEUE_BACKEND is None
    assert mod.CHAT_IDEMPOTENCY_STATE is not None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_runtime_state.py::test_reset_runtime_state_resets_queues_and_caches -v`
Expected: FAIL (module/function missing)

**Step 3: Implement runtime_state.reset_runtime_state**

Create `/Users/lvxiaoer/Documents/New project/services/api/runtime_state.py`:

```python
from __future__ import annotations

from collections import deque
import threading
from typing import Any, Dict, List, Optional, Tuple


def reset_runtime_state(mod: Any, *, create_chat_idempotency_store) -> None:
    mod.UPLOAD_JOB_QUEUE = deque()
    mod.UPLOAD_JOB_LOCK = threading.Lock()
    mod.UPLOAD_JOB_EVENT = threading.Event()
    mod.UPLOAD_JOB_WORKER_STARTED = False
    mod.UPLOAD_JOB_STOP_EVENT = threading.Event()
    mod.UPLOAD_JOB_WORKER_THREAD = None

    mod.EXAM_JOB_QUEUE = deque()
    mod.EXAM_JOB_LOCK = threading.Lock()
    mod.EXAM_JOB_EVENT = threading.Event()
    mod.EXAM_JOB_WORKER_STARTED = False
    mod.EXAM_JOB_STOP_EVENT = threading.Event()
    mod.EXAM_JOB_WORKER_THREAD = None

    mod.CHAT_JOB_LOCK = threading.Lock()
    mod.CHAT_JOB_EVENT = threading.Event()
    mod.CHAT_JOB_WORKER_STARTED = False
    mod.CHAT_WORKER_STOP_EVENT = threading.Event()
    mod.CHAT_JOB_LANES = {}
    mod.CHAT_JOB_ACTIVE_LANES = set()
    mod.CHAT_JOB_QUEUED = set()
    mod.CHAT_JOB_TO_LANE = {}
    mod.CHAT_LANE_CURSOR = 0
    mod.CHAT_WORKER_THREADS = []
    mod.CHAT_LANE_RECENT = {}
    mod.CHAT_IDEMPOTENCY_STATE = create_chat_idempotency_store(mod.CHAT_JOB_DIR)
    mod._CHAT_LANE_STORES = {}
    mod._QUEUE_BACKEND = None

    mod._OCR_SEMAPHORE = threading.BoundedSemaphore(int(mod.OCR_MAX_CONCURRENCY))
    mod._LLM_SEMAPHORE = threading.BoundedSemaphore(int(mod.LLM_MAX_CONCURRENCY))
    mod._LLM_SEMAPHORE_STUDENT = threading.BoundedSemaphore(int(mod.LLM_MAX_CONCURRENCY_STUDENT))
    mod._LLM_SEMAPHORE_TEACHER = threading.BoundedSemaphore(int(mod.LLM_MAX_CONCURRENCY_TEACHER))

    mod._STUDENT_INFLIGHT = {}
    mod._STUDENT_INFLIGHT_LOCK = threading.Lock()

    mod._PROFILE_CACHE = {}
    mod._PROFILE_CACHE_LOCK = threading.Lock()
    mod._ASSIGNMENT_DETAIL_CACHE = {}
    mod._ASSIGNMENT_DETAIL_CACHE_LOCK = threading.Lock()

    mod._PROFILE_UPDATE_QUEUE = deque()
    mod._PROFILE_UPDATE_LOCK = threading.Lock()
    mod._PROFILE_UPDATE_EVENT = threading.Event()
    mod._PROFILE_UPDATE_WORKER_STARTED = False
    mod._PROFILE_UPDATE_STOP_EVENT = threading.Event()
    mod._PROFILE_UPDATE_WORKER_THREAD = None

    mod._TEACHER_SESSION_COMPACT_TS = {}
    mod._TEACHER_SESSION_COMPACT_LOCK = threading.Lock()
    mod._SESSION_INDEX_LOCKS = {}
    mod._SESSION_INDEX_LOCKS_LOCK = threading.Lock()
```

**Step 4: Run tests to verify pass**

Run: `pytest tests/test_runtime_state.py::test_reset_runtime_state_resets_queues_and_caches -v`
Expected: PASS

**Step 5: Commit**

```bash
git add /Users/lvxiaoer/Documents/New\ project/services/api/runtime_state.py \
  /Users/lvxiaoer/Documents/New\ project/tests/test_runtime_state.py
git commit -m "refactor: add runtime state reset helper"
```

---

### Task 3: Wire settings + runtime_state into app_core

**Files:**
- Modify: `/Users/lvxiaoer/Documents/New project/services/api/app_core.py`

**Step 1: Write failing test (reuse)**

No new test file needed; rely on existing settings/runtime_state tests + tenant tests to catch regressions.

**Step 2: Update config reads to use settings accessors**

Replace all `os.getenv(...)` config reads in the global config block with `settings` calls. Example pattern:

```python
DATA_DIR = Path(_settings.data_dir() or (APP_ROOT / "data"))
UPLOADS_DIR = Path(_settings.uploads_dir() or (APP_ROOT / "uploads"))
LLM_ROUTING_PATH = Path(_settings.llm_routing_path() or (DATA_DIR / "llm_routing.json"))
DIAG_LOG_ENABLED = _settings.diag_log_enabled()
DIAG_LOG_PATH = Path(_settings.diag_log_path() or (APP_ROOT / "tmp" / "diagnostics.log"))
CHAT_WORKER_POOL_SIZE = _settings.chat_worker_pool_size()
...
PROFILE_UPDATE_QUEUE_MAX = _settings.profile_update_queue_max()
```

For derived values:
- Use `total = _settings.llm_max_concurrency()` then `LLM_MAX_CONCURRENCY_STUDENT = _settings.llm_max_concurrency_student(total)`
- Use `base = _settings.chat_max_messages()` then student/teacher from that base
- Use `max_msgs = _settings.teacher_session_compact_max_messages()` then keep_tail via `teacher_session_compact_keep_tail(max_msgs)`
- For `TEACHER_MEMORY_AUTO_APPLY_TARGETS`, keep existing set construction using `_settings.teacher_memory_auto_apply_targets_raw()`

**Step 3: Replace PYTEST env checks**

Introduce `if _settings.is_pytest():` wherever `os.getenv("PYTEST_CURRENT_TEST")` is used in `app_core.py` (queue backend selection, chat lane store, etc.).

**Step 4: Initialize runtime state**

After config values are defined in `app_core.py`, import and call `reset_runtime_state`:

```python
from .runtime_state import reset_runtime_state as _reset_runtime_state

_reset_runtime_state(sys.modules[__name__], create_chat_idempotency_store=create_chat_idempotency_store)
```

**Step 5: Run tests to verify pass**

Run:
- `pytest tests/test_settings.py::test_settings_defaults_and_conversions -v`
- `pytest tests/test_runtime_state.py::test_reset_runtime_state_resets_queues_and_caches -v`
- `pytest tests/test_app_queue_backend_mode.py::test_rq_required_in_api_startup -v`
- `pytest tests/test_tenant_admin_and_dispatcher.py::test_tenant_unload_stops_chat_workers -v`

Expected: PASS

**Step 6: Commit**

```bash
git add /Users/lvxiaoer/Documents/New\ project/services/api/app_core.py
git commit -m "refactor: centralize config and initialize runtime state"
```

---

### Task 4: Use runtime_state reset in tenant_app_factory

**Files:**
- Modify: `/Users/lvxiaoer/Documents/New project/services/api/tenant_app_factory.py`

**Step 1: Write failing test (optional)**

If needed, add a narrow assertion to existing tenant tests verifying state resets (e.g., `_QUEUE_BACKEND` is None after tenant creation). Otherwise rely on existing tenant tests.

**Step 2: Replace manual reset with runtime_state.reset_runtime_state**

In `_configure_module_for_tenant`, after setting data/paths and config values, call:

```python
from .runtime_state import reset_runtime_state

reset_runtime_state(mod, create_chat_idempotency_store=idempotency_factory)
```

Then remove the duplicated manual reset block for queues/locks/caches/threads to avoid drift.

**Step 3: Run tests to verify pass**

Run:
- `pytest tests/test_tenant_admin_and_dispatcher.py::test_tenant_unload_stops_chat_workers -v`

Expected: PASS

**Step 4: Commit**

```bash
git add /Users/lvxiaoer/Documents/New\ project/services/api/tenant_app_factory.py
git commit -m "refactor: reset tenant runtime state via runtime_state"
```

---

### Task 5: Full regression sweep (best effort)

**Files:**
- None

**Step 1: Run core tests**

Run: `pytest tests/test_settings.py tests/test_runtime_state.py tests/test_app_queue_backend_mode.py tests/test_tenant_admin_and_dispatcher.py -v`
Expected: PASS

**Step 2: Commit (if any test-only tweaks)**

```bash
git status -sb
```

---

Plan complete and saved to `/Users/lvxiaoer/Documents/New project/.worktrees/codex/stage0-runtime-state/docs/plans/2026-02-08-stage0-runtime-state-settings.md`.

Two execution options:

1. Subagent-Driven (this session) — I dispatch a fresh subagent per task and review between tasks
2. Parallel Session (separate) — Open a new session using executing-plans and run the plan step-by-step

Which approach?
