# Maintainability P1/P2 Execution Slices (2026-02-12)

## Current Status Snapshot

1. Backend P1 (teacher routes split + shared helper) is complete:
`services/api/routes/teacher_routes.py` now composes sub-routers and shared helper logic is centralized in `services/api/routes/teacher_route_helpers.py`.
2. `run_agent_runtime` hotspot has been decomposed:
`services/api/agent_service.py` function `run_agent_runtime` is now 71 lines (from 297), with private helpers for skill loading, teacher guards, longform branch, and tool-loop orchestration.
3. Guardrail added:
`tests/test_agent_service_structure.py` enforces `run_agent_runtime < 170`.

## P1 Slice A (Student Send Flow Hook, 2-3 days)

### Objective
Extract send orchestration and local locking from `frontend/apps/student/src/App.tsx` into stable hooks, reducing coupling and improving testability.

### Steps
1. Add lock primitive module:
`frontend/apps/student/src/features/chat/sendLock.ts`
- Move `withStudentSendLock` fallback locking logic and constants here.
- Keep browser Locks API path + localStorage fallback behavior unchanged.
2. Add send-flow hook:
`frontend/apps/student/src/features/chat/useStudentSendFlow.ts`
- Move `handleSend` + pending storage synchronization (`syncPendingFromStorage`, wait loop, request dispatch, placeholder updates).
- Input/output contract should be explicit params + callbacks, no hidden global reads.
3. Wire App integration:
`frontend/apps/student/src/App.tsx`
- Replace inline lock/send logic with hook invocation.
- Keep current UI texts and error copy unchanged.
4. Add targeted regression tests:
- `frontend/apps/student/src/features/chat/useStudentSendFlow.test.ts` for lock contention and pending recovery branches.
- Keep existing E2E path green.

### Gates
1. `frontend/apps/student/src/App.tsx < 1500` after slice A.
2. `cd frontend && npm run typecheck` passes.
3. Existing student chat E2E remains green.

## P1 Slice B (Session Sidebar State Hook, 2-3 days, parallel with Slice A)

### Objective
Move session sidebar/menu/view-state logic out of `App.tsx`.

### Steps
1. Add state hook:
`frontend/apps/student/src/features/session/useStudentSessionSidebarState.ts`
- Move sidebar open state, menu refs, keyboard handlers, outside-click close, archived filter toggles.
2. Add view-state sync hook:
`frontend/apps/student/src/features/session/useStudentSessionViewStateSync.ts`
- Move local+remote view-state merge/sync logic.
3. Keep render tree unchanged:
`StudentSessionShell` remains the UI boundary; App only consumes hook outputs.

### Gates
1. `frontend/apps/student/src/App.tsx < 1200` after slice B.
2. Session menu keyboard navigation behavior unchanged.
3. `cd frontend && npm run typecheck` passes.

## P2 Slice C (TeacherWorkbenchViewModel, follow-up)

### Objective
Reduce prop storm from teacher App to workbench.

### Steps
1. Create view-model builder:
`frontend/apps/teacher/src/features/workbench/teacherWorkbenchViewModel.ts`
2. Replace long prop list with a single typed object prop:
`viewModel` (+ minimal callbacks that cannot be embedded).
3. Update consumer:
`frontend/apps/teacher/src/features/workbench/TeacherWorkbench.tsx`.

### Gates
1. `frontend/apps/teacher/src/App.tsx < 800`.
2. Workbench prop count from App reduced to <= 8 top-level props.

## P2 Slice D (app_core Sink-Down, follow-up)

### Objective
Reduce `app_core.py` import fan-out and move compatibility wrappers into bounded context application modules.

### Steps
1. Group wrappers by domain and move call paths to context modules:
`services/api/exam/application.py`, `services/api/assignment/application.py`, `services/api/chat/application.py`.
2. Keep `app_core.py` as compatibility facade only for unresolved legacy imports.
3. Add structure budget test:
`tests/test_app_core_structure.py` with initial guard at `< 1200`.

### Gates
1. `services/api/app_core.py < 1200`.
2. Full backend test suite remains green.

## Verification Commands (per slice)

1. `python3 -m pytest -q`
2. `cd frontend && npm run typecheck`
3. `wc -l frontend/apps/student/src/App.tsx frontend/apps/teacher/src/App.tsx services/api/app_core.py`
