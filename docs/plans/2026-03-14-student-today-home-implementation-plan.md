# Student Today-First Homepage Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在不改后端 API 的前提下，把学生端默认首屏从聊天页切换为 `Today-first` 任务首页，并用统一主任务卡表达 `待生成 / 生成中 / 未开始 / 进行中 / 已提交` 五种状态。

**Architecture:** 保持现有 `useStudentState`、`useAssignment`、`useSessionManager`、`useChatPolling`、`ChatPanel` 和移动端壳不变，只在学生端增加一个首页层、若干纯展示组件和一组状态映射 selector。`App.tsx` 负责决定当前显示首页还是执行态；首页组件只消费派生后的展示数据，不直接耦合底层业务细节。

**Tech Stack:** React 19 + TypeScript + Tailwind CSS 4 + Vitest + Testing Library + Playwright

---

## Scope

- In scope:
  - 学生端 `Today-first` 首页默认入口
  - 五种首页状态的派生与展示
  - 首页与聊天执行态的切换
  - 学生端首屏视觉 token 与文案层级调整
  - 组件测试与 E2E 回归
- Out of scope:
  - 新增后端接口
  - 新业务状态机
  - 重写聊天、上传、会话历史底层逻辑
  - 老师端改造

## Execution Order

1. 先把首页状态派生逻辑测出来。
2. 再把首页组件骨架做出来。
3. 再把 `App.tsx` 接到首页 / 聊天执行态。
4. 最后统一视觉样式和补 E2E。

---

### Task 1: Add student homepage state selector

**Files:**
- Create: `frontend/apps/student/src/features/home/studentTodayHomeState.ts`
- Create: `frontend/apps/student/src/features/home/studentTodayHomeState.test.ts`
- Modify: `frontend/apps/student/src/appTypes.ts`
- Modify: `frontend/apps/student/src/hooks/useStudentState.ts`

**Step 1: Write the failing test**
- 在 `studentTodayHomeState.test.ts` 增加用例，覆盖：
  - 未验证学生时首页不可进入主流程
  - `assignmentLoading=true` 时返回 `generating`
  - `todayAssignment` 为空且无错误时返回 `pending_generation`
  - 有 `todayAssignment` 且当前会话未开始时返回 `ready`
  - 有 `pendingChatJob` 或活动会话含用户消息时返回 `in_progress`
  - 最近完成回复或任务已提交标记存在时返回 `submitted`

**Step 2: Run test to verify it fails**
- Run: `cd frontend && npm run test:unit -- apps/student/src/features/home/studentTodayHomeState.test.ts`
- Expected: FAIL，缺少 selector 模块和状态类型。

**Step 3: Write minimal implementation**
- 在 `appTypes.ts` 增加首页展示相关类型：
  - `StudentTodayHomeStatus`
  - `StudentTodayHomeViewModel`
- 在 `useStudentState.ts` 保持原状态结构不大改，只补最小必要字段；优先复用现有：
  - `pendingChatJob`
  - `recentCompletedReplies`
  - `todayAssignment`
  - `messages`
  - `activeSessionId`
- 新建 `studentTodayHomeState.ts`：
  - 导出 `buildStudentTodayHomeViewModel`
  - 统一把底层状态映射到 5 种首页状态和一个主 CTA
  - 保证没有“无任务”分支

**Step 4: Run test to verify it passes**
- Run: `cd frontend && npm run test:unit -- apps/student/src/features/home/studentTodayHomeState.test.ts`
- Expected: PASS。

**Step 5: Commit**
```bash
git add frontend/apps/student/src/features/home/studentTodayHomeState.ts frontend/apps/student/src/features/home/studentTodayHomeState.test.ts frontend/apps/student/src/appTypes.ts frontend/apps/student/src/hooks/useStudentState.ts
git commit -m "feat(student-home): add today homepage state selector"
```

---

### Task 2: Build the student homepage presentation components

**Files:**
- Create: `frontend/apps/student/src/features/home/StudentTodayHome.tsx`
- Create: `frontend/apps/student/src/features/home/StudentTodayHome.test.tsx`
- Create: `frontend/apps/student/src/features/home/TodayTaskCard.tsx`
- Create: `frontend/apps/student/src/features/home/TodayHero.tsx`
- Create: `frontend/apps/student/src/features/home/TaskMaterialList.tsx`
- Create: `frontend/apps/student/src/features/home/LearningProgressRail.tsx`

**Step 1: Write the failing test**
- 在 `StudentTodayHome.test.tsx` 增加断言：
  - 渲染今日标题区、主任务卡、材料区、进度区、历史入口
  - 每种状态只出现一个主按钮
  - `pending_generation` 显示 `生成今日任务`
  - `generating` 显示生成中说明且主按钮不可误导点击
  - `ready` 显示 `开始今日任务`
  - `in_progress` 显示 `继续完成`
  - `submitted` 显示 `查看本次提交`

**Step 2: Run test to verify it fails**
- Run: `cd frontend && npm run test:unit -- apps/student/src/features/home/StudentTodayHome.test.tsx`
- Expected: FAIL，首页组件不存在。

**Step 3: Write minimal implementation**
- `StudentTodayHome.tsx` 负责整体区块布局，不放复杂业务逻辑。
- `TodayHero.tsx` 显示日期、标题和一句任务导语。
- `TodayTaskCard.tsx` 作为唯一视觉重心，承载五种状态与唯一 CTA。
- `TaskMaterialList.tsx` 只展示当前任务必需材料，不做宫格式卡片。
- `LearningProgressRail.tsx` 用线性步骤或状态标签表达阶段，不引入图表。
- 首页底部历史入口先做成简洁列表或文本入口，避免和主任务竞争。

**Step 4: Run test to verify it passes**
- Run: `cd frontend && npm run test:unit -- apps/student/src/features/home/StudentTodayHome.test.tsx`
- Expected: PASS。

**Step 5: Commit**
```bash
git add frontend/apps/student/src/features/home/StudentTodayHome.tsx frontend/apps/student/src/features/home/StudentTodayHome.test.tsx frontend/apps/student/src/features/home/TodayTaskCard.tsx frontend/apps/student/src/features/home/TodayHero.tsx frontend/apps/student/src/features/home/TaskMaterialList.tsx frontend/apps/student/src/features/home/LearningProgressRail.tsx
git commit -m "feat(student-home): build today-first homepage components"
```

---

### Task 3: Wire homepage and execution state in the student app shell

**Files:**
- Modify: `frontend/apps/student/src/App.tsx`
- Modify: `frontend/apps/student/src/features/layout/StudentLayout.tsx`
- Modify: `frontend/apps/student/src/features/layout/StudentTopbar.tsx`
- Modify: `frontend/apps/student/src/features/layout/StudentTopbar.test.tsx`
- Modify: `frontend/apps/student/src/features/chat/ChatPanel.tsx`
- Modify: `frontend/apps/student/src/features/layout/mobileShellState.ts`
- Modify: `frontend/apps/student/src/features/layout/mobileShellState.test.ts`

**Step 1: Write the failing test**
- 在 `StudentTopbar.test.tsx` 增加断言：
  - 首页态主文案不再强调“新会话”
  - 首页态优先出现“今日任务”相关入口
  - 紧凑移动端不暴露多余低优先级动作
- 在 `mobileShellState.test.ts` 增加断言：
  - 首页是默认落点
  - 进入执行态后仍可稳定切回学习首页

**Step 2: Run test to verify it fails**
- Run: `cd frontend && npm run test:unit -- apps/student/src/features/layout/StudentTopbar.test.tsx apps/student/src/features/layout/mobileShellState.test.ts`
- Expected: FAIL，因为当前默认仍以聊天 / 会话为中心。

**Step 3: Write minimal implementation**
- `App.tsx`：
  - 通过 `buildStudentTodayHomeViewModel` 生成首页 view model
  - 增加 `home` 与 `execution` 两层显示逻辑
  - 默认在首页态，点击主任务 CTA 后进入聊天执行态
  - 不修改 `ChatPanel` 的聊天行为，只调整入口顺序
- `StudentLayout.tsx`：
  - 允许首页态渲染主内容，不强耦合聊天布局
- `StudentTopbar.tsx`：
  - 将主标题、一级动作改成首页优先级
  - 让“新会话”降级，避免与今日任务抢权重
- `mobileShellState.ts`：
  - 保持原有移动端壳，但把首页作为默认学习入口

**Step 4: Run test to verify it passes**
- Run: `cd frontend && npm run test:unit -- apps/student/src/features/layout/StudentTopbar.test.tsx apps/student/src/features/layout/mobileShellState.test.ts`
- Expected: PASS。

**Step 5: Commit**
```bash
git add frontend/apps/student/src/App.tsx frontend/apps/student/src/features/layout/StudentLayout.tsx frontend/apps/student/src/features/layout/StudentTopbar.tsx frontend/apps/student/src/features/layout/StudentTopbar.test.tsx frontend/apps/student/src/features/chat/ChatPanel.tsx frontend/apps/student/src/features/layout/mobileShellState.ts frontend/apps/student/src/features/layout/mobileShellState.test.ts
git commit -m "feat(student-home): wire homepage into student app shell"
```

---

### Task 4: Refine student theme tokens and homepage visual hierarchy

**Files:**
- Modify: `frontend/apps/student/src/tailwind.css`
- Modify: `frontend/apps/shared/mobile/mobile.css`
- Modify: `frontend/apps/student/src/features/home/StudentTodayHome.tsx`
- Modify: `frontend/apps/student/src/features/chat/SessionSidebar.tsx`
- Modify: `frontend/apps/student/src/features/chat/SessionSidebarLearningSection.tsx`
- Test: `frontend/apps/shared/mobile/mobileStyles.test.ts`

**Step 1: Write the failing test**
- 在 `mobileStyles.test.ts` 增加断言：
  - 学生端定义首页相关语义 token，如：
    - `--color-app-bg`
    - `--color-task-strip`
    - `--color-note`
    - `--color-progress`
  - 共享移动端样式不硬编码老师端风格

**Step 2: Run test to verify it fails**
- Run: `cd frontend && npm run test:unit -- apps/shared/mobile/mobileStyles.test.ts`
- Expected: FAIL，当前学生端 token 仍偏通用后台样式。

**Step 3: Write minimal implementation**
- 在 `tailwind.css` 中把学生端主题调整为“学习桌面”语义：
  - 暖灰背景
  - 更克制的强调色
  - 更清晰的标题层级和分隔节奏
- `StudentTodayHome.tsx`：
  - 减少重复卡片边框
  - 只保留一个主视觉重心
- `SessionSidebar.tsx` 与 `SessionSidebarLearningSection.tsx`：
  - 下调历史会话在首屏心智中的存在感
- `mobile.css`：
  - 保持结构不变，使用语义 token 承载角色差异

**Step 4: Run test to verify it passes**
- Run: `cd frontend && npm run test:unit -- apps/shared/mobile/mobileStyles.test.ts`
- Expected: PASS。

**Step 5: Commit**
```bash
git add frontend/apps/student/src/tailwind.css frontend/apps/shared/mobile/mobile.css frontend/apps/student/src/features/home/StudentTodayHome.tsx frontend/apps/student/src/features/chat/SessionSidebar.tsx frontend/apps/student/src/features/chat/SessionSidebarLearningSection.tsx frontend/apps/shared/mobile/mobileStyles.test.ts
git commit -m "feat(student-home): refine theme tokens and homepage hierarchy"
```

---

### Task 5: Validate homepage behavior with focused E2E coverage

**Files:**
- Modify: `frontend/e2e/student-learning-loop.spec.ts`
- Modify: `frontend/e2e/student-session-sidebar.spec.ts`
- Reuse: `frontend/e2e/helpers/studentHarness.ts`

**Step 1: Write the failing test**
- 在 `student-learning-loop.spec.ts` 增加场景：
  - 默认打开首页而不是直接落到聊天执行态
  - 当 `/assignment/today` 返回可用作业时显示 `开始今日任务`
  - 当路由处于生成中或空返回时显示 `生成今日任务` 或生成中说明
  - 点击主 CTA 后进入执行态并保留当前任务上下文
- 在 `student-session-sidebar.spec.ts` 增加场景：
  - 首页态与执行态切换时移动端面板状态保持稳定

**Step 2: Run test to verify it fails**
- Run: `cd frontend && npm run e2e:student -- e2e/student-learning-loop.spec.ts`
- Run: `cd frontend && npm run e2e:student -- e2e/student-session-sidebar.spec.ts`
- Expected: FAIL，因为当前默认首屏还是聊天中心。

**Step 3: Write minimal implementation**
- 使用现有 e2e mock 方式接管 `/assignment/today` 与聊天启动接口
- 首页默认落点、主 CTA、进入执行态后的上下文都以可见文案和稳定 test id 断言
- 不额外引入复杂测试桩

**Step 4: Run test to verify it passes**
- Run: `cd frontend && npm run e2e:student -- e2e/student-learning-loop.spec.ts`
- Run: `cd frontend && npm run e2e:student -- e2e/student-session-sidebar.spec.ts`
- Expected: PASS。

**Step 5: Final verification**
- Run: `cd frontend && npm run test:unit -- apps/student/src/features/home/studentTodayHomeState.test.ts apps/student/src/features/home/StudentTodayHome.test.tsx apps/student/src/features/layout/StudentTopbar.test.tsx apps/student/src/features/layout/mobileShellState.test.ts`
- Run: `cd frontend && npm run e2e:student -- e2e/student-learning-loop.spec.ts`
- Expected: PASS。

**Step 6: Commit**
```bash
git add frontend/e2e/student-learning-loop.spec.ts frontend/e2e/student-session-sidebar.spec.ts
git commit -m "test(student-home): cover today-first homepage flow"
```

---

## Notes for Implementation

- 首页状态判断优先放在纯 selector 中，不把分支散落在 `App.tsx`
- 首轮实现不要引入新的全局状态管理
- 如果“已提交”难以可靠从现有数据直接推导，优先复用 `recentCompletedReplies`
- 首页 CTA 文案必须全程唯一，避免同时出现两个主操作
- 历史会话与自由提问必须保留，但都降为次级入口

## Recommended Commands

- Focused unit tests:
  - `cd frontend && npm run test:unit -- apps/student/src/features/home/studentTodayHomeState.test.ts`
  - `cd frontend && npm run test:unit -- apps/student/src/features/home/StudentTodayHome.test.tsx`
  - `cd frontend && npm run test:unit -- apps/student/src/features/layout/StudentTopbar.test.tsx apps/student/src/features/layout/mobileShellState.test.ts`
- Focused E2E:
  - `cd frontend && npm run e2e:student -- e2e/student-learning-loop.spec.ts`
  - `cd frontend && npm run e2e:student -- e2e/student-session-sidebar.spec.ts`

