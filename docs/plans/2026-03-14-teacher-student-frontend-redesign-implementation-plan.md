# Teacher + Student Frontend Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在不改变核心后端契约的前提下，完成老师端“教学作战台”与学生端“学习陪练舱”的前端重构，让两端首屏在 2 秒内可被清晰区分，同时保持现有教学工作流、聊天能力、移动端壳和验证流程可用。

**Architecture:** 这次改造只动前端展示层与组件分层，不新增后端 API。整体方案分为三层：第一层拆分老师端/学生端的语义化 theme token；第二层重构两端首屏信息架构（老师优先显示任务与流程，学生优先显示今日学习与下一步）；第三层统一聊天与移动端细节，去掉通用 SaaS/IM 视觉惯性但保留现有交互能力。

**Tech Stack:** React 19 + TypeScript + Tailwind CSS 4 + react-resizable-panels + Vitest + Playwright

---

## Scope

- In scope:
  - 老师端首屏、顶栏、工作台、聊天区的视觉与层级重构
  - 学生端首屏、学习信息区、聊天区、移动端底栏的视觉与层级重构
  - 老师端/学生端 theme token 拆分
  - 基于现有 Vitest / Playwright 的回归验证
- Out of scope:
  - 后端 API 变更
  - 新数据域、新业务状态机
  - 自定义字体托管/新品牌资产接入
  - 大规模状态管理重写

## Non-goals

1. 不为了“设计感”重写现有业务逻辑。
2. 不新增仅用于炫技的动画系统。
3. 不在第一轮改造里引入两套完全分叉的组件库。
4. 不把移动端改成新的导航模式以外的全新产品流程。

## Execution Order

1. 先拆 token 与共享壳样式。
2. 再做老师端首屏与工作台重心。
3. 再做学生端首屏与学习优先级。
4. 最后统一聊天细节、移动端标签、验证与文档。

---

## Phase 1: Theme Foundation

### Task 1: Split teacher/student semantic theme tokens

**Files:**
- Modify: `frontend/apps/teacher/src/tailwind.css`
- Modify: `frontend/apps/student/src/tailwind.css`
- Modify: `frontend/apps/shared/mobile/mobile.css`
- Test: `frontend/apps/shared/mobile/mobileStyles.test.ts`

**Step 1: Write the failing test**
- 在 `frontend/apps/shared/mobile/mobileStyles.test.ts` 增加断言：
  - `mobile.css` 定义 `--mobile-tabbar-active-bg`、`--mobile-tabbar-active-fg`、`--mobile-sheet-surface`；
  - 老师端 `tailwind.css` 定义新的语义色，如 `--color-app-bg`、`--color-rail`、`--color-panel`、`--color-warning`；
  - 学生端 `tailwind.css` 定义新的语义色，如 `--color-app-bg`、`--color-task-strip`、`--color-note`、`--color-progress`。

**Step 2: Run test to verify it fails**
- Run: `cd frontend && npm run test:unit -- apps/shared/mobile/mobileStyles.test.ts`
- Expected: FAIL，提示缺少新的 CSS 变量或规则。

**Step 3: Write minimal implementation**
- 老师端将当前统一的浅灰绿主题拆成“冷静控制台”语义：
  - `--color-app-bg`
  - `--color-rail`
  - `--color-panel`
  - `--color-accent`
  - `--color-warning`
  - `--color-success`
- 学生端将当前统一主题拆成“暖纸学习”语义：
  - `--color-app-bg`
  - `--color-task-strip`
  - `--color-note`
  - `--color-progress`
  - `--color-accent`
  - `--color-success`
- `apps/shared/mobile/mobile.css` 用共享 CSS 变量替换硬编码 active 色和 sheet 背景色，保留结构，不固定角色视觉。

**Step 4: Run test to verify it passes**
- Run: `cd frontend && npm run test:unit -- apps/shared/mobile/mobileStyles.test.ts`
- Expected: PASS。

**Step 5: Commit**
```bash
git add frontend/apps/teacher/src/tailwind.css frontend/apps/student/src/tailwind.css frontend/apps/shared/mobile/mobile.css frontend/apps/shared/mobile/mobileStyles.test.ts
git commit -m "feat(frontend): split semantic theme tokens for teacher and student"
```

---

## Phase 2: Teacher App — Teaching Operations Cockpit

### Task 2: Add a teacher task strip above the conversation area

**Files:**
- Create: `frontend/apps/teacher/src/features/layout/TeacherTaskStrip.tsx`
- Create: `frontend/apps/teacher/src/features/layout/TeacherTaskStrip.test.tsx`
- Modify: `frontend/apps/teacher/src/App.tsx`
- Modify: `frontend/apps/teacher/src/features/chat/TeacherChatMainContent.tsx`

**Step 1: Write the failing test**
- 在 `frontend/apps/teacher/src/features/layout/TeacherTaskStrip.test.tsx` 增加用例：
  - 渲染当前工作模式（assignment/exam）
  - 渲染当前主状态（处理中 / 待审核 / 已完成）
  - 渲染下一步提示（例如“继续审核草稿”）

**Step 2: Run test to verify it fails**
- Run: `cd frontend && npm run test:unit -- apps/teacher/src/features/layout/TeacherTaskStrip.test.tsx`
- Expected: FAIL，模块不存在。

**Step 3: Write minimal implementation**
- 新建 `TeacherTaskStrip.tsx`，只接受已存在的前端 state 派生值，不引入新业务状态。
- `App.tsx` 从现有 `uploadMode`、`uploadJobInfo`、`examJobInfo`、`draftLoading`、`examDraftLoading`、`progressData`、`analysisReportsSummary` 中组装显示用 props。
- `TeacherChatMainContent.tsx` 在消息区上方渲染任务条，使首屏先表达“当前教学任务”，再进入聊天与执行细节。

**Step 4: Run test to verify it passes**
- Run: `cd frontend && npm run test:unit -- apps/teacher/src/features/layout/TeacherTaskStrip.test.tsx`
- Expected: PASS。

**Step 5: Commit**
```bash
git add frontend/apps/teacher/src/features/layout/TeacherTaskStrip.tsx frontend/apps/teacher/src/features/layout/TeacherTaskStrip.test.tsx frontend/apps/teacher/src/App.tsx frontend/apps/teacher/src/features/chat/TeacherChatMainContent.tsx
git commit -m "feat(teacher-ui): add task strip above conversation area"
```

### Task 3: Simplify teacher topbar and move admin actions out of the main rail

**Files:**
- Create: `frontend/apps/teacher/src/features/layout/TeacherAdminPanel.tsx`
- Modify: `frontend/apps/teacher/src/features/layout/TeacherTopbar.tsx`
- Modify: `frontend/apps/teacher/src/features/layout/TeacherTopbar.test.tsx`
- Modify: `frontend/apps/teacher/src/App.tsx`

**Step 1: Write the failing test**
- 在 `TeacherTopbar.test.tsx` 增加断言：
  - 桌面顶栏只显示“会话 / 工作台 / 设置”一级动作；
  - “教师认证”“学生密码重置”等管理动作不再直接占据一级导航；
  - 管理动作出现在 `TeacherAdminPanel` 或 `更多` 面板内。

**Step 2: Run test to verify it fails**
- Run: `cd frontend && npm run test:unit -- apps/teacher/src/features/layout/TeacherTopbar.test.tsx`
- Expected: FAIL，因为现有顶栏仍直接暴露认证入口和高密度操作。

**Step 3: Write minimal implementation**
- 新建 `TeacherAdminPanel.tsx` 承接教师认证、密码设置、学生密码重置等管理动作。
- `TeacherTopbar.tsx` 只保留：
  - 产品标题
  - 会话开关
  - 工作台开关
  - 设置入口
  - 管理入口（单一按钮）
- `App.tsx` 负责承接顶层面板开关，不修改原有认证/密码重置 API 逻辑。

**Step 4: Run test to verify it passes**
- Run: `cd frontend && npm run test:unit -- apps/teacher/src/features/layout/TeacherTopbar.test.tsx`
- Expected: PASS。

**Step 5: Commit**
```bash
git add frontend/apps/teacher/src/features/layout/TeacherAdminPanel.tsx frontend/apps/teacher/src/features/layout/TeacherTopbar.tsx frontend/apps/teacher/src/features/layout/TeacherTopbar.test.tsx frontend/apps/teacher/src/App.tsx
git commit -m "feat(teacher-ui): simplify topbar and move admin actions to panel"
```

### Task 4: Rebuild the teacher workflow tab around a timeline-first hierarchy

**Files:**
- Create: `frontend/apps/teacher/src/features/workbench/workflow/WorkflowTimeline.tsx`
- Create: `frontend/apps/teacher/src/features/workbench/workflow/WorkflowTimeline.test.tsx`
- Modify: `frontend/apps/teacher/src/features/workbench/tabs/WorkflowTab.tsx`
- Modify: `frontend/apps/teacher/src/features/workbench/workflow/WorkflowSummaryCard.tsx`
- Test: `frontend/e2e/teacher-workbench-flow.spec.ts`

**Step 1: Write the failing test**
- 在 `WorkflowTimeline.test.tsx` 增加断言：
  - 时间线按最近执行顺序渲染节点；
  - 失败/阻塞节点优先高亮；
  - 当无执行记录时显示教学引导空态而不是空白卡片。
- 在 `e2e/teacher-workbench-flow.spec.ts` 增加一个断言：工作流首屏先出现“最近一次执行 / 下一步”，而不是直接落到上传表单。

**Step 2: Run test to verify it fails**
- Run: `cd frontend && npm run test:unit -- apps/teacher/src/features/workbench/workflow/WorkflowTimeline.test.tsx`
- Run: `cd frontend && npm run e2e:teacher -- e2e/teacher-workbench-flow.spec.ts`
- Expected: FAIL，缺少 `WorkflowTimeline` 与新的首屏层级。

**Step 3: Write minimal implementation**
- 新建 `WorkflowTimeline.tsx`，消费现有 `executionTimeline` 数据，不新增 API。
- `WorkflowTab.tsx` 将结构改为：
  1. 当前工作流摘要
  2. 最近执行时间线
  3. 下一步主操作
  4. 次级详情区（上传 / 草稿 / 进度 / 分析）
- `WorkflowSummaryCard.tsx` 只保留首要摘要，不再承担全部信息密度。

**Step 4: Run test to verify it passes**
- Run: `cd frontend && npm run test:unit -- apps/teacher/src/features/workbench/workflow/WorkflowTimeline.test.tsx`
- Run: `cd frontend && npm run e2e:teacher -- e2e/teacher-workbench-flow.spec.ts`
- Expected: PASS。

**Step 5: Commit**
```bash
git add frontend/apps/teacher/src/features/workbench/workflow/WorkflowTimeline.tsx frontend/apps/teacher/src/features/workbench/workflow/WorkflowTimeline.test.tsx frontend/apps/teacher/src/features/workbench/tabs/WorkflowTab.tsx frontend/apps/teacher/src/features/workbench/workflow/WorkflowSummaryCard.tsx frontend/e2e/teacher-workbench-flow.spec.ts
git commit -m "feat(teacher-ui): rebuild workflow tab around execution timeline"
```

### Task 5: Restyle teacher chat surfaces from generic IM to command/result workspace

**Files:**
- Modify: `frontend/apps/teacher/src/features/chat/ChatMessages.tsx`
- Modify: `frontend/apps/teacher/src/features/chat/ChatMessages.test.tsx`
- Modify: `frontend/apps/teacher/src/features/chat/ChatComposer.tsx`
- Modify: `frontend/apps/teacher/src/features/chat/ChatComposer.test.tsx`
- Modify: `frontend/apps/teacher/src/features/chat/TeacherChatMainContent.tsx`

**Step 1: Write the failing test**
- 在 `ChatMessages.test.tsx` 增加断言：
  - 用户消息保留轻量气泡；
  - 助手执行过程渲染为“过程卡片/结果块”而不是单一气泡；
  - 待执行工具状态块有明确标题与状态数。
- 在 `ChatComposer.test.tsx` 增加断言：
  - 组件显示“当前能力/当前任务提示”；
  - 发送按钮文案与提示更像任务指令入口而不是普通 IM。

**Step 2: Run test to verify it fails**
- Run: `cd frontend && npm run test:unit -- apps/teacher/src/features/chat/ChatMessages.test.tsx apps/teacher/src/features/chat/ChatComposer.test.tsx`
- Expected: FAIL，因为当前视觉仍是通用聊天语法。

**Step 3: Write minimal implementation**
- `ChatMessages.tsx`：
  - 将 assistant 输出分为讲解块、过程块、工具状态块三类视觉容器；
  - 保留现有文案与内容，不改消息数据结构。
- `ChatComposer.tsx`：
  - 顶部保留当前能力提示，但调整成“任务上下文条”；
  - 发送区提示改成“输入教学指令或审阅要求”。
- `TeacherChatMainContent.tsx` 负责维持布局节奏，不新增逻辑。

**Step 4: Run test to verify it passes**
- Run: `cd frontend && npm run test:unit -- apps/teacher/src/features/chat/ChatMessages.test.tsx apps/teacher/src/features/chat/ChatComposer.test.tsx`
- Expected: PASS。

**Step 5: Commit**
```bash
git add frontend/apps/teacher/src/features/chat/ChatMessages.tsx frontend/apps/teacher/src/features/chat/ChatMessages.test.tsx frontend/apps/teacher/src/features/chat/ChatComposer.tsx frontend/apps/teacher/src/features/chat/ChatComposer.test.tsx frontend/apps/teacher/src/features/chat/TeacherChatMainContent.tsx
git commit -m "feat(teacher-ui): restyle chat surfaces as command workspace"
```

---

## Phase 3: Student App — Focused Learning Cabin

### Task 6: Add a student daily-focus header ahead of chat

**Files:**
- Create: `frontend/apps/student/src/features/layout/StudentDailyFocus.tsx`
- Create: `frontend/apps/student/src/features/layout/StudentDailyFocus.test.tsx`
- Modify: `frontend/apps/student/src/App.tsx`
- Modify: `frontend/apps/student/src/features/chat/ChatPanel.tsx`

**Step 1: Write the failing test**
- 在 `StudentDailyFocus.test.tsx` 增加断言：
  - 已认证时显示今日作业编号、题数、知识点或下一步建议；
  - 无作业时显示指导性空态；
  - 未认证时不渲染误导性的学习进度块。

**Step 2: Run test to verify it fails**
- Run: `cd frontend && npm run test:unit -- apps/student/src/features/layout/StudentDailyFocus.test.tsx`
- Expected: FAIL，模块不存在。

**Step 3: Write minimal implementation**
- 新建 `StudentDailyFocus.tsx`，只消费现有 `todayAssignment`、`verifiedStudent`、`assignmentLoading`、`assignmentError`。
- `App.tsx` 在聊天区前插入该组件，使学生首屏先看到“今天学什么”。
- `ChatPanel.tsx` 负责把“学习头带 + 消息区 + 输入区”组装为单一壳体。

**Step 4: Run test to verify it passes**
- Run: `cd frontend && npm run test:unit -- apps/student/src/features/layout/StudentDailyFocus.test.tsx`
- Expected: PASS。

**Step 5: Commit**
```bash
git add frontend/apps/student/src/features/layout/StudentDailyFocus.tsx frontend/apps/student/src/features/layout/StudentDailyFocus.test.tsx frontend/apps/student/src/App.tsx frontend/apps/student/src/features/chat/ChatPanel.tsx
git commit -m "feat(student-ui): add daily focus header before chat"
```

### Task 7: Promote learning info above history management in the student sidebar

**Files:**
- Modify: `frontend/apps/student/src/features/chat/SessionSidebar.tsx`
- Modify: `frontend/apps/student/src/features/chat/SessionSidebarLearningSection.tsx`
- Modify: `frontend/apps/student/src/features/chat/SessionSidebarHistorySection.tsx`
- Create: `frontend/apps/student/src/features/chat/SessionSidebarLearningSection.test.tsx`
- Test: `frontend/e2e/student-session-sidebar.spec.ts`

**Step 1: Write the failing test**
- 在 `SessionSidebarLearningSection.test.tsx` 增加断言：
  - 已认证时默认显示学习信息摘要，不默认暴露认证表单；
  - 未认证时显示认证入口与引导文案；
  - 今日作业下载入口在学习信息内可见。
- 在 `student-session-sidebar.spec.ts` 增加断言：移动端打开侧栏时，学习信息区在历史会话之前可见。

**Step 2: Run test to verify it fails**
- Run: `cd frontend && npm run test:unit -- apps/student/src/features/chat/SessionSidebarLearningSection.test.tsx`
- Run: `cd frontend && npm run e2e:student -- e2e/student-session-sidebar.spec.ts`
- Expected: FAIL。

**Step 3: Write minimal implementation**
- `SessionSidebar.tsx` 调整 section 顺序与容器权重：学习信息优先，历史会话次之。
- `SessionSidebarLearningSection.tsx`：
  - 已认证默认显示学习摘要、今日作业、重认证入口；
  - 认证表单折叠到显式展开状态。
- `SessionSidebarHistorySection.tsx` 保留当前历史能力，但视觉降级成“记录区”。

**Step 4: Run test to verify it passes**
- Run: `cd frontend && npm run test:unit -- apps/student/src/features/chat/SessionSidebarLearningSection.test.tsx`
- Run: `cd frontend && npm run e2e:student -- e2e/student-session-sidebar.spec.ts`
- Expected: PASS。

**Step 5: Commit**
```bash
git add frontend/apps/student/src/features/chat/SessionSidebar.tsx frontend/apps/student/src/features/chat/SessionSidebarLearningSection.tsx frontend/apps/student/src/features/chat/SessionSidebarHistorySection.tsx frontend/apps/student/src/features/chat/SessionSidebarLearningSection.test.tsx frontend/e2e/student-session-sidebar.spec.ts
git commit -m "feat(student-ui): prioritize learning information over session history"
```

### Task 8: Redesign student chat surfaces as study notes instead of generic bubbles

**Files:**
- Create: `frontend/apps/student/src/features/chat/ChatMessages.test.tsx`
- Create: `frontend/apps/student/src/features/chat/ChatComposer.test.tsx`
- Modify: `frontend/apps/student/src/features/chat/ChatMessages.tsx`
- Modify: `frontend/apps/student/src/features/chat/ChatComposer.tsx`
- Modify: `frontend/apps/student/src/features/chat/ChatPanel.tsx`

**Step 1: Write the failing test**
- 在新的 `ChatMessages.test.tsx` 中断言：
  - assistant 回复以“讲义块/批注块”呈现；
  - 用户输入仍保留轻气泡；
  - “新消息”按钮继续在离底部时出现。
- 在新的 `ChatComposer.test.tsx` 中断言：
  - 未认证时输入区保持禁用；
  - 已认证时提示文案体现“继续学习/继续提问”；
  - 附件区仍可工作。

**Step 2: Run test to verify it fails**
- Run: `cd frontend && npm run test:unit -- apps/student/src/features/chat/ChatMessages.test.tsx apps/student/src/features/chat/ChatComposer.test.tsx`
- Expected: FAIL，测试文件或新断言尚不存在。

**Step 3: Write minimal implementation**
- `ChatMessages.tsx` 将 assistant 消息容器改为更接近讲义/笔记的块状表达，减少 IM 气泡感。
- `ChatComposer.tsx` 调整 placeholder、hint、发送按钮节奏，使其更像学习动作入口。
- `ChatPanel.tsx` 调整 spacing，使每日学习头带、消息区、输入区形成统一垂直节奏。

**Step 4: Run test to verify it passes**
- Run: `cd frontend && npm run test:unit -- apps/student/src/features/chat/ChatMessages.test.tsx apps/student/src/features/chat/ChatComposer.test.tsx`
- Expected: PASS。

**Step 5: Commit**
```bash
git add frontend/apps/student/src/features/chat/ChatMessages.test.tsx frontend/apps/student/src/features/chat/ChatComposer.test.tsx frontend/apps/student/src/features/chat/ChatMessages.tsx frontend/apps/student/src/features/chat/ChatComposer.tsx frontend/apps/student/src/features/chat/ChatPanel.tsx
git commit -m "feat(student-ui): restyle chat as study-note experience"
```

### Task 9: Update student mobile labels and topbar copy for learning-first navigation

**Files:**
- Modify: `frontend/apps/student/src/App.tsx`
- Modify: `frontend/apps/student/src/features/layout/StudentTopbar.tsx`
- Modify: `frontend/apps/student/src/features/layout/StudentTopbar.test.tsx`
- Test: `frontend/e2e/student-learning-loop.spec.ts`

**Step 1: Write the failing test**
- 在 `StudentTopbar.test.tsx` 增加断言：
  - 顶栏主文案能体现“学习”上下文，而不是通用聊天页；
  - 移动端快捷按钮与标签优先级匹配 `今日 / 对话 / 记录`。
- 在 `student-learning-loop.spec.ts` 增加断言：移动端进入后默认先看到“今日学习”区域。

**Step 2: Run test to verify it fails**
- Run: `cd frontend && npm run test:unit -- apps/student/src/features/layout/StudentTopbar.test.tsx`
- Run: `cd frontend && npm run e2e:student -- e2e/student-learning-loop.spec.ts`
- Expected: FAIL。

**Step 3: Write minimal implementation**
- `App.tsx` 调整 `mobileTabItems` 标签与默认 tab，使移动端优先落在今日学习。
- `StudentTopbar.tsx` 将主文案与按钮标签改为学习优先语义。
- 不修改 `MobileTabBar.tsx` 结构，只通过 props 驱动新信息架构。

**Step 4: Run test to verify it passes**
- Run: `cd frontend && npm run test:unit -- apps/student/src/features/layout/StudentTopbar.test.tsx`
- Run: `cd frontend && npm run e2e:student -- e2e/student-learning-loop.spec.ts`
- Expected: PASS。

**Step 5: Commit**
```bash
git add frontend/apps/student/src/App.tsx frontend/apps/student/src/features/layout/StudentTopbar.tsx frontend/apps/student/src/features/layout/StudentTopbar.test.tsx frontend/e2e/student-learning-loop.spec.ts
git commit -m "feat(student-ui): switch mobile navigation to learning-first copy"
```

---

## Phase 4: Shared Verification and Documentation

### Task 10: Run full frontend verification and update user-facing docs

**Files:**
- Modify: `docs/how-to/teacher-daily-workflow.md`
- Modify: `docs/how-to/student-login-and-submit.md`

**Step 1: Update docs**
- 在 `teacher-daily-workflow.md` 补充老师端首屏改版后的入口说明：任务条、工作台、管理入口位置变化。
- 在 `student-login-and-submit.md` 补充学生端“今日学习头带”、学习信息区与移动端标签变化。

**Step 2: Run lint + format + typecheck**
- Run: `cd frontend && npm run lint && npm run format:check && npm run typecheck`
- Expected: PASS。

**Step 3: Run unit tests**
- Run: `cd frontend && npm run test:unit`
- Expected: PASS。

**Step 4: Run build + critical e2e**
- Run: `cd frontend && npm run build:teacher && npm run build:student`
- Run: `cd frontend && npm run e2e:teacher -- e2e/teacher-workbench-flow.spec.ts`
- Run: `cd frontend && npm run e2e:student -- e2e/student-learning-loop.spec.ts`
- Run: `cd frontend && npm run e2e:mobile-menu`
- Expected: PASS。

**Step 5: Commit**
```bash
git add docs/how-to/teacher-daily-workflow.md docs/how-to/student-login-and-submit.md
git commit -m "docs(frontend): update teacher and student workflow docs for redesigned UI"
```

---

## Definition of Done

- 老师端首屏先表达“当前教学任务 + 工作流状态”，不再像默认聊天工具。
- 学生端首屏先表达“今日学习 + 下一步动作”，不再像学生版客服聊天界面。
- 老师端与学生端的主题 token 明确分离，但共享组件结构仍可复用。
- 桌面端和移动端都不丢失关键操作。
- `npm run verify` 可通过，且教师/学生关键 e2e 回归通过。

## Suggested Execution Slices

1. `Task 1-3`：主题与老师端首屏骨架
2. `Task 4-5`：老师端工作流与聊天区打磨
3. `Task 6-9`：学生端学习优先级改造
4. `Task 10`：全量验证与文档

## Risks to Watch During Implementation

- 不要在视觉重构时改动既有 API payload 或聊天状态机。
- 不要让老师端顶栏减负后导致认证/密码重置入口超过 1 步可达。
- 不要让学生端“今日学习头带”在移动端压缩聊天输入区可用空间。
- 不要把共享组件直接复制两份；优先用语义 token 和局部容器改造。
