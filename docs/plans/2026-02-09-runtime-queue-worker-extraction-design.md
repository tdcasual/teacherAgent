# Runtime/Queue/Worker Extraction Design

**Goal:** Fully remove runtime, queue, and worker orchestration from `services/api/app_core.py` and relocate it into dedicated packages with clear ownership, while updating all call sites to the new modules (no compatibility wrappers).

## Scope
- Extract runtime lifecycle (tenant start/stop, inline vs RQ selection) into `services/api/runtime/`.
- Extract queue backend selection/caching into `services/api/queue/`.
- Extract all worker loops and worker start/stop controls into `services/api/workers/`.
- Remove runtime/queue/worker functions and globals from `app_core.py`.
- Update imports in API handlers, services, tests, and tenant bootstrapping.

## Non-Goals
- No behavior changes to job processing logic.
- No new queue backend implementation.
- No new worker types.

## Module Boundaries
- **runtime/**
  - `runtime_manager.py`: owns `start_tenant_runtime` / `stop_tenant_runtime` and decides inline vs RQ.
  - `runtime_state.py`: holds shared runtime state (chat lane store, semaphores, idempotency store).
  - `queue_runtime.py`: utility entrypoints for enqueue/scan/start/stop that are runtime-aware.
- **queue/**
  - `queue_backend.py`: interface + base helpers.
  - `queue_backend_rq.py`: RQ implementation.
  - `queue_inline_backend.py`: inline backend wrapper.
  - `queue_backend_factory.py`: caching + selection logic.
- **workers/**
  - `chat_worker_service.py`, `rq_worker.py`, and upload/exam/profile worker loops.
  - start/stop functions live here, not in `app_core.py`.

## Data Flow (Runtime + Queue + Worker)
1. API handler calls `queue_runtime.enqueue_*` or `queue_backend_factory.get_app_queue_backend`.
2. `runtime_manager` decides inline vs RQ at startup and initializes queue backend.
3. `workers/*` modules execute job loops; domain services remain unchanged.
4. `runtime_state` provides shared resources (lane store, semaphores, idempotency store).

## Error Handling
- `queue_backend_factory` raises clear initialization errors; `runtime_manager` logs and fails fast or degrades based on configuration.
- Worker loops are resilient (single-job failure updates job status, does not terminate the worker).
- Start/stop are idempotent and safe to call repeatedly.

## Migration Plan
1. Create `runtime/`, `queue/`, `workers/` packages and move existing modules into them.
2. Update imports across services, handlers, tests, and app startup to new module paths.
3. Remove runtime/queue/worker functions and globals from `app_core.py`.
4. Ensure tests do not import runtime/queue/worker via `app_core.py`.

## Testing Plan
- Unit tests for queue backend factory caching/reset and inline/RQ selection.
- Runtime manager tests for pytest vs non-pytest paths (inline vs RQ).
- Worker start/stop idempotency tests.
- Integration tests to confirm handlers use new modules (no app_core wrappers).
- Full `python3 -m pytest -v` regression.

## Risks and Mitigations
- **Risk:** Broken imports after file moves. **Mitigation:** incremental refactor + focused import tests.
- **Risk:** Runtime start/stop order regressions. **Mitigation:** add tests for lifecycle ordering.
- **Risk:** Hidden app_core dependencies. **Mitigation:** ripgrep sweep and add guard tests.
