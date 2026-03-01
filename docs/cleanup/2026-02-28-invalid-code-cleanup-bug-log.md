# Invalid Code Cleanup Bug Log (2026-02-28)

## Scope

- Track bugs discovered during invalid/dead code cleanup.
- Keep each entry reproducible with clear evidence and fix status.

## Entry Template

### BUG-XXXX: <short title>

- Discovered at: `<timestamp UTC>`
- Area: `<module/path>`
- Symptom: `<what failed>`
- Repro steps:
  1. `<step>`
  2. `<step>`
- Evidence:
  - `<command>`
  - `<error snippet>`
- Root cause: `<analysis>`
- Fix status: `open|fixed|wontfix`
- Notes: `<optional>`

## Entries

### BUG-0001: MCP JSON-RPC handler had mixed indentation in `core_example.register`

- Discovered at: `2026-02-28T12:38:30Z`
- Area: `services/mcp/app.py`
- Symptom: static check reports mixed tab/space indentation; code readability and portability risk.
- Repro steps:
  1. Run `python3 -m ruff check .`.
  2. Inspect diagnostics for `services/mcp/app.py`.
- Evidence:
  - `python3 -m ruff check .`
  - `E101 Indentation contains mixed spaces and tabs` at `services/mcp/app.py:709-711`
- Root cause: accidental tab characters introduced inside the `for key in (...)` block of command argument assembly.
- Fix status: `fixed`
- Notes: normalized to spaces-only indentation; no logic change.

### BUG-0002: Repository contains broad Python dead-import debt (multiple `F401`)

- Discovered at: `2026-02-28T12:38:30Z`
- Area: `scripts/` + `tests/` (multiple files)
- Symptom: many unused imports inflate noise and hide meaningful diagnostics.
- Repro steps:
  1. Run `python3 -m ruff check .`.
  2. Filter for `F401`.
- Evidence:
  - `python3 -m ruff check .`
  - report includes multiple `F401` entries across scripts/tests.
- Root cause: historical refactors removed usage without pruning import lists.
- Fix status: `fixed`
- Notes: cleanup batches removed all currently detectable `F401` entries (`python3 -m ruff check . --select F401` now passes).

### BUG-0003: Widespread test import-order debt (`I001`) still obscures signal quality

- Discovered at: `2026-02-28T12:54:00Z`
- Area: `tests/` (multiple files)
- Symptom: import-order lint noise remains high, making real warnings harder to spot.
- Repro steps:
  1. Run `python3 -m ruff check tests --select I001`.
  2. Observe multi-file unsorted/unformatted import diagnostics.
- Evidence:
  - `python3 -m ruff check tests --select I001`
  - baseline was 67 findings; after cleanup now 0 findings remain.
- Root cause: long-term mixed import style, plus deliberate late-import patterns in some tests.
- Fix status: `fixed`
- Notes: completed in staged batches; final check `python3 -m ruff check tests --select I001` is clean.

### BUG-0004: `test_tool_registry_sync` depended on unstable active-core selection

- Discovered at: `2026-02-28T12:57:15Z`
- Area: `tests/test_tool_registry_sync.py`
- Symptom: tests pass in isolation but fail when executed after other runtime tests.
- Repro steps:
  1. Run `python3 -m pytest -q tests/test_llm_routing.py tests/test_teacher_skill_service.py tests/test_tenant_infra.py tests/test_tool_registry_sync.py`.
  2. Observe `test_run_agent_*` returning welcome text instead of stubbed `"ok"`.
- Evidence:
  - Combined run above failed with 2 assertions in `test_tool_registry_sync.py`.
  - Isolated run `python3 -m pytest -q tests/test_tool_registry_sync.py` passed.
- Root cause: test only patched `app_mod.call_llm`, but `run_agent` resolves dependencies through the currently wired core, which can differ across test order.
- Fix status: `fixed`
- Notes: added `_patch_call_llm` helper to patch both `app_mod` and `services.api.wiring.get_app_core()` active core before assertions.

### BUG-0005: Cleanup aftermath left stale unused symbols in TS and tests

- Discovered at: `2026-02-28T13:13:00Z`
- Area: `frontend/apps/shared/errorMessage.ts`, `frontend/apps/teacher/src/features/workbench/workbenchFormatters.ts`, and selected tests
- Symptom: stricter no-unused checks failed after previous dead-code removals.
- Repro steps:
  1. Run `npm run typecheck -- --noUnusedLocals --noUnusedParameters`.
  2. Run `python3 -m ruff check . --select F821,F841,F541,F811,F823`.
- Evidence:
  - TS6133 on `FALLBACK_SERVER_ERROR` and `formatMissingRequirements`.
  - Ruff flagged `F541` and `F841` in test files.
- Root cause: helper/function removals made adjacent constants/imports/locals unreachable but they were not pruned in the same patch.
- Fix status: `fixed`
- Notes: removed stale symbols, fixed extraneous `f` string prefixes, and dropped one unused local variable.

### BUG-0006: Residual test lint defects (`E731`/`E741`) reduced readability and static-safety

- Discovered at: `2026-02-28T13:16:00Z`
- Area: `tests/test_content_catalog_service.py`, `tests/test_job_repository_lockfile.py`
- Symptom: lint flagged ambiguous variable name and lambda-assignment anti-patterns.
- Repro steps:
  1. Run `python3 -m ruff check . --select E731,E741`.
  2. Observe findings in the two test modules above.
- Evidence:
  - `E741` for comprehension variable `l`.
  - multiple `E731` for `acquire = lambda: ...` patterns.
- Root cause: earlier test scaffolding favored compact closures over explicit local helpers.
- Fix status: `fixed`
- Notes: renamed ambiguous variable and replaced lambda assignments with local `def` functions; related tests still pass.

### BUG-0007: Remaining `E402` import-order debt tied to runtime path/bootstrap sequencing

- Discovered at: `2026-02-28T13:16:00Z`
- Area: multiple scripts/tests using `sys.path` mutation or `load_dotenv` before dependent imports
- Symptom: `python3 -m ruff check .` still reports `E402` in bootstrapping-style modules.
- Repro steps:
  1. Run `python3 -m ruff check . --select E402`.
  2. Observe bootstrap-style modules with imports after path/env setup.
- Evidence:
  - Initial run: `python3 -m ruff check . --select E402` reported unresolved entries.
  - Current verification: `python3 -m ruff check . --select E402` -> `All checks passed!`.
- Root cause: modules intentionally adjust import path/environment before importing runtime dependencies.
- Fix status: `fixed`
- Notes: applied explicit `# noqa: E402` only in modules where bootstrap ordering is semantically required; reordered imports in non-bootstrap modules to satisfy lint without behavior changes.

### BUG-0008: Student stream reconnect-cap test expected outdated call count

- Discovered at: `2026-02-28T13:41:36Z`
- Area: `frontend/apps/student/src/features/chat/chatStreamClient.test.ts`
- Symptom: unit test fails with expected fetch retry count mismatch during stream fallback path.
- Repro steps:
  1. Run `cd frontend && npm run test:unit`.
  2. Observe failure in `runStudentChatStream > falls back after reconnect failures reach cap`.
- Evidence:
  - `npm run test:unit` reported `expected "spy" to be called 3 times, but got 2 times` at `chatStreamClient.test.ts:97`.
  - Focused rerun `npx vitest run apps/student/src/features/chat/chatStreamClient.test.ts` reproduced consistently (5/5).
- Root cause: implementation intentionally applies a stricter no-event reconnect cap `min(2, maxReconnects)` before first event arrives (`cursor <= initialCursor`), but test still asserted the generic `maxReconnects=3` call count.
- Fix status: `fixed`
- Notes: updated test title and assertion to align with no-event cap behavior while preserving fallback/protocol assertions.

### BUG-0009: `StudentVerifyCandidate` export removal violated backend contract drift guard

- Discovered at: `2026-02-28T13:55:04Z`
- Area: `frontend/apps/student/src/appTypes.ts` + `tests/test_student_verify_contract_drift.py`
- Symptom: CI backend-quality failed during full backend test suite after dead-code cleanup batch.
- Repro steps:
  1. Run `python3 -m pytest -q tests/test_student_verify_contract_drift.py`.
  2. Observe failure on required exported type contract.
- Evidence:
  - CI run `22522046250` failed at `Run full backend test suite` with assertion from `tests/test_student_verify_contract_drift.py:12`.
  - Local repro: `assert "export type StudentVerifyCandidate" in source` failed against current `appTypes.ts`.
- Root cause: `StudentVerifyCandidate` was flagged by `ts-prune` as module-local usage, but repository policy includes a drift guard requiring this symbol to remain an explicit exported contract type.
- Fix status: `fixed`
- Notes: restored `export type StudentVerifyCandidate` while keeping other safe export reductions.

### BUG-0010: `stop_chat_worker` could mark worker stopped while thread still alive

- Discovered at: `2026-02-28T14:57:00Z`
- Area: `services/api/workers/chat_worker_service.py`
- Symptom: stop path unconditionally set `worker_started=False`, even when join timeout expired and worker thread remained alive, allowing duplicate worker startup and lane-processing conflicts.
- Repro steps:
  1. Add/execute `test_stop_chat_worker_keeps_started_flag_when_thread_still_alive`.
  2. Run `python3 -m pytest -q tests/test_chat_worker_service.py -k still_alive`.
- Evidence:
  - Before fix: assertion failed (`assert started["value"] is True`) because stop path forced `False`.
  - After fix: same test passes and keeps `worker_started=True` when thread remains alive.
- Root cause: `stop_chat_worker()` joined threads with timeout but always cleared started flag without checking `thread.is_alive()`.
- Fix status: `fixed`
- Notes: stop path now inspects liveness, retains alive thread references, and sets `worker_started` from actual alive-thread state.

### BUG-0011: inline worker stop paths had same stale-state race as chat worker

- Discovered at: `2026-03-01T08:13:00Z`
- Area: `services/api/workers/upload_worker_service.py`, `services/api/workers/exam_worker_service.py`, `services/api/workers/profile_update_worker_service.py`
- Symptom: stop paths unconditionally cleared `worker_started` and thread handle even when `join(timeout)` returned while thread was still alive, reopening duplicate-start race for inline workers.
- Repro steps:
  1. Run `python3 -m pytest -q tests/test_inline_worker_services.py -k still_alive`.
  2. Observe `started` flipped to `False` despite alive fake thread in all three stop helpers.
- Evidence:
  - Before fix: `3 failed` with assertion `assert started["value"] is True`.
  - After fix: same selection passes (`3 passed`).
- Root cause: stop helpers assumed `join(timeout)` means termination and forced stopped state without `is_alive()` check.
- Fix status: `fixed`
- Notes: stop helpers now preserve thread handle and started flag while thread remains alive; once not alive they clear handle and mark stopped.

### BUG-0012: chat worker stale-start recovery conflicted with explicit started override

- Discovered at: `2026-03-01T08:27:54Z`
- Area: `services/api/workers/chat_worker_service.py`
- Symptom: after adding stale-start recovery, `start_chat_worker()` restarted workers when `worker_started=True` but no tracked threads, breaking tests and controlled runtimes that intentionally use this flag as "do not auto-start".
- Repro steps:
  1. Set `CHAT_JOB_WORKER_STARTED=True` and avoid real worker startup in chat-flow tests.
  2. Run `python3 -m pytest -q tests/test_chat_job_flow.py tests/test_student_history_flow.py`.
- Evidence:
  - Regression run produced multiple failures with job status stuck at `processing` because background workers restarted and raced manual `process_chat_job`.
  - Added unit guard `test_start_chat_worker_respects_started_override_without_tracked_threads`.
- Root cause: stale recovery path treated `started=True && threads=[]` as broken state, but in this codebase it can be an explicit runtime/test override.
- Fix status: `fixed`
- Notes: stale recovery now runs only when started flag is true and there are tracked threads; if no threads are tracked, `start_chat_worker()` preserves override semantics.

### BUG-0013: chat worker threads lacked `CURRENT_CORE` context propagation

- Discovered at: `2026-03-01T08:31:19Z`
- Area: `services/api/wiring/chat_wiring.py`
- Symptom: worker threads repeatedly logged `CURRENT_CORE not set, falling back to default tenant module`; this created heavy noise and teardown-time logging errors in long pytest runs.
- Repro steps:
  1. Run `python3 -m pytest -q` with chat worker activity.
  2. Observe repeated fallback warnings emitted from worker thread stack paths.
- Evidence:
  - Full-suite output showed repeated warning call stacks originating from `chat_job_worker_loop` through `services/api/wiring/__init__.py:get_app_core`.
  - New regression test `tests/test_chat_wiring_context.py::test_chat_worker_thread_factory_sets_current_core`.
- Root cause: worker threads were started without binding `CURRENT_CORE`, so dependency lookups inside worker execution fell back to default core on every call.
- Fix status: `fixed`
- Notes: `_chat_worker_deps()` now wraps thread targets to set/reset `CURRENT_CORE` for worker thread execution context.
