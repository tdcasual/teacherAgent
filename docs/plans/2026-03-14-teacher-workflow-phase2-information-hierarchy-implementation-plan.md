# Teacher Workflow Phase 2 Information Hierarchy Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Clarify the teacher workbench workflow tab by separating must-do actions from secondary reference information.

**Architecture:** Keep the existing workflow data model and child sections intact, and only reshape `WorkflowTab` presentation order and shell hierarchy. Add focused tests first to lock the new grouping and ordering, then implement the minimal layout changes and re-run visual verification.

**Tech Stack:** React 19, TypeScript, Vitest, Testing Library, Vite, Playwright

---

### Task 1: Lock the new section hierarchy

**Files:**
- Modify: `/Users/lvxiaoer/Documents/codeWork/teacherAgent/frontend/apps/teacher/src/features/workbench/tabs/WorkflowTab.test.tsx`

**Step 1: Write the failing test**
- Assert the workflow tab exposes `必做` and `按需查看` labels.
- Assert assignment mode places the progress section before the execution timeline inside supplementary content.

**Step 2: Run test to verify it fails**
- Run: `cd /Users/lvxiaoer/Documents/codeWork/teacherAgent/frontend && npm run test:unit -- WorkflowTab.test.tsx`

**Step 3: Write minimal implementation**
- Reshape `WorkflowTab` into two wrapped section shells and reorder supplementary content for assignment mode.

**Step 4: Run test to verify it passes**
- Run: `cd /Users/lvxiaoer/Documents/codeWork/teacherAgent/frontend && npm run test:unit -- WorkflowTab.test.tsx`

### Task 2: Visual refinement and verification

**Files:**
- Modify: `/Users/lvxiaoer/Documents/codeWork/teacherAgent/frontend/apps/teacher/src/features/workbench/tabs/WorkflowTab.tsx`

**Step 1: Add shell-level hierarchy copy**
- Add compact copy that reinforces current-action-first scanning.

**Step 2: Keep secondary information visually quieter**
- Apply softer background/border treatment to the supplementary container.

**Step 3: Run focused verification**
- Run: `cd /Users/lvxiaoer/Documents/codeWork/teacherAgent/frontend && npm run test:unit -- WorkflowTab.test.tsx`

### Task 3: Full validation

**Files:**
- Reuse: `/Users/lvxiaoer/Documents/codeWork/teacherAgent/frontend/output/playwright/ui-review/capture-ui-review.mjs`

**Step 1: Run full checks**
- Run: `cd /Users/lvxiaoer/Documents/codeWork/teacherAgent/frontend && npm run lint && npm run typecheck && npm run build:teacher`

**Step 2: Capture fresh screenshots**
- Run: `node /Users/lvxiaoer/Documents/codeWork/teacherAgent/frontend/output/playwright/ui-review/capture-ui-review.mjs`

**Step 3: Compare the updated workflow sidebar screenshots**
- Inspect the teacher workflow screenshots to confirm the current-action and supplementary groups are visually distinct.
