# Student + Teacher Next Phase Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在现有学生端 `Today-first` 和老师端“精致编辑台”基础上，继续推进下一阶段体验改版，优先解决学生移动端不够 `today-first`、老师端多层信息重复、主区与侧栏失衡的问题。

**Architecture:** 保持现有状态模型、接口协议与主组件树不变，只做展示层重排、默认入口修正、信息降噪和视觉层级强化。所有改动都以现有 worktree 中已落地的学生端首页和老师端工作台为基础，通过单测 + E2E + 截图回归验证。

**Tech Stack:** React 19 + TypeScript + Tailwind CSS 4 + Vitest + Testing Library + Playwright

---

## Scope

- In scope:
  - 学生端移动壳默认进入态修正
  - 学生端首页主次层级强化
  - 教师端顶部条 / 右栏 / 工作流的重复信息去重
  - 教师端主区与右栏密度再平衡
  - 教师管理面板分组重构
  - 截图与重点 E2E 回归
- Out of scope:
  - 新后端接口
  - 新权限模型
  - 聊天协议重写
  - 作业/考试工作流业务状态机变更

## Execution Order

1. 先修学生端移动默认进入态，确保 `today-first` 名副其实。
2. 再压缩老师端重复状态表达，恢复清晰的单层指挥关系。
3. 然后处理教师端主区 / 右栏平衡与管理面板分组。
4. 最后统一做截图与高风险流回归。

---

### Task 1: Fix student mobile default landing so learning opens on today home

**Files:**
- Modify: `frontend/apps/student/src/App.tsx`
- Modify: `frontend/apps/student/src/features/layout/StudentTopbar.tsx`
- Modify: `frontend/apps/shared/mobile/MobileTabBar.tsx`
- Modify: `frontend/apps/student/src/features/chat/SessionSidebar.tsx`
- Modify: `frontend/apps/student/src/features/chat/SessionSidebarHistorySection.tsx`
- Modify: `frontend/apps/student/src/features/chat/SessionSidebarLearningSection.tsx`
- Test: `frontend/apps/student/src/features/layout/StudentTopbar.test.tsx`
- Test: `frontend/e2e/student-session-sidebar.spec.ts`
- Test: `frontend/e2e/student-learning-loop.spec.ts`

**Step 1: Write the failing test**
- 在 `StudentTopbar.test.tsx` 增加断言：
  - 移动紧凑模式下，`今日任务` 仍是可见的一层入口
  - 不会默认把会话抽屉当成学习首页主体
- 在 `student-session-sidebar.spec.ts` 增加断言：
  - 移动端落到 `学习` tab 时先看到 `student-today-home`
  - 只有点击 `会话` tab 才显示历史会话主列表
- 在 `student-learning-loop.spec.ts` 增加断言：
  - 首屏先出现 `开始今日任务`
  - 点击后才进入聊天执行态

**Step 2: Run test to verify it fails**
- Run: `cd frontend && npm run test:unit -- apps/student/src/features/layout/StudentTopbar.test.tsx`
- Run: `cd frontend && npm run e2e:student -- e2e/student-session-sidebar.spec.ts`
- Expected: FAIL，当前移动学习入口仍被会话层抢走首屏。

**Step 3: Write minimal implementation**
- 在 `App.tsx` 中把移动 `learning` tab 的默认内容固定为今日首页主视图。
- 会话列表只在 `sessions` tab 或显式打开会话层时展示。
- 保持现有底部 `聊天 / 会话 / 学习` 三标签，不新增第四个入口。
- `StudentTopbar.tsx` 保留 `今日任务` 入口，但不再让它与会话态产生视觉冲突。
- `SessionSidebar*` 仅保留列表职责，不承担首页主舞台职责。

**Step 4: Run test to verify it passes**
- Run: `cd frontend && npm run test:unit -- apps/student/src/features/layout/StudentTopbar.test.tsx`
- Run: `cd frontend && npm run e2e:student -- e2e/student-session-sidebar.spec.ts`
- Run: `cd frontend && npm run e2e:student -- e2e/student-learning-loop.spec.ts`
- Expected: PASS。

---

### Task 2: Strengthen student homepage hierarchy and reduce sidebar competition

**Files:**
- Modify: `frontend/apps/student/src/features/home/StudentTodayHome.tsx`
- Modify: `frontend/apps/student/src/features/home/TodayTaskCard.tsx`
- Modify: `frontend/apps/student/src/features/home/TodayHero.tsx`
- Modify: `frontend/apps/student/src/features/home/TaskMaterialList.tsx`
- Modify: `frontend/apps/student/src/features/home/LearningProgressRail.tsx`
- Modify: `frontend/apps/student/src/features/chat/SessionSidebar.tsx`
- Modify: `frontend/apps/student/src/tailwind.css`
- Modify: `frontend/apps/shared/mobile/mobile.css`
- Test: `frontend/apps/student/src/features/home/StudentTodayHome.test.tsx`

**Step 1: Write the failing test**
- 在 `StudentTodayHome.test.tsx` 增加断言：
  - 任务主卡仍是唯一一级 CTA 容器
  - “历史与补充”区权重低于主任务卡
  - 材料区和进度区在视觉语义上是辅助层，不与主 CTA 抢注意力

**Step 2: Run test to verify it fails**
- Run: `cd frontend && npm run test:unit -- apps/student/src/features/home/StudentTodayHome.test.tsx`
- Expected: FAIL，当前首页虽然结构正确，但主次层级还不够明显。

**Step 3: Write minimal implementation**
- 放大 `TodayHero` 与主任务卡之间的阅读节奏，让标题 → 主卡 → CTA 成为稳定视线顺序。
- 下调“历史与补充”按钮存在感，避免与主按钮同权。
- 收紧左栏会话搜索和列表边框存在感，避免桌面端左栏比今日内容更显眼。
- 在移动端通过 token 强化 `学习` 页的首页感，而不是继续使用会话页视觉语言。

**Step 4: Run test to verify it passes**
- Run: `cd frontend && npm run test:unit -- apps/student/src/features/home/StudentTodayHome.test.tsx`
- Expected: PASS。

---

### Task 3: Remove duplicate status messaging across teacher task strip, summary rail, and workflow

**Files:**
- Modify: `frontend/apps/teacher/src/features/layout/TeacherTaskStrip.tsx`
- Modify: `frontend/apps/teacher/src/features/layout/TeacherTaskStrip.test.tsx`
- Modify: `frontend/apps/teacher/src/features/workbench/TeacherWorkbench.tsx`
- Modify: `frontend/apps/teacher/src/features/workbench/TeacherWorkbench.test.tsx`
- Modify: `frontend/apps/teacher/src/features/workbench/workflow/WorkflowSummaryCard.tsx`
- Modify: `frontend/apps/teacher/src/features/workbench/workflow/WorkflowSummaryCard.test.tsx`
- Modify: `frontend/apps/teacher/src/features/workbench/tabs/WorkflowTab.tsx`
- Modify: `frontend/apps/teacher/src/features/workbench/tabs/WorkflowTab.test.tsx`
- Test: `frontend/e2e/teacher-workbench-flow.spec.ts`

**Step 1: Write the failing test**
- 在 `TeacherWorkbench.test.tsx` 和 `WorkflowSummaryCard.test.tsx` 增加断言：
  - 顶部任务条负责“今日重心 + 下一步 + 主 CTA”
  - 右栏摘要只显示精简状态，不重复完整 `下一步`
  - `WorkflowTab` 负责详细动作，不再复述顶部指挥句
- 在 `teacher-workbench-flow.spec.ts` 增加断言：
  - 页面上不再同时出现三处同义“去上传区 / 下一步 / 未开始”文案

**Step 2: Run test to verify it fails**
- Run: `cd frontend && npm run test:unit -- apps/teacher/src/features/layout/TeacherTaskStrip.test.tsx apps/teacher/src/features/workbench/TeacherWorkbench.test.tsx apps/teacher/src/features/workbench/workflow/WorkflowSummaryCard.test.tsx apps/teacher/src/features/workbench/tabs/WorkflowTab.test.tsx`
- Run: `cd frontend && npm run e2e:teacher -- e2e/teacher-workbench-flow.spec.ts`
- Expected: FAIL，当前三个层级之间仍有较高文案重复度。

**Step 3: Write minimal implementation**
- `TeacherTaskStrip.tsx` 保留最完整的行动指令。
- `TeacherWorkbench.tsx` 的摘要区收缩为状态短句 + 进入工作流入口，不再完整复制主指令。
- `WorkflowSummaryCard.tsx` 保留状态总览与动作目标，但去掉与顶部完全重复的句式。
- `WorkflowTab.tsx` 专注于“必做动作 / 补充参考”的执行层，不再承担第二个顶部任务条的角色。

**Step 4: Run test to verify it passes**
- Run: `cd frontend && npm run test:unit -- apps/teacher/src/features/layout/TeacherTaskStrip.test.tsx apps/teacher/src/features/workbench/TeacherWorkbench.test.tsx apps/teacher/src/features/workbench/workflow/WorkflowSummaryCard.test.tsx apps/teacher/src/features/workbench/tabs/WorkflowTab.test.tsx`
- Run: `cd frontend && npm run e2e:teacher -- e2e/teacher-workbench-flow.spec.ts`
- Expected: PASS。

---

### Task 4: Rebalance teacher main stage and restructure teacher management panel

**Files:**
- Modify: `frontend/apps/teacher/src/features/workbench/TeacherWorkbench.tsx`
- Modify: `frontend/apps/teacher/src/features/workbench/tabs/SkillsTab.tsx`
- Modify: `frontend/apps/teacher/src/features/workbench/tabs/WorkflowTab.tsx`
- Modify: `frontend/apps/teacher/src/features/layout/TeacherLayout.tsx`
- Modify: `frontend/apps/teacher/src/features/manage/TeacherManagePanel.tsx`
- Modify: `frontend/apps/teacher/src/features/manage/TeacherManagePanel.test.tsx`
- Modify: `frontend/apps/teacher/src/tailwind.css`
- Test: `frontend/e2e/teacher-layout-sentinel.spec.ts`

**Step 1: Write the failing test**
- 在 `TeacherManagePanel.test.tsx` 增加断言：
  - 面板至少分成 `身份验证`、`密码设置`、`学生密码管理` 三组
  - 每组都存在独立标题和辅助说明
- 在 `teacher-layout-sentinel.spec.ts` 增加断言：
  - 主区、右栏都保持可见，且右栏不会吞掉主要阅读重心

**Step 2: Run test to verify it fails**
- Run: `cd frontend && npm run test:unit -- apps/teacher/src/features/manage/TeacherManagePanel.test.tsx`
- Run: `cd frontend && npm run e2e:teacher -- e2e/teacher-layout-sentinel.spec.ts`
- Expected: FAIL，当前管理面板还是连续堆叠，右栏信息密度也偏高。

**Step 3: Write minimal implementation**
- `TeacherWorkbench.tsx` 调整右栏密度：
  - 非当前任务强相关的能力卡和补充模块下沉或折叠
  - 主区消息区保留更稳定的视觉舞台感
- `SkillsTab.tsx` 如果当前不在技能模式，降低抢眼程度。
- `TeacherManagePanel.tsx` 改成明确的分组块结构，每组有单独边界和小标题。
- 在 `tailwind.css` 中为老师端增加更明确的分组、标题和表单层级节奏。

**Step 4: Run test to verify it passes**
- Run: `cd frontend && npm run test:unit -- apps/teacher/src/features/manage/TeacherManagePanel.test.tsx`
- Run: `cd frontend && npm run e2e:teacher -- e2e/teacher-layout-sentinel.spec.ts`
- Expected: PASS。

---

### Task 5: Final screenshot and regression verification for both roles

**Files:**
- Reuse: `frontend/output/playwright/ui-review/capture-ui-review.mjs`
- Modify if needed: `frontend/e2e/teacher-workbench-flow.spec.ts`
- Modify if needed: `frontend/e2e/student-session-sidebar.spec.ts`
- Modify if needed: `frontend/e2e/student-learning-loop.spec.ts`

**Step 1: Run focused validation**
- Run: `cd frontend && npm run typecheck`
- Run: `cd frontend && npm run build:teacher`
- Run: `cd frontend && npm run build:student`
- Run: `cd frontend && npm run e2e:teacher -- e2e/teacher-workbench-flow.spec.ts`
- Run: `cd frontend && npm run e2e:teacher -- e2e/teacher-layout-sentinel.spec.ts`
- Run: `cd frontend && npm run e2e:student -- e2e/student-learning-loop.spec.ts`
- Run: `cd frontend && npm run e2e:student -- e2e/student-session-sidebar.spec.ts`

**Step 2: Capture fresh screenshots**
- Run teacher preview from teacher worktree on `4176`
- Run student preview from student worktree on `4177`
- Run: `cd frontend && node output/playwright/ui-review/capture-ui-review.mjs`

**Step 3: Compare screenshots against the design goals**
- 教师端：
  - 顶部任务条是唯一的主指挥层
  - 右栏不再重复主指令
  - 管理面板分组清楚
- 学生端：
  - 移动端首屏先看到今日任务
  - 学习与会话两个 tab 截图差异明显
  - 桌面首页视线稳定落在主任务卡

**Step 4: Record final artifact paths**
- `output/playwright/ui-review/teacher-desktop-chat-cockpit.png`
- `output/playwright/ui-review/teacher-workflow-timeline.png`
- `output/playwright/ui-review/teacher-manage-panel.png`
- `output/playwright/ui-review/student-desktop-today-home.png`
- `output/playwright/ui-review/student-mobile-today.png`
- `output/playwright/ui-review/student-mobile-records.png`

