# Student UI Quality Hardening Design (Plan A)

Date: 2026-02-13  
Scope: Student frontend quality hardening with delivery quality as first priority.

## 1. Goals And Constraints

### Goals
1. Reduce student UI regressions in core flows (sidebar, send, recover, session switch).
2. Improve confidence of every release through deterministic test gates.
3. Lower maintenance cost by separating high-coupling UI modules.

### Non-goals
1. No major visual redesign.
2. No business workflow changes.
3. No backend contract expansion unless required by stability.

### Constraints
1. Keep current user-facing behavior unchanged except bug fixes.
2. Keep CI runtime controlled by defining a minimal critical UI suite.
3. Preserve existing local-storage compatibility.

## 2. Quality Targets (Exit Criteria)

1. Critical student UI E2E suite pass rate: 100% on main branch.
2. New regression tests added for sidebar state persistence and anti-bounce behavior.
3. No open P0 UI bugs in core student path before release.
4. `frontend/apps/student/src/features/chat/SessionSidebar.tsx` responsibilities split with no behavior drift.

## 3. Recommended Execution (Plan A)

## P0: Stabilize And Guard (Must, This Week)

### P0-1 Sidebar state hardening matrix
Tasks:
1. Expand desktop + mobile toggle tests for `open -> close -> open` roundtrip.
2. Add persistence checks for `studentSidebarOpen` across reload.
3. Verify interaction with active session switching and pending status.

Acceptance:
1. `frontend/e2e/student-sidebar-collapse-regression.spec.ts` passes.
2. Add at least two additional assertions in existing sidebar-related student E2E.
3. No transient class bounce detected after manual close in desktop.

### P0-2 Critical path state-transition contracts
Tasks:
1. Define invariant checks around `sidebarOpen`, `activeSessionId`, `pendingChatJob`.
2. Add reducer-level unit checks for illegal reverse transitions.

Acceptance:
1. State transition tests fail when introducing artificial regressions.
2. Existing student send/pending flow tests stay green.

### P0-3 CI minimal gate for student UI
Tasks:
1. Add a student critical subset job in CI (sidebar, send, recover).
2. Keep failure artifacts (trace/video/screenshot).

Acceptance:
1. CI blocks merge on any critical student UI failure.
2. Failure artifacts are visible and downloadable from workflow runs.

Estimated effort: 1.5-2.0 days.

## P1: Refactor For Maintainability (1-2 Weeks)

### P1-1 SessionSidebar modular split
Tasks:
1. Extract history list area component.
2. Extract identity/verification panel component.
3. Extract assignment info panel component.
4. Keep dialog orchestration at container level.

Acceptance:
1. No behavior diff in current E2E suite.
2. `SessionSidebar.tsx` size and cognitive load reduced materially.
3. Strongly typed props per submodule with minimal shared mutable state.

### P1-2 Student UI selector layer
Tasks:
1. Introduce derived selectors for UI state composition.
2. Remove duplicated inline derivation in rendering path.

Acceptance:
1. UI derivation rules are centralized and unit-tested.
2. Rendering components consume selector outputs, not raw mixed state.

Estimated effort: 3-4 days.

## P2: Consistency And Risk Reduction (After P1)

### P2-1 Accessibility and interaction consistency pass
Tasks:
1. Focus-return and keyboard traversal audit for menu/dialog/sidebar.
2. Normalize disabled/loading copy and visual states.

Acceptance:
1. Keyboard-only completion of core flow is possible.
2. No conflicting status labels across sending/pending/verifying.

### P2-2 Lightweight visual regression sentinel
Tasks:
1. Add snapshot sentinel for student shell and sidebar in two breakpoints.
2. Keep snapshots minimal to avoid flaky maintenance burden.

Acceptance:
1. Layout drift is caught early in PR checks.
2. Snapshot update process is documented.

Estimated effort: 2-3 days.

## 4. Verification Commands

Run from `/Users/lvxiaoer/Documents/New project/frontend`:

```bash
npm run e2e:student -- e2e/student-sidebar-collapse-regression.spec.ts
npm run e2e:student -- e2e/student-session-sidebar.spec.ts
npm run e2e:student -- e2e/student-high-risk-resilience.spec.ts
npm run typecheck
```

## 5. Delivery Sequence

1. Complete all P0 items and stabilize CI gate.
2. Execute P1 refactor in small slices with behavior-lock tests first.
3. Execute P2 consistency improvements and visual sentinels.

## 6. Risks And Mitigation

1. Risk: E2E flakiness from timing-sensitive polling paths.  
Mitigation: prefer deterministic mocks and explicit state assertions.
2. Risk: Refactor drift in SessionSidebar behavior.  
Mitigation: lock behavior with regression tests before extraction.
3. Risk: CI time increase.  
Mitigation: keep critical subset small and focused on core user journey.
