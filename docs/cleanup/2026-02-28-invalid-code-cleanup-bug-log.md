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
