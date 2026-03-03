# Runtime Decoupling Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove global singleton/runtime state coupling and make app/core/config/worker wiring instance-scoped, deterministic, and test-isolated.

**Architecture:** Replace module-level config/core singletons with explicit `AppSettings` + `CoreRuntime` instances created via app factory. Wire routes, services, and workers through constructor-injected deps instead of contextvar fallback. Keep runtime lifecycle per app instance and eliminate cross-test state bleed.

**Tech Stack:** FastAPI, Python dataclasses, existing wiring modules, pytest.

---

## Scope Policy

- No backward compatibility constraints.
- Prefer explicit construction over implicit global state.
- Remove legacy facades where they add coupling.

## Task 1: Introduce explicit runtime settings model

**Files:**
- Create: `services/api/runtime_settings.py`
- Modify: `services/api/settings.py`
- Modify: `services/api/config.py`
- Test: `tests/test_settings.py`

**Checklist:**
1. Add `AppSettings` dataclass for all env-driven values currently spread across `settings.py` and `config.py`.
2. Add `load_settings(env: Mapping[str, str] | None = None) -> AppSettings`.
3. Convert `config.py` from module-level constants to pure builders (e.g. `build_paths(settings)`).
4. Remove direct env reads from `config.py` module import path.
5. Add tests proving two different settings instances produce isolated `DATA_DIR/UPLOADS_DIR`.

## Task 2: Replace module-global core with instance core

**Files:**
- Create: `services/api/core_runtime.py`
- Modify: `services/api/app_core.py`
- Modify: `services/api/container.py`
- Test: `tests/test_app_container.py`

**Checklist:**
1. Define `CoreRuntime` object (or equivalent) encapsulating core state/resources.
2. Move mutable globals (queues/locks/cache/runtime flags) into `CoreRuntime` fields.
3. Keep pure utility functions in separate modules; avoid re-exporting via `app_core.py`.
4. Update container creation to accept and store a `CoreRuntime` instance.
5. Ensure each app instance gets a fresh core object.

## Task 3: Introduce app factory and kill singleton fallback logic

**Files:**
- Modify: `services/api/app.py`
- Modify: `services/api/runtime/lifecycle.py`
- Test: `tests/test_app_core_structure.py`
- Test: `tests/test_app_modularization_guardrails.py`

**Checklist:**
1. Add `create_app(settings: AppSettings) -> FastAPI`.
2. Remove `_APP_CORE`, `_DEFAULT_APP`, and `get_core()` fallback behavior.
3. Store `settings`, `core`, `container` in `app.state` only.
4. Ensure lifespan startup/bootstrap reads from `app.state.core` (instance-scoped).
5. Keep a minimal module-level `app = create_app(load_settings())` for runtime entrypoint only.

## Task 4: Remove contextvar-based core lookup from wiring path

**Files:**
- Modify: `services/api/wiring/__init__.py`
- Modify: `services/api/wiring/*.py`
- Modify: `services/api/app_routes.py`
- Test: `tests/test_chat_wiring_context.py`

**Checklist:**
1. Stop using `get_app_core()` for normal deps resolution.
2. Convert deps builders to accept `core` explicitly (`build_xxx_deps(core)`).
3. Update route registration to pass concrete deps built at app creation.
4. Keep contextvar only for request-scoped auth/request-id if needed; not for core transport.
5. Delete dead path that raises `CURRENT_CORE not set` for background operations.

## Task 5: Fix worker core propagation uniformly

**Files:**
- Modify: `services/api/wiring/worker_wiring.py`
- Modify: `services/api/workers/exam_worker_service.py`
- Modify: `services/api/workers/upload_worker_service.py`
- Modify: `services/api/workers/profile_update_worker_service.py`
- Test: `tests/test_exam_upload_flow.py`
- Test: `tests/test_chat_wiring_context.py`

**Checklist:**
1. Bind worker deps to explicit `core` instance at construction.
2. Remove implicit context lookups from worker thread code path.
3. Standardize thread factory wrappers (chat/upload/exam/profile) with identical context bootstrap semantics.
4. Add regression tests for worker-thread execution not requiring global context.

## Task 6: Remove underscore-export facade and tighten module boundaries

**Files:**
- Modify: `services/api/app_core.py`
- Modify: `services/api/app_core_wiring_exports.py`
- Modify: `tests/test_app_modularization_guardrails.py`

**Checklist:**
1. Stop dynamic wildcard-like export binding in `app_core.py`.
2. Replace underscore-prefixed dependency exposure with explicit public provider APIs.
3. Update guardrail tests to validate explicit provider interface, not hidden internals.
4. Remove dead compatibility symbols.

## Task 7: Restore deterministic chart/exam/auth behavior under test isolation

**Files:**
- Modify: `services/api/routes/misc_chart_routes.py`
- Modify: `services/api/auth_registry_service.py`
- Modify: `services/api/exam_utils.py`
- Test: `tests/test_chart_exec_tool.py`
- Test: `tests/test_auth_token_password_flow.py`
- Test: `tests/test_security_auth_hardening.py`
- Test: `tests/test_longform_exam_analysis.py`

**Checklist:**
1. Ensure all store/path functions receive instance `data_dir/uploads_dir` from core/settings, not cached globals.
2. Remove process-wide cache points that couple to first-loaded env.
3. Verify chart and auth endpoints resolve tmp paths in each test app instance.
4. Validate longform exam path sees per-test exam manifests consistently.

## Task 8: Fix strict typing and budget failures

**Files:**
- Modify: `services/api/exam_analysis_charts_service.py`
- Modify: `config/backend_quality_budget.json` (only if policy decision requires)
- Test: `tests/test_exam_analysis_charts_types.py`
- Test: `tests/test_backend_quality_budget_regression.py`

**Checklist:**
1. Fix mypy errors around `class_compare.sort` key typing and `no-redef`.
2. Keep quality budget strict; avoid raising threshold unless explicitly approved.
3. Re-run budget checker and verify mypy error count within budget.

## Task 9: Rework test app bootstrap into explicit fixture factory

**Files:**
- Create: `tests/helpers/app_factory.py`
- Modify: failing test files currently using per-file `load_app(...)`
- Test: full pytest suite

**Checklist:**
1. Replace repeated `importlib.reload(app_mod)` + env mutation pattern with fixture-level `create_test_app(settings_override)`.
2. Ensure each test gets isolated app/core instance.
3. Remove cross-file monkeypatch leakage by scoping patches to fixture/app instance.
4. Keep file-local helpers only for domain fixtures, not app bootstrap.

## Task 10: Verification and merge gate

**Files:**
- Modify: `docs/operations/change-management-and-governance.md` (if gate updates required)
- Test: full backend + frontend verify

**Checklist:**
1. Run `python3 -m pytest -q` with clean pass target.
2. Run `python3 scripts/quality/check_backend_quality_budget.py --print-only`.
3. Run `npm run verify` in `frontend`.
4. Add CI guard: fail if app factory isolation regression appears.

## Acceptance Criteria

- No module-level singleton core used for request/runtime logic.
- `DATA_DIR/UPLOADS_DIR` respected per app instance and per test fixture.
- Worker threads run without `CURRENT_CORE not set` failures.
- `test_app_modularization_guardrails`, `test_exam_upload_flow`, `test_assignment_progress`, `test_auth_token_password_flow`, `test_chart_exec_tool`, `test_longform_exam_analysis`, `test_security_auth_hardening` all pass.
- mypy budget back to threshold.
