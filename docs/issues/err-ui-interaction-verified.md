# 基于 `err.txt` 的问题核验与 Issue 草稿（可直接复制粘贴）

日期：2026-02-08  
范围：`/Users/lvxiaoer/Documents/New project/frontend/apps/{teacher,student}`  
说明：本文件将 `err.txt` 中的“架构/交互/安全”项转成可落地的 Issue，并给出可复现/可验证的证据（命令 + 指标 + 位置）。

---

## Issue 1 — [P1] `App.tsx` 仍然偏大（Teacher 2439 LOC / Student 1171 LOC）

### 证据（硬指标）
- LOC：
  - `wc -l frontend/apps/teacher/src/App.tsx` → `2439`
  - `wc -l frontend/apps/student/src/App.tsx` → `1171`
- Teacher 组件规模仍然偏“单体”，难以做局部修改与回归测试隔离。

### 当前状态
- **已达成 DoD**：Teacher `App.tsx` 从约 4600+ 行降到 2439；Student `App.tsx` 从 1700+ 行降到 1171（进一步抽出 session sidebar/topbar 与 types 到独立文件）。

### 建议拆分方向（不改行为的安全重构优先）
- Teacher：继续抽 `SessionSidebar`、`ChatComposer`、`ChatMessages`、`Uploads/Workflow`、`Settings` 等为 feature 组件，并把纯函数移出。
- Student：继续抽 `history/session loader`、`assignment` 拉取、以及 sidebar 渲染到 `features/*`，避免在根组件内堆叠（`viewState`/`pending overlay` 已拆到 `apps/student/src/features/chat/*`）。

### 验收标准（DoD）
- Teacher `App.tsx` ≤ 2500 行（或按模块拆分后根组件只保留路由/布局/顶层状态拼装）。
- Student `App.tsx` ≤ 1200 行。
- `npm run typecheck && npm run e2e:teacher && npm run e2e:student` 全绿。

---

## Issue 2 — [P1] Teacher 根组件局部状态过多（`useState` 73 / `useEffect` 51）

### 证据（硬指标）
- `rg -c "useState\\(" frontend/apps/teacher/src/App.tsx` → `18`
- `rg -c "useEffect\\(" frontend/apps/teacher/src/App.tsx` → `51`
- `react-hooks/exhaustive-deps` 被显式忽略：`frontend/apps/teacher/src/App.tsx:397`

### 影响（可验证的事实）
- 任意一个 `setState` 都会触发 `App` 重新渲染；在根组件承载大量 UI 时，会放大无关区域的重渲染成本。
- 多处 effect 依赖被忽略会增加“闭包读到旧值”的风险。

### 建议
- 优先把同一域的状态收敛到 `useReducer`（例如：chat job/polling、view-state sync、upload workflow）。
- 或引入轻量全局状态（如 Zustand）承载跨面板共享状态。

### 验收标准（DoD）
- Teacher `App.tsx` 内 `useState` 降到 ≤ 40（其余下沉到子组件或 reducer）。
- 删除/减少 `exhaustive-deps` 忽略点，并补充针对对应行为的 E2E（已有部分覆盖）。

### 当前状态
- **已完成**：将 `TeacherWorkbench` + session/history 相关状态收敛为 reducer（减少根组件的 state hook 数量，并降低跨域 setState 触发的无关重渲染风险）：
  - `frontend/apps/teacher/src/features/state/teacherWorkbenchState.ts`
  - `frontend/apps/teacher/src/features/state/teacherSessionState.ts`

---

## Issue 3 — [P2] 仍在使用原生 `window.prompt/confirm`（体验不一致且不可控）

### 证据（硬指标）
- `rg -n "window\\.(prompt|confirm)\\(" -S .` → **无匹配**

### 当前状态
- **已修复**：Teacher/Student 均替换为自定义对话框组件：
  - `frontend/apps/shared/dialog.tsx`
  - `frontend/apps/shared/dialog.css`
- Teacher 侧 E2E 已从 native dialog 监听改为 UI 交互（更“硬”的验证）：
  - `frontend/e2e/teacher-chat-critical.spec.ts`
  - `frontend/e2e/teacher-chat-regression.spec.ts`

### 验收标准（DoD）
- 全仓库无 `window.prompt/confirm`（或仅限开发模式）。
- E2E 覆盖：重命名/归档对话框可通过键盘操作、Esc 关闭、焦点返回触发点。

---

## Issue 4 — [P2] 手写 `setTimeout` 轮询较多（易出竞态/泄漏/退避不一致）

### 证据（硬指标）
- Teacher：`rg -c "setTimeout\\(" frontend/apps/teacher/src/App.tsx` → `1`
- Student：`rg -c "setTimeout\\(" frontend/apps/student/src/App.tsx` → `4`
- 统一的可见性 + 退避轮询实现已抽到 shared（轮询核心集中，减少重复）：
  - `frontend/apps/shared/visibilityBackoffPolling.ts`（`rg -c "setTimeout\\(" ...` → `1`）

### 建议
- 先抽一个内部 hook（不引入三方库也行）：`usePolling(fn, { interval, jitter, backoff, enabled })`
- 或引入 `TanStack Query/SWR` 统一轮询、缓存与重试策略（属于更大改造，需阶段性推进）。

### 验收标准（DoD）
- 轮询逻辑集中在 1 个 hook（或库），并且每条轮询都有明确的取消条件与退避策略。
- E2E 覆盖“网络抖动重试/最终成功/最终失败”路径（Teacher 侧已有覆盖样例）。

---

## Issue 5 — [P0] `dangerouslySetInnerHTML` 渲染聊天内容：需要持续的 XSS 防护回归

### 证据（位置）
- Student：`frontend/apps/student/src/App.tsx:1129`
- Teacher：`frontend/apps/teacher/src/features/chat/ChatMessages.tsx:41`

### 当前缓解措施（已存在 + 已验证）
- Markdown 渲染走 `rehype-sanitize`（已集中到共享模块）：
  - `frontend/apps/shared/markdown.ts`
- 新增 E2E（硬验证）：
  - `frontend/e2e/security-markdown-sanitize.spec.ts`：常见 payload（`<script>`、`onerror`、`javascript:`、`data:`）不落地到 DOM

### 建议
- 将 XSS 回归测试纳入 CI 必跑集合（目前已被 student/teacher 两套 Playwright config 覆盖）。
- 审视 `katexSchema` 放行的属性集合，避免引入过宽的 allowlist。

### 验收标准（DoD）
- E2E 断言覆盖：`script` 节点为 0、`on*=`/`javascript:`/`data:` 不出现在渲染 HTML 中。
- 若未来调整 sanitize schema，必须同步更新测试用例并保持通过。

---

## 变更记录（与 `err.txt` 的“重复代码”项对应，已完成）

### 已消除的重复（Student/Teacher 共用）
- 安全 localStorage：`frontend/apps/shared/storage.ts`
- 时间/ID：`frontend/apps/shared/time.ts`、`frontend/apps/shared/id.ts`
- Markdown 渲染与图表 URL 绝对化：`frontend/apps/shared/markdown.ts`

### 验证（本次已跑过）
- `cd frontend && npm run typecheck`
- `cd frontend && npm run e2e:teacher`
- `cd frontend && npm run e2e:student`

### 最新门禁（硬验证，误撤销后重新跑）
- 2026-02-08：`npm run typecheck` ✅
- 2026-02-08：`npm run e2e:teacher` ✅（205 passed）
- 2026-02-08：`npm run e2e:student` ✅（16 passed）

### 额外回归修复（E2E 硬证据）
- 修复：作业确认成功后清理 `teacherActiveUpload`，并处理后端可能返回的终态 `status: "created"`（避免状态卡在“待确认”）。
- E2E：`frontend/e2e/teacher-workbench-flow.spec.ts` 用例 `D011` 覆盖（确认按钮变为“已创建”且 localStorage marker 清空）。
- 修复：`frontend/e2e/teacher-system-filesystem.spec.ts` 的“幂等确认”用例增加 UI 完成态与文件存在性等待，避免因 route 回调写盘时序导致的误报（硬验证更稳）。
