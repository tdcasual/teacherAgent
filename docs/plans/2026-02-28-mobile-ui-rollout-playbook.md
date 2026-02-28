# Mobile UI Rollout Playbook (Student + Teacher)

## Goal

- Roll out mobile shell v2 gradually without regressing runtime stability or key chat flows.
- Keep rollback latency under 5 minutes by relying on localStorage/env feature flags.

## Feature Flags

- Student: `VITE_MOBILE_SHELL_V2_STUDENT` and local override `studentMobileShellV2`.
- Teacher: `VITE_MOBILE_SHELL_V2_TEACHER` and local override `teacherMobileShellV2`.

## Preconditions

- `npm run lint` passes.
- `npm run e2e:mobile-menu` passes.
- Manual smoke completed on three viewports: `375x667`, `393x852`, `412x915`.

## Rollout Stages

1. Stage A (internal only)
- Enable v2 flags for internal QA accounts.
- Observe runtime logs and mobile task completion for 24 hours.

2. Stage B (small cohort)
- Enable v2 flags for 10-20% mobile traffic.
- Keep desktop behavior unchanged.

3. Stage C (full mobile rollout)
- Enable for 100% mobile traffic after Stage B remains stable for 48 hours.

## Watch Metrics

- Runtime error count matching:
  - `Maximum update depth exceeded`
  - `TypeError`
  - `ReferenceError`
- Mobile tab switch success rate.
- Bottom sheet open/close completion rate.
- Message send success rate after tab switches.

## Rollback Rules

- Immediate rollback if any of:
  - Runtime error spike > 2x baseline for 10 minutes.
  - Mobile send success rate drops by > 5%.
  - Session/workbench navigation becomes non-functional.

## Rollback Procedure

1. Set `VITE_MOBILE_SHELL_V2_STUDENT=0`.
2. Set `VITE_MOBILE_SHELL_V2_TEACHER=0`.
3. Clear local overrides in debug sessions:
   - `localStorage.removeItem('studentMobileShellV2')`
   - `localStorage.removeItem('teacherMobileShellV2')`
4. Re-run `npm run e2e:mobile-menu`.
5. Announce rollback completion and incident summary.

## Ownership

- Frontend owner: validates UI/interaction behavior and tests.
- QA owner: verifies stage gate criteria and smoke checklist.
- Release owner: controls flag percentages and rollback switches.
