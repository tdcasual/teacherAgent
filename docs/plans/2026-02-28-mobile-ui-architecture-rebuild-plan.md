# Teacher + Student Mobile UI Architecture Rebuild Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebuild teacher and student frontend UI into a mobile-first architecture with chat-first interaction, full-screen task flows, and resilient streaming feedback while preserving current business capability.

**Architecture:** Split each app into a stable conversation shell plus task-specific full-screen flows. On mobile, replace persistent side panels with sheet/navigation patterns and explicit screen states. Introduce feature flags, state migration guards, and progressive rollout so the refactor is reversible.

**Tech Stack:** React 19, TypeScript, Tailwind CSS 4, react-resizable-panels (desktop only), Vitest, Playwright

---

## Scope

- In scope:
  - Teacher app mobile IA refactor (chat-first shell + bottom tabs + sheets + flow pages)
  - Student app mobile IA refactor (assignment-first shell + session sheet + full-screen persona)
  - Unified streaming status model and UI contracts
  - New mobile-focused e2e and unit coverage
- Out of scope:
  - Backend API contract changes
  - Full visual redesign for desktop parity
  - New data domains (no new workflow semantics)

## Design Principles

1. Chat must remain usable even when any secondary panel fails.
2. Mobile state transitions must be explicit and serializable (URL/state key/feature flag).
3. Desktop behavior remains stable unless behind explicit flag.
4. Every major view transition gets e2e coverage.
5. Big-bang release is forbidden; rollout must be staged.

---

## Phase 0: Safety Rails

### Task 1: Add feature flags for shell migration

**Files:**
- Create: `frontend/apps/shared/featureFlags.ts`
- Modify: `frontend/apps/teacher/src/App.tsx`
- Modify: `frontend/apps/student/src/App.tsx`
- Test: `frontend/apps/shared/featureFlags.test.ts`

**Step 1: Write failing test**

```ts
import { describe, expect, it } from 'vitest'
import { readFeatureFlag } from './featureFlags'

describe('readFeatureFlag', () => {
  it('returns fallback false when flag is missing', () => {
    expect(readFeatureFlag('mobileShellV2', false, {})).toBe(false)
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm run test:unit -- apps/shared/featureFlags.test.ts`
Expected: FAIL with module/function missing.

**Step 3: Write minimal implementation**

```ts
export const readFeatureFlag = (key: string, fallback: boolean, source: Record<string, string | undefined>) => {
  const raw = source[key]
  if (raw == null) return fallback
  return raw === '1' || raw.toLowerCase() === 'true'
}
```

**Step 4: Run test to verify it passes**

Run: `cd frontend && npm run test:unit -- apps/shared/featureFlags.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/apps/shared/featureFlags.ts frontend/apps/shared/featureFlags.test.ts frontend/apps/teacher/src/App.tsx frontend/apps/student/src/App.tsx
git commit -m "feat(ui): add feature flags for mobile shell migration"
```

---

### Task 2: Introduce shared mobile primitives (sheet + tab bar)

**Files:**
- Create: `frontend/apps/shared/mobile/BottomSheet.tsx`
- Create: `frontend/apps/shared/mobile/MobileTabBar.tsx`
- Create: `frontend/apps/shared/mobile/mobile.css`
- Test: `frontend/apps/shared/mobile/BottomSheet.test.tsx`

**Step 1: Write failing test**

```tsx
import { render, screen } from '@testing-library/react'
import { BottomSheet } from './BottomSheet'

it('renders children when open', () => {
  render(<BottomSheet open onClose={() => {}} title="Sheet">content</BottomSheet>)
  expect(screen.getByText('content')).toBeVisible()
})
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm run test:unit -- apps/shared/mobile/BottomSheet.test.tsx`
Expected: FAIL module missing.

**Step 3: Write minimal implementation**

- `BottomSheet` supports `open`, `onClose`, `title`, `children`, overlay click close, escape close.
- `MobileTabBar` supports 3-5 tabs with active state and accessible labels.

**Step 4: Run test to verify it passes**

Run: `cd frontend && npm run test:unit -- apps/shared/mobile/BottomSheet.test.tsx`
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/apps/shared/mobile
git commit -m "feat(ui): add shared mobile sheet and tab primitives"
```

---

## Phase 1: Teacher App Re-architecture

### Task 3: Split teacher shell into conversation shell and flow shell

**Files:**
- Create: `frontend/apps/teacher/src/features/layout/TeacherConversationShell.tsx`
- Create: `frontend/apps/teacher/src/features/layout/TeacherFlowShell.tsx`
- Modify: `frontend/apps/teacher/src/App.tsx`
- Test: `frontend/e2e/teacher-mobile-shell-navigation.spec.ts`

**Step 1: Write failing e2e test**

```ts
test('mobile tab switch keeps composer reachable on chat shell', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await openTeacherApp(page, { stateOverrides: { teacherMobileShellV2: 'true' } })
  await expect(page.getByRole('button', { name: '聊天' })).toBeVisible()
  await expect(page.getByRole('button', { name: '发送' })).toBeVisible()
})
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm run e2e:teacher -- e2e/teacher-mobile-shell-navigation.spec.ts`
Expected: FAIL due missing navigation/shell split.

**Step 3: Write minimal implementation**

- `TeacherConversationShell` hosts topbar + chat main + composer.
- `TeacherFlowShell` hosts workflow/routing/persona full-screen content.
- `App.tsx` routes mobile tabs to shell mode while desktop remains current layout.

**Step 4: Run test to verify it passes**

Run: same command above.
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/apps/teacher/src/App.tsx frontend/apps/teacher/src/features/layout/TeacherConversationShell.tsx frontend/apps/teacher/src/features/layout/TeacherFlowShell.tsx frontend/e2e/teacher-mobile-shell-navigation.spec.ts
git commit -m "feat(teacher-mobile): split conversation and flow shells"
```

---

### Task 4: Replace teacher sidebars with mobile sheets

**Files:**
- Modify: `frontend/apps/teacher/src/features/chat/TeacherSessionRail.tsx`
- Modify: `frontend/apps/teacher/src/features/workbench/TeacherWorkbench.tsx`
- Modify: `frontend/apps/teacher/src/features/chat/useSessionActions.ts`
- Modify: `frontend/apps/teacher/src/features/chat/useTeacherUiPanels.ts`
- Test: `frontend/e2e/teacher-mobile-sheet-contract.spec.ts`

**Step 1: Write failing e2e test**

```ts
test('mobile open session list then select closes sheet and keeps chat focus', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await openTeacherApp(page, { stateOverrides: { teacherMobileShellV2: 'true' } })
  await page.getByRole('button', { name: '会话' }).click()
  await page.getByRole('button', { name: /s2/ }).click()
  await expect(page.getByRole('button', { name: '发送' })).toBeVisible()
})
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm run e2e:teacher -- e2e/teacher-mobile-sheet-contract.spec.ts`
Expected: FAIL.

**Step 3: Write minimal implementation**

- Session list and workbench render inside `BottomSheet` on mobile.
- Existing overlay logic is removed from mobile V2 path.
- Selecting session auto-closes sheet and restores composer focus.

**Step 4: Run test to verify it passes**

Run same command.
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/apps/teacher/src/features/chat/TeacherSessionRail.tsx frontend/apps/teacher/src/features/workbench/TeacherWorkbench.tsx frontend/apps/teacher/src/features/chat/useSessionActions.ts frontend/apps/teacher/src/features/chat/useTeacherUiPanels.ts frontend/e2e/teacher-mobile-sheet-contract.spec.ts
git commit -m "feat(teacher-mobile): migrate sidebars to sheet interactions"
```

---

### Task 5: Simplify teacher topbar for mobile

**Files:**
- Modify: `frontend/apps/teacher/src/features/layout/TeacherTopbar.tsx`
- Create: `frontend/apps/teacher/src/features/layout/TeacherMoreMenu.tsx`
- Test: `frontend/e2e/teacher-mobile-topbar-density.spec.ts`

**Step 1: Write failing e2e test**

```ts
test('mobile topbar shows at most two primary actions', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await openTeacherApp(page, { stateOverrides: { teacherMobileShellV2: 'true' } })
  await expect(page.getByRole('button', { name: '更多' })).toBeVisible()
})
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm run e2e:teacher -- e2e/teacher-mobile-topbar-density.spec.ts`
Expected: FAIL.

**Step 3: Write minimal implementation**

- Mobile topbar keeps: title, session toggle, “更多”.
- Move auth/routing/persona/settings/workbench actions into `TeacherMoreMenu`.

**Step 4: Run test to verify it passes**

Run same command.
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/apps/teacher/src/features/layout/TeacherTopbar.tsx frontend/apps/teacher/src/features/layout/TeacherMoreMenu.tsx frontend/e2e/teacher-mobile-topbar-density.spec.ts
git commit -m "feat(teacher-mobile): reduce topbar density with more menu"
```

---

### Task 6: Promote routing/persona/settings to full-screen flows

**Files:**
- Modify: `frontend/apps/teacher/src/features/settings/SettingsModal.tsx`
- Modify: `frontend/apps/teacher/src/features/persona/TeacherPersonaManager.tsx`
- Modify: `frontend/apps/teacher/src/features/routing/RoutingPage.tsx`
- Test: `frontend/e2e/teacher-mobile-fullscreen-flows.spec.ts`

**Step 1: Write failing e2e test**

```ts
test('routing opens as full-screen flow on mobile and returns to chat', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await openTeacherApp(page, { stateOverrides: { teacherMobileShellV2: 'true' } })
  await page.getByRole('button', { name: '更多' }).click()
  await page.getByRole('button', { name: '模型路由' }).click()
  await expect(page.locator('[data-testid="teacher-flow-shell"]')).toBeVisible()
  await page.getByRole('button', { name: '返回聊天' }).click()
  await expect(page.getByRole('button', { name: '发送' })).toBeVisible()
})
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm run e2e:teacher -- e2e/teacher-mobile-fullscreen-flows.spec.ts`
Expected: FAIL.

**Step 3: Write minimal implementation**

- On mobile V2 flag, routing/persona/settings use full-screen page container instead of floating modal.
- Keep desktop modal behavior unchanged.

**Step 4: Run test to verify it passes**

Run same command.
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/apps/teacher/src/features/settings/SettingsModal.tsx frontend/apps/teacher/src/features/persona/TeacherPersonaManager.tsx frontend/apps/teacher/src/features/routing/RoutingPage.tsx frontend/e2e/teacher-mobile-fullscreen-flows.spec.ts
git commit -m "feat(teacher-mobile): use full-screen flow pages for ops features"
```

---

### Task 7: Make teacher composer mobile-safe with explicit insets and sticky contract

**Files:**
- Modify: `frontend/apps/teacher/src/features/chat/ChatComposer.tsx`
- Modify: `frontend/apps/teacher/src/features/chat/TeacherChatMainContent.tsx`
- Modify: `frontend/apps/teacher/src/tailwind.css`
- Test: `frontend/e2e/teacher-mobile-composer-sticky.spec.ts`

**Step 1: Write failing e2e test**

```ts
test('mobile composer remains visible after opening keyboard and switching tabs', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await openTeacherApp(page, { stateOverrides: { teacherMobileShellV2: 'true' } })
  const composer = page.getByPlaceholder(TEACHER_COMPOSER_PLACEHOLDER)
  await composer.click()
  await expect(composer).toBeVisible()
})
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm run e2e:teacher -- e2e/teacher-mobile-composer-sticky.spec.ts`
Expected: FAIL.

**Step 3: Write minimal implementation**

- Add mobile class variants for composer padding/safe-area and sticky footer behavior.
- Ensure shell uses `min-h-0` + isolated scroll container only.

**Step 4: Run test to verify it passes**

Run same command.
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/apps/teacher/src/features/chat/ChatComposer.tsx frontend/apps/teacher/src/features/chat/TeacherChatMainContent.tsx frontend/apps/teacher/src/tailwind.css frontend/e2e/teacher-mobile-composer-sticky.spec.ts
git commit -m "feat(teacher-mobile): harden composer sticky and safe-area behavior"
```

---

## Phase 2: Student App Re-architecture

### Task 8: Build assignment-first student home shell

**Files:**
- Create: `frontend/apps/student/src/features/layout/StudentHomeShell.tsx`
- Modify: `frontend/apps/student/src/App.tsx`
- Modify: `frontend/apps/student/src/features/layout/StudentTopbar.tsx`
- Test: `frontend/e2e/student-mobile-assignment-first.spec.ts`

**Step 1: Write failing e2e test**

```ts
test('mobile opens to assignment-first surface and one-tap start chat', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await openStudentApp(page, { stateOverrides: { studentMobileShellV2: 'true' } })
  await expect(page.getByText('今日作业')).toBeVisible()
  await page.getByRole('button', { name: '开始今日作业' }).click()
  await expect(page.getByRole('button', { name: '发送' })).toBeVisible()
})
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm run e2e:student -- e2e/student-mobile-assignment-first.spec.ts`
Expected: FAIL.

**Step 3: Write minimal implementation**

- New `StudentHomeShell` with assignment summary card and CTA.
- CTA routes to chat pane state and focuses composer.

**Step 4: Run test to verify it passes**

Run same command.
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/apps/student/src/features/layout/StudentHomeShell.tsx frontend/apps/student/src/App.tsx frontend/apps/student/src/features/layout/StudentTopbar.tsx frontend/e2e/student-mobile-assignment-first.spec.ts
git commit -m "feat(student-mobile): introduce assignment-first home shell"
```

---

### Task 9: Replace student left sidebar with session sheet

**Files:**
- Modify: `frontend/apps/student/src/features/layout/StudentLayout.tsx`
- Modify: `frontend/apps/student/src/features/chat/SessionSidebar.tsx`
- Modify: `frontend/apps/student/src/tailwind.css`
- Test: `frontend/e2e/student-mobile-session-sheet.spec.ts`

**Step 1: Write failing e2e test**

```ts
test('session sheet opens from bottom and closes after selection', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await openStudentApp(page, { stateOverrides: { studentMobileShellV2: 'true' } })
  await page.getByRole('button', { name: '会话' }).click()
  await page.getByRole('button', { name: /main/ }).click()
  await expect(page.getByRole('button', { name: '发送' })).toBeVisible()
})
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm run e2e:student -- e2e/student-mobile-session-sheet.spec.ts`
Expected: FAIL.

**Step 3: Write minimal implementation**

- Mobile V2 path renders history list in `BottomSheet` with existing menu keyboard support preserved.
- Remove fixed-left slide panel behavior for V2.

**Step 4: Run test to verify it passes**

Run same command.
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/apps/student/src/features/layout/StudentLayout.tsx frontend/apps/student/src/features/chat/SessionSidebar.tsx frontend/apps/student/src/tailwind.css frontend/e2e/student-mobile-session-sheet.spec.ts
git commit -m "feat(student-mobile): migrate session history to bottom sheet"
```

---

### Task 10: Convert student persona picker to full-screen flow

**Files:**
- Modify: `frontend/apps/student/src/features/layout/StudentTopbar.tsx`
- Create: `frontend/apps/student/src/features/persona/StudentPersonaScreen.tsx`
- Test: `frontend/e2e/student-mobile-persona-screen.spec.ts`

**Step 1: Write failing e2e test**

```ts
test('persona opens full-screen on mobile and selection returns to chat', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await openStudentApp(page, { stateOverrides: { studentMobileShellV2: 'true' } })
  await page.getByRole('button', { name: '选择角色卡' }).click()
  await expect(page.locator('[data-testid="student-persona-screen"]')).toBeVisible()
})
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm run e2e:student -- e2e/student-mobile-persona-screen.spec.ts`
Expected: FAIL.

**Step 3: Write minimal implementation**

- Mobile V2 uses full-screen persona screen with search/list/editor sections.
- Keep current desktop dropdown as-is for backward compatibility.

**Step 4: Run test to verify it passes**

Run same command.
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/apps/student/src/features/layout/StudentTopbar.tsx frontend/apps/student/src/features/persona/StudentPersonaScreen.tsx frontend/e2e/student-mobile-persona-screen.spec.ts
git commit -m "feat(student-mobile): move persona selection to full-screen flow"
```

---

## Phase 3: Dynamic Interaction and State Resilience

### Task 11: Introduce shared stream phase model

**Files:**
- Create: `frontend/apps/shared/streamPhase.ts`
- Modify: `frontend/apps/student/src/hooks/useChatPolling.ts`
- Modify: `frontend/apps/teacher/src/features/chat/useTeacherChatApi.ts`
- Modify: `frontend/apps/student/src/features/chat/studentUiSelectors.ts`
- Modify: `frontend/apps/teacher/src/features/chat/ChatMessages.tsx`
- Test: `frontend/apps/shared/streamPhase.test.ts`
- Test: `frontend/apps/student/src/features/chat/chatStreamClient.test.ts`

**Step 1: Write failing tests**

```ts
it('maps transport states to ui phases', () => {
  expect(toStreamPhase({ pending: true, hasDelta: false })).toBe('sending')
})
```

```ts
it('respects maxReconnects contract for no-event reconnect path', async () => {
  // assert behavior aligns with implementation cap policy
})
```

**Step 2: Run tests to verify failure**

Run: `cd frontend && npm run test:unit -- apps/shared/streamPhase.test.ts apps/student/src/features/chat/chatStreamClient.test.ts`
Expected: FAIL.

**Step 3: Write minimal implementation**

- Define explicit phases: `idle`, `sending`, `streaming`, `recovering`, `failed`, `done`.
- Align student reconnect test with implemented cap policy (or adjust implementation intentionally, but test and implementation must match).

**Step 4: Run tests to verify pass**

Run same command.
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/apps/shared/streamPhase.ts frontend/apps/shared/streamPhase.test.ts frontend/apps/student/src/hooks/useChatPolling.ts frontend/apps/teacher/src/features/chat/useTeacherChatApi.ts frontend/apps/student/src/features/chat/studentUiSelectors.ts frontend/apps/teacher/src/features/chat/ChatMessages.tsx frontend/apps/student/src/features/chat/chatStreamClient.test.ts
git commit -m "feat(ui): unify stream phases and reconcile reconnect test contract"
```

---

### Task 12: Add view-state schema versioning and migration guard

**Files:**
- Create: `frontend/apps/shared/viewStateSchema.ts`
- Modify: `frontend/apps/teacher/src/features/chat/viewState.ts`
- Modify: `frontend/apps/student/src/features/session/useStudentSessionViewStateSync.ts`
- Test: `frontend/apps/shared/viewStateSchema.test.ts`

**Step 1: Write failing test**

```ts
it('migrates v1 view-state payload to v2 without data loss', () => {
  const migrated = migrateViewState({ version: 1, title_map: {} })
  expect(migrated.version).toBe(2)
})
```

**Step 2: Run test to verify failure**

Run: `cd frontend && npm run test:unit -- apps/shared/viewStateSchema.test.ts`
Expected: FAIL.

**Step 3: Implement minimal migration**

- Add versioned parser/migrator.
- Use migrator before localStorage reads in teacher/student view-state loaders.

**Step 4: Run test to verify pass**

Run same command.
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/apps/shared/viewStateSchema.ts frontend/apps/shared/viewStateSchema.test.ts frontend/apps/teacher/src/features/chat/viewState.ts frontend/apps/student/src/features/session/useStudentSessionViewStateSync.ts
git commit -m "feat(state): add view-state schema versioning and migration guard"
```

---

## Phase 4: Verification and Rollout

### Task 13: Expand mobile e2e matrix for both roles

**Files:**
- Create: `frontend/e2e/teacher-mobile-v2-regression.spec.ts`
- Create: `frontend/e2e/student-mobile-v2-regression.spec.ts`
- Modify: `frontend/package.json`

**Step 1: Write failing tests covering critical paths**

- Teacher: tab switch, sheet close, full-screen flow return, composer reachability, pending-state recovery.
- Student: assignment-first path, session sheet keyboard contract, persona full-screen return, overflow/overscroll guard.

**Step 2: Run tests to verify failure**

Run:
- `cd frontend && npm run e2e:teacher -- e2e/teacher-mobile-v2-regression.spec.ts`
- `cd frontend && npm run e2e:student -- e2e/student-mobile-v2-regression.spec.ts`

Expected: FAIL before implementation completion.

**Step 3: Implement or tune selectors/contracts**

- Add stable `data-testid` where needed.

**Step 4: Run tests to verify pass**

Run same commands plus:
- `cd frontend && npm run e2e:teacher -- --grep mobile`
- `cd frontend && npm run e2e:student -- --grep mobile`

Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/e2e/teacher-mobile-v2-regression.spec.ts frontend/e2e/student-mobile-v2-regression.spec.ts frontend/package.json
git commit -m "test(mobile): add v2 regression suites for teacher and student"
```

---

### Task 14: Final verification gate and staged rollout

**Files:**
- Modify: `frontend/README.md`
- Modify: `frontend/apps/student/src/main.tsx`
- Modify: `frontend/apps/teacher/src/main.tsx`

**Step 1: Add rollout toggle docs and env contract**

- Document `VITE_MOBILE_SHELL_V2_TEACHER` and `VITE_MOBILE_SHELL_V2_STUDENT`.

**Step 2: Run full verification**

Run:
- `cd frontend && npm run lint`
- `cd frontend && npm run typecheck`
- `cd frontend && npm run test:unit`
- `cd frontend && npm run e2e:teacher -- --grep mobile`
- `cd frontend && npm run e2e:student -- --grep mobile`

Expected: all pass.

**Step 3: Wire phased enablement**

- default off in production, on in staging.
- add quick rollback instruction (single flag flip).

**Step 4: Commit**

```bash
git add frontend/README.md frontend/apps/student/src/main.tsx frontend/apps/teacher/src/main.tsx
git commit -m "chore(release): document and wire staged mobile shell rollout"
```

---

## Acceptance Criteria

1. Teacher mobile can complete: session select -> chat send -> routing flow open/close -> return chat without layout break.
2. Student mobile can complete: assignment entry -> chat send -> session switch -> persona switch without hidden controls.
3. No regression on existing desktop teacher 3-panel behavior when V2 flags are disabled.
4. Existing mobile grep suites plus new V2 suites are green.
5. Stream status is explicit and recoverable in both apps.

## Rollback Plan

1. Disable V2 flags in env (teacher/student independently).
2. Keep old shell components intact until two stable releases.
3. If localStorage mismatch appears, schema migrator falls back to v1 parser.

---

## Reflection Round 1 (Post-V1 Critique)

**Problems found in V1:**
- Too much UI surface changed before state contract hardening.
- Risk of hidden coupling between sheet transitions and pending job restoration.
- Testing emphasis was strong, but observability and rollback telemetry were under-specified.

**Revision after Round 1:**
1. Moved stream/state contract tasks (Task 11/12) earlier in priority for implementation sequence.
2. Added explicit requirement: do not enable mobile sheet behavior until stream phase model is merged.
3. Added per-task mobile `data-testid` rule to reduce flaky selectors.
4. Added rollout gate requiring mobile grep suites to pass twice in isolated runs.

---

## Reflection Round 2 (Operational Hardening Critique)

**Problems found after Round 1 revision:**
- Still lacked concrete runbook for mixed deployments where teacher V2 is on and student V2 is off.
- Commit granularity was acceptable but no “stop points” for user acceptance demos.
- Needed stronger protection against long-lived localStorage drift.

**Revision after Round 2 (Final V3 Plan):**
1. Add stop points after Task 7 (teacher demo) and Task 10 (student demo) before continuing.
2. Add rollout matrix:
   - Stage A: teacher V2 on (staging only), student V2 off
   - Stage B: both V2 on (staging)
   - Stage C: 10% production teacher, then student
3. Add storage hygiene check command to QA checklist:
   - clear old keys and verify migration path with seeded v1 payload snapshots.
4. Add explicit success SLA:
   - zero P0 mobile UI regression in 7 days,
   - mobile key flows p95 interaction latency < 150ms for tab/sheet transitions.

---

## Recommended Execution Order (from final V3)

1. Task 1 -> Task 2 -> Task 11 -> Task 12
2. Task 3 -> Task 4 -> Task 5 -> Task 6 -> Task 7
3. **Stop Point A: Teacher UAT demo**
4. Task 8 -> Task 9 -> Task 10
5. **Stop Point B: Student UAT demo**
6. Task 13 -> Task 14

