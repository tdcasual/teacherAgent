# Teacher Workbench Phase 1 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Upgrade the teacher desktop first screen so the task strip and workbench header clearly surface current status and a single next action without changing workflow logic.

**Architecture:** Keep the existing teacher app state model and workflow view model intact, then reshape only the presentation layer for `TeacherTaskStrip` and `TeacherWorkbench`. Add focused component tests first, verify red, implement minimal UI changes, then capture fresh screenshots for comparison.

**Tech Stack:** React 19, TypeScript, Vitest, Testing Library, Vite, Playwright

---

### Task 1: Lock in task strip behavior

**Files:**
- Modify: `/Users/lvxiaoer/Documents/codeWork/teacherAgent/frontend/apps/teacher/src/features/layout/TeacherTaskStrip.tsx`
- Create/Modify: `/Users/lvxiaoer/Documents/codeWork/teacherAgent/frontend/apps/teacher/src/features/layout/TeacherTaskStrip.test.tsx`

**Step 1: Write the failing test**
- Assert the strip renders a stronger action-oriented heading, next-step label, and one primary CTA for each status.

**Step 2: Run test to verify it fails**
- Run: `npm run test:unit -- TeacherTaskStrip.test.tsx`

**Step 3: Write minimal implementation**
- Add CTA prop support and reshape the strip layout into status + action copy + primary button.

**Step 4: Run test to verify it passes**
- Run: `npm run test:unit -- TeacherTaskStrip.test.tsx`

### Task 2: Lock in workbench header behavior

**Files:**
- Modify: `/Users/lvxiaoer/Documents/codeWork/teacherAgent/frontend/apps/teacher/src/features/workbench/TeacherWorkbench.tsx`
- Create/Modify: `/Users/lvxiaoer/Documents/codeWork/teacherAgent/frontend/apps/teacher/src/features/workbench/TeacherWorkbench.test.tsx`

**Step 1: Write the failing test**
- Assert the header shows current status summary, one primary CTA, and secondary refresh/collapse actions while keeping tabs available.

**Step 2: Run test to verify it fails**
- Run: `npm run test:unit -- TeacherWorkbench.test.tsx`

**Step 3: Write minimal implementation**
- Add a workbench summary header driven by the existing view model plus new presentation fields from `App.tsx`.

**Step 4: Run test to verify it passes**
- Run: `npm run test:unit -- TeacherWorkbench.test.tsx`

### Task 3: Wire desktop teacher app presentation

**Files:**
- Modify: `/Users/lvxiaoer/Documents/codeWork/teacherAgent/frontend/apps/teacher/src/App.tsx`

**Step 1: Write/update failing tests if needed**
- Extend component tests only if state-to-CTA mapping cannot be covered at unit level.

**Step 2: Implement minimal mapping**
- Map workflow indicator state to task strip/workbench header copy and target section ids.

**Step 3: Run focused verification**
- Run: `npm run test:unit -- TeacherTaskStrip.test.tsx TeacherWorkbench.test.tsx`

### Task 4: Visual verification

**Files:**
- Reuse: `/Users/lvxiaoer/Documents/codeWork/teacherAgent/output/playwright/ui-review/capture-ui-review.mjs`

**Step 1: Capture updated teacher screenshots**
- Run the existing Playwright capture script against local preview/dev servers.

**Step 2: Inspect screenshots**
- Compare teacher desktop chat/workflow/manage images against the previous UI goals.
