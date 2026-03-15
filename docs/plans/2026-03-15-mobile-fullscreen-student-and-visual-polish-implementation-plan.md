# Mobile Fullscreen Student + Visual Polish Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 把学生端移动体验改成无常驻侧栏的三态全屏切换，并继续压缩老师端右栏噪音、拉开整套界面的视觉等级。

**Architecture:** 保持现有学生/老师状态模型、接口协议和主组件树不变，优先通过展示层重排与导航语义收敛完成这轮改版。学生端移动壳改成 `学习 / 会话 / 聊天` 三个全屏模式，桌面端结构保持不变；老师端继续保留双栏，但把右栏降成摘要和入口，避免与主聊天区竞争。

**Tech Stack:** React 19 + TypeScript + Tailwind CSS 4 + Vitest + Testing Library + Playwright

---

## Scope

- In scope:
  - 学生端移动壳去掉常驻侧栏感，改成全屏 tab 模式
  - 学生端移动顶部/底部导航语义去重
  - 学生端首页主任务卡继续强化，辅助区继续降噪
  - 老师端右栏进一步去模块化、去竞争化
  - 统一调整老师/学生的 CTA 与容器色彩权重
  - 更新截图脚本并生成新截图
- Out of scope:
  - 后端接口变更
  - 会话/聊天业务状态机重写
  - 新的老师工作流功能
  - 学生端新增第四个底部入口

## Execution Order

1. 先把学生移动端改成真正的三态全屏，消除“桌面侧栏硬压到手机上”的问题。
2. 再清理移动端重复导航，收拢入口语义。
3. 然后继续拉开学生首页主次层级。
4. 再压老师右栏噪音与模块密度。
5. 最后统一做颜色权重整理、截图与回归验证。

---

### Task 1: Convert student mobile shell into full-screen `learning / sessions / chat` modes

**Files:**
- Modify: `frontend/apps/student/src/App.tsx`
- Modify: `frontend/apps/student/src/features/layout/mobileShellState.ts`
- Modify: `frontend/apps/student/src/features/chat/SessionSidebar.tsx`
- Modify: `frontend/apps/student/src/features/chat/sessionSidebarTypes.ts`
- Modify: `frontend/apps/student/src/features/chat/SessionSidebarHistorySection.tsx`
- Test: `frontend/apps/student/src/features/layout/mobileShellState.test.ts`
- Test: `frontend/e2e/student-session-sidebar.spec.ts`
- Test: `frontend/e2e/student-learning-loop.spec.ts`

**Step 1: Write the failing tests**
- 在 `mobileShellState.test.ts` 增加断言：
  - 移动端 `learning` 只展开今日首页，不展开会话侧栏。
  - 移动端 `sessions` 只展开历史会话主列表，不保留聊天主区。
  - 选择会话后，模式自动切到 `chat`。
- 在 `student-session-sidebar.spec.ts` 增加断言：
  - `学习` tab 下看不到历史会话容器。
  - `会话` tab 下看不到聊天输入框与今日任务主卡。
  - `聊天` tab 下看不到历史会话列表。
  - 在 `会话` tab 选中会话后自动回到 `聊天` tab。
- 在 `student-learning-loop.spec.ts` 增加断言：
  - 首屏仍是 `student-today-home`。
  - 点击主 CTA 后进入 `聊天` tab，而不是带着半展开侧栏进入聊天态。

**Step 2: Run tests to verify they fail**
- Run: `cd frontend && npm run test:unit -- apps/student/src/features/layout/mobileShellState.test.ts`
- Run: `cd frontend && npm run e2e:student -- e2e/student-session-sidebar.spec.ts`
- Run: `cd frontend && npm run e2e:student -- e2e/student-learning-loop.spec.ts`
- Expected: FAIL，当前移动端仍保留 `sidebarOpen` 语义，`会话` 与 `聊天` 还不是完全分离的全屏模式。

**Step 3: Write minimal implementation**
- 在 `App.tsx` 中把移动端三态改成真正的全屏主视图切换：
  - `learning` 渲染 `StudentTodayHome`
  - `sessions` 渲染历史会话全屏视图
  - `chat` 渲染 `ChatPanel`
- 移动端不再依赖常驻 `sidebarOpen` 决定主舞台；`sidebarOpen` 仅保留桌面端行为。
- `SessionSidebar.tsx` 在移动全屏模式下只渲染必要内容，不再承载“覆盖在聊天旁边”的结构。
- 选中会话、新建会话、恢复远端活跃会话后，移动端应稳定回到 `chat` 模式。

**Step 4: Run tests to verify they pass**
- Run: `cd frontend && npm run test:unit -- apps/student/src/features/layout/mobileShellState.test.ts`
- Run: `cd frontend && npm run e2e:student -- e2e/student-session-sidebar.spec.ts`
- Run: `cd frontend && npm run e2e:student -- e2e/student-learning-loop.spec.ts`
- Expected: PASS。

**Step 5: Commit**
- Run:
```bash
cd frontend
git add apps/student/src/App.tsx \
  apps/student/src/features/layout/mobileShellState.ts \
  apps/student/src/features/chat/SessionSidebar.tsx \
  apps/student/src/features/chat/sessionSidebarTypes.ts \
  apps/student/src/features/chat/SessionSidebarHistorySection.tsx \
  apps/student/src/features/layout/mobileShellState.test.ts \
  e2e/student-session-sidebar.spec.ts \
  e2e/student-learning-loop.spec.ts
git commit -m "feat: make student mobile shell fullscreen by tab"
```

---

### Task 2: Remove duplicated mobile navigation and simplify the student compact topbar

**Files:**
- Modify: `frontend/apps/student/src/features/layout/StudentTopbar.tsx`
- Modify: `frontend/apps/student/src/App.tsx`
- Modify: `frontend/apps/student/src/tailwind.css`
- Test: `frontend/apps/student/src/features/layout/StudentTopbar.test.tsx`
- Test: `frontend/e2e/student-session-sidebar.spec.ts`

**Step 1: Write the failing tests**
- 在 `StudentTopbar.test.tsx` 增加断言：
  - 紧凑移动模式下不再出现和底部 tab 重复的 `会话 / 今日任务` 双入口组合。
  - 顶部保留品牌、必要身份信息和 `更多`，不再承担模式切换。
  - `更多` 菜单仍保留 `新建会话` 等次级动作。
- 在 `student-session-sidebar.spec.ts` 增加断言：
  - 移动端切换 `学习 / 会话 / 聊天` 仅通过底部 tab 完成。
  - 顶部不再出现会误导为“第二套导航”的按钮文案。

**Step 2: Run tests to verify they fail**
- Run: `cd frontend && npm run test:unit -- apps/student/src/features/layout/StudentTopbar.test.tsx`
- Run: `cd frontend && npm run e2e:student -- e2e/student-session-sidebar.spec.ts --grep "mobile"`
- Expected: FAIL，当前紧凑 topbar 仍有重复的模式按钮。

**Step 3: Write minimal implementation**
- 移动紧凑 topbar 只保留：
  - 产品名
  - 当前学生信息的轻量展示或 `更多` 中展示
  - `更多` 菜单
- 把 `今日任务` 和 `会话开/会话` 这类模式入口从移动 topbar 移除。
- 在 `tailwind.css` 中重新调整紧凑 topbar 的间距、宽度和截断策略，避免顶部条过满。

**Step 4: Run tests to verify they pass**
- Run: `cd frontend && npm run test:unit -- apps/student/src/features/layout/StudentTopbar.test.tsx`
- Run: `cd frontend && npm run e2e:student -- e2e/student-session-sidebar.spec.ts --grep "mobile"`
- Expected: PASS。

**Step 5: Commit**
- Run:
```bash
cd frontend
git add apps/student/src/features/layout/StudentTopbar.tsx \
  apps/student/src/App.tsx \
  apps/student/src/tailwind.css \
  apps/student/src/features/layout/StudentTopbar.test.tsx \
  e2e/student-session-sidebar.spec.ts
git commit -m "feat: simplify student mobile topbar navigation"
```

---

### Task 3: Strengthen student today-home hierarchy after mobile shell cleanup

**Files:**
- Modify: `frontend/apps/student/src/features/home/StudentTodayHome.tsx`
- Modify: `frontend/apps/student/src/features/home/TodayHero.tsx`
- Modify: `frontend/apps/student/src/features/home/TodayTaskCard.tsx`
- Modify: `frontend/apps/student/src/features/home/TaskMaterialList.tsx`
- Modify: `frontend/apps/student/src/features/home/LearningProgressRail.tsx`
- Modify: `frontend/apps/student/src/tailwind.css`
- Test: `frontend/apps/student/src/features/home/StudentTodayHome.test.tsx`
- Test: `frontend/e2e/student-learning-loop.spec.ts`

**Step 1: Write the failing tests**
- 在 `StudentTodayHome.test.tsx` 增加断言：
  - 主任务卡仍是唯一一级 CTA 舞台。
  - 材料区与进度区在 DOM 语义和测试标识上属于辅助层。
  - 历史与补充入口权重低于主 CTA，不再和主按钮同级。
- 在 `student-learning-loop.spec.ts` 增加断言：
  - 首屏先看见主任务标题和唯一主按钮。
  - 历史入口存在，但在交互顺序上位于主任务之后。

**Step 2: Run tests to verify they fail**
- Run: `cd frontend && npm run test:unit -- apps/student/src/features/home/StudentTodayHome.test.tsx`
- Run: `cd frontend && npm run e2e:student -- e2e/student-learning-loop.spec.ts`
- Expected: FAIL，当前首页层级虽已改善，但还不够极端。

**Step 3: Write minimal implementation**
- 放大 `TodayHero` 与主任务卡之间的层级差：
  - 主标题更明确
  - 主任务卡更完整
  - 主按钮更集中
- 降低材料区、进度区和历史补充区的边框与底色对比度。
- 移动端首页增加更明显的“完整首页”感，不再像桌面卡片的缩小版。

**Step 4: Run tests to verify they pass**
- Run: `cd frontend && npm run test:unit -- apps/student/src/features/home/StudentTodayHome.test.tsx`
- Run: `cd frontend && npm run e2e:student -- e2e/student-learning-loop.spec.ts`
- Expected: PASS。

**Step 5: Commit**
- Run:
```bash
cd frontend
git add apps/student/src/features/home/StudentTodayHome.tsx \
  apps/student/src/features/home/TodayHero.tsx \
  apps/student/src/features/home/TodayTaskCard.tsx \
  apps/student/src/features/home/TaskMaterialList.tsx \
  apps/student/src/features/home/LearningProgressRail.tsx \
  apps/student/src/tailwind.css \
  apps/student/src/features/home/StudentTodayHome.test.tsx \
  e2e/student-learning-loop.spec.ts
git commit -m "feat: strengthen student today-home hierarchy"
```

---

### Task 4: Further reduce teacher right-rail competition and keep the chat stage dominant

**Files:**
- Modify: `frontend/apps/teacher/src/features/workbench/TeacherWorkbench.tsx`
- Modify: `frontend/apps/teacher/src/features/workbench/tabs/WorkflowTab.tsx`
- Modify: `frontend/apps/teacher/src/features/workbench/tabs/SkillsTab.tsx`
- Modify: `frontend/apps/teacher/src/features/layout/TeacherTopbar.tsx`
- Modify: `frontend/apps/teacher/src/features/layout/TeacherAdminPanel.tsx`
- Modify: `frontend/apps/teacher/src/tailwind.css`
- Test: `frontend/apps/teacher/src/features/workbench/TeacherWorkbench.test.tsx`
- Test: `frontend/apps/teacher/src/features/workbench/tabs/WorkflowTab.test.tsx`
- Test: `frontend/apps/teacher/src/features/layout/TeacherTopbar.test.tsx`
- Test: `frontend/e2e/teacher-layout-sentinel.spec.ts`
- Test: `frontend/e2e/teacher-workbench-flow.spec.ts`

**Step 1: Write the failing tests**
- 在 `TeacherWorkbench.test.tsx` 增加断言：
  - 右栏默认只保留流程摘要、入口 CTA、轻量 tab 切换。
  - `当前焦点` 保留，但补充模块默认更弱。
- 在 `WorkflowTab.test.tsx` 增加断言：
  - 工作流页的“必做动作”与“补充参考”层级差进一步拉开。
- 在 `TeacherTopbar.test.tsx` 增加断言：
  - 管理面板打开后仍不会在视觉和结构上压过主聊天区。
- 在 `teacher-layout-sentinel.spec.ts` 与 `teacher-workbench-flow.spec.ts` 增加断言：
  - 主区聊天舞台宽度、阅读重心和 CTA 抓力高于右栏。

**Step 2: Run tests to verify they fail**
- Run: `cd frontend && npm run test:unit -- apps/teacher/src/features/workbench/TeacherWorkbench.test.tsx apps/teacher/src/features/workbench/tabs/WorkflowTab.test.tsx apps/teacher/src/features/layout/TeacherTopbar.test.tsx`
- Run: `cd frontend && npm run e2e:teacher -- e2e/teacher-layout-sentinel.spec.ts`
- Run: `cd frontend && npm run e2e:teacher -- e2e/teacher-workbench-flow.spec.ts`
- Expected: FAIL，当前老师右栏仍有“空的很空，挤的很挤”的竞争感。

**Step 3: Write minimal implementation**
- `TeacherWorkbench.tsx`：
  - 缩减右栏模块边框密度
  - 压缩次级按钮和说明文案
  - 保持主 CTA 醒目但减少重复容器
- `WorkflowTab.tsx`：
  - 进一步明确“主线流程”与“补充参考”的分区视觉差
- `SkillsTab.tsx`：
  - 非激活态继续降噪，避免能力卡抢主任务
- `TeacherTopbar.tsx` / `TeacherAdminPanel.tsx`：
  - 管理浮层边界和分组标题更清晰，但整体更像工具抽屉而不是第二工作区
- `tailwind.css`：
  - 调整老师端摘要区、边框、背景层级

**Step 4: Run tests to verify they pass**
- Run: `cd frontend && npm run test:unit -- apps/teacher/src/features/workbench/TeacherWorkbench.test.tsx apps/teacher/src/features/workbench/tabs/WorkflowTab.test.tsx apps/teacher/src/features/layout/TeacherTopbar.test.tsx`
- Run: `cd frontend && npm run e2e:teacher -- e2e/teacher-layout-sentinel.spec.ts`
- Run: `cd frontend && npm run e2e:teacher -- e2e/teacher-workbench-flow.spec.ts`
- Expected: PASS。

**Step 5: Commit**
- Run:
```bash
cd frontend
git add apps/teacher/src/features/workbench/TeacherWorkbench.tsx \
  apps/teacher/src/features/workbench/tabs/WorkflowTab.tsx \
  apps/teacher/src/features/workbench/tabs/SkillsTab.tsx \
  apps/teacher/src/features/layout/TeacherTopbar.tsx \
  apps/teacher/src/features/layout/TeacherAdminPanel.tsx \
  apps/teacher/src/tailwind.css \
  apps/teacher/src/features/workbench/TeacherWorkbench.test.tsx \
  apps/teacher/src/features/workbench/tabs/WorkflowTab.test.tsx \
  apps/teacher/src/features/layout/TeacherTopbar.test.tsx \
  e2e/teacher-layout-sentinel.spec.ts \
  e2e/teacher-workbench-flow.spec.ts
git commit -m "feat: reduce teacher right rail visual competition"
```

---

### Task 5: Rebalance CTA color weight and refresh screenshot regression artifacts

**Files:**
- Modify: `frontend/apps/student/src/tailwind.css`
- Modify: `frontend/apps/teacher/src/tailwind.css`
- Modify: `frontend/output/playwright/ui-review/capture-ui-review.mjs`
- Test: `frontend/e2e/student-session-sidebar.spec.ts`
- Test: `frontend/e2e/student-learning-loop.spec.ts`
- Test: `frontend/e2e/teacher-layout-sentinel.spec.ts`
- Test: `frontend/e2e/teacher-workbench-flow.spec.ts`

**Step 1: Write the failing test or sentinel assertion**
- 在现有 E2E 中补充轻量断言：
  - 学生端移动 `学习` 和 `会话` 截图差异明显。
  - 学生端主 CTA 比辅助按钮更醒目。
  - 老师端右栏 CTA 可见，但不通过更重的背景块压过顶部任务条。
- 如需更直接，可在 `capture-ui-review.mjs` 中加入当前文案和视图的等待条件，确保截图落在正确状态。

**Step 2: Run verification to confirm current visuals are not yet at target**
- Run: `cd frontend && npm run e2e:student -- e2e/student-session-sidebar.spec.ts`
- Run: `cd frontend && npm run e2e:teacher -- e2e/teacher-layout-sentinel.spec.ts`
- Run: `cd frontend && node output/playwright/ui-review/capture-ui-review.mjs`
- Expected: 即使测试不红，也能通过截图看出 CTA 与容器权重尚未充分拉开；把这一步作为视觉基线记录。

**Step 3: Write minimal implementation**
- 在 `apps/student/src/tailwind.css` 与 `apps/teacher/src/tailwind.css` 中统一调整：
  - 主 CTA 使用更集中、更明确的品牌色权重
  - 大面积容器退回更克制的中性色
  - 辅助按钮与说明块进一步弱化
- 更新 `capture-ui-review.mjs`，确保截图命中新的 `学习 / 会话 / 工作流编辑 / 管理面板分组` 状态。

**Step 4: Run full regression and capture fresh screenshots**
- Run: `cd frontend && npm run typecheck`
- Run: `cd frontend && npm run build:teacher`
- Run: `cd frontend && npm run build:student`
- Run: `cd frontend && npm run e2e:teacher -- e2e/teacher-workbench-flow.spec.ts`
- Run: `cd frontend && npm run e2e:teacher -- e2e/teacher-layout-sentinel.spec.ts`
- Run: `cd frontend && npm run e2e:student -- e2e/student-learning-loop.spec.ts`
- Run: `cd frontend && npm run e2e:student -- e2e/student-session-sidebar.spec.ts`
- Run teacher preview on `4176`
- Run student preview on `4177`
- Run: `cd frontend && node output/playwright/ui-review/capture-ui-review.mjs`
- Expected: PASS，并产出新截图。

**Step 5: Commit**
- Run:
```bash
cd frontend
git add apps/student/src/tailwind.css \
  apps/teacher/src/tailwind.css \
  output/playwright/ui-review/capture-ui-review.mjs \
  e2e/student-session-sidebar.spec.ts \
  e2e/student-learning-loop.spec.ts \
  e2e/teacher-layout-sentinel.spec.ts \
  e2e/teacher-workbench-flow.spec.ts
git commit -m "feat: rebalance visual hierarchy across student and teacher"
```

