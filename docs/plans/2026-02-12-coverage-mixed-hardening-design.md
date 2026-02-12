# Coverage Mixed Hardening Design (2026-02-12)

## Goal

Raise backend coverage from the current baseline while keeping behavior stable and
quality gates green (`ruff=0`, `mypy=0`, budget check passing). This design uses a
mixed strategy: targeted coverage expansion plus small refactors that improve
testability without changing external API contracts.

## Scope

Primary modules:

1. `services/api/chart_executor.py` (low coverage, high complexity)
2. `services/api/teacher_skill_service.py` (low coverage, external IO branches)
3. `services/api/workers/rq_tasks.py` (near-zero coverage, queue/redis flows)

Non-goals:

- No API shape changes.
- No cross-module architecture rewrite.
- No production behavior changes beyond bug-fix parity for testability.

## Execution Slices

### Slice A: `rq_tasks` (quick win)

- Add a small internal scan helper to remove duplicated pending-job scan logic.
- Keep public entrypoints unchanged.
- Add comprehensive unit tests for enqueue, scan, and run paths with mocked
  Redis, Queue, lane store, and tenant runtime.

Expected result: coverage for `rq_tasks` from near 0% to high baseline quickly.

### Slice B: `teacher_skill_service`

- Add tests for GitHub URL/raw conversion, download error handling, companion
  directory download recursion, frontmatter fallback/default injection, dependency
  extraction, dependency checking, and install failure branches.
- Keep function signatures unchanged.

Expected result: strong branch coverage uplift in import/dependency paths.

### Slice C: `chart_executor`

- Add tests for runtime execution branches (semaphore gate, sandbox scan short-circuit,
  venv-init failure path, retry/missing-module auto-install path, timeout path,
  artifact/meta assembly).
- Introduce only minimal seams if necessary to simplify deterministic tests.

Expected result: raise `chart_executor` coverage materially while preserving runtime behavior.

## Testing and Verification

For each slice:

1. RED: add/extend failing tests for uncovered branches.
2. GREEN: implement minimal refactor/fix to pass tests.
3. Verify:
   - targeted pytest subset,
   - `ruff` on changed files,
   - `mypy` on changed modules when applicable,
   - `scripts/quality/check_backend_quality_budget.py`.

Final verification:

- Full backend suite with coverage:
  `python3 -m pytest tests/ -x -q -m "not stress" --cov=services/api --cov-report=term-missing`

## Risk and Rollback

- Each slice remains independently reversible.
- Any regression in shared flows (queue, chart runtime, skill import) is contained
  by slice-level tests before full-suite run.
