# Teacher UI Full Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 完成老师端彻底重构，解决聊天区滚动冲突、入口命名混乱，并落地 `@agent` / `$skill` 输入协议。

**Architecture:** 前端将输入协议解析与滚动控制拆成独立模块，聊天页面保留单一滚动容器并加入“仅在底部自动跟随”策略。后端扩展 `agent_id` 契约并向执行链路透传，保持对旧请求兼容。

**Tech Stack:** React + TypeScript + CSS + FastAPI + Pydantic + pytest/unittest

---

### Task 1: 后端契约扩展（agent_id）

**Files:**
- Modify: `services/api/api_models.py`
- Modify: `services/api/chat_start_service.py`
- Modify: `services/api/chat_job_processing_service.py`
- Modify: `services/api/agent_service.py`
- Modify: `services/api/app.py`
- Test: `tests/test_chat_job_flow.py`

**Step 1: 写失败测试（新增 `agent_id` 透传断言）**
- 在 `tests/test_chat_job_flow.py` 增加用例：`/chat/start` 传入 `agent_id=opencode` 后，`process_chat_job` 调用 `run_agent` 时能收到 `agent_id`。

**Step 2: 运行测试确认失败**
- Run: `pytest tests/test_chat_job_flow.py -q`
- Expected: 新增断言失败（`agent_id` 未透传）。

**Step 3: 最小实现**
- 给 `ChatRequest`/`ChatStartRequest` 增加 `agent_id`。
- `chat_start_service` 在 request payload/job record 中写入 `agent_id`。
- `compute_chat_reply_sync` 与 `run_agent` 调用链新增 `agent_id` 参数并透传。
- `agent_service` 调用 `call_llm` 的 `kind` 改为可包含 agent 维度（非 default 时追加后缀）。

**Step 4: 运行测试确认通过**
- Run: `pytest tests/test_chat_job_flow.py -q`
- Expected: 通过。

### Task 2: 前端输入协议重构（`@agent` / `$skill`）

**Files:**
- Create: `frontend/apps/teacher/src/features/chat/invocation.ts`
- Modify: `frontend/apps/teacher/src/App.tsx`
- Test: `frontend/apps/teacher/src/features/chat/invocation.selftest.mjs`（临时自测脚本）

**Step 1: 写失败测试（解析器）**
- 编写 `invocation.selftest.mjs`，断言：
  - `@opencode $physics-teacher-ops 生成作业` 可解析出 `agent_id` 与 `skill_id`。
  - 清洗后文本不包含召唤 token。
  - 未识别 token 会报 warning。

**Step 2: 运行测试确认失败**
- Run: `node frontend/apps/teacher/src/features/chat/invocation.selftest.mjs`
- Expected: 缺少实现导致失败。

**Step 3: 最小实现**
- 实现 token 解析器：提取/验证 `@agent` 与 `$skill`，返回 `effectiveAgentId/effectiveSkillId/cleanedInput/warnings`。
- 在 `App.tsx` 里替换旧 `@技能` mention 逻辑：
  - `@` 触发 agent 建议；
  - `$` 触发 skill 建议；
  - 发送时传 `agent_id` 与 `skill_id`。

**Step 4: 运行测试确认通过**
- Run: `node frontend/apps/teacher/src/features/chat/invocation.selftest.mjs`
- Expected: 输出所有断言通过。

### Task 3: 滚动与布局重构（单一滚动容器）

**Files:**
- Modify: `frontend/apps/teacher/src/App.tsx`
- Modify: `frontend/apps/teacher/src/styles.css`

**Step 1: 写失败验证（行为回归）**
- 通过人工最小验证脚本/日志点确认旧逻辑会在新消息到来时强制回底。

**Step 2: 最小实现**
- CSS 改造：
  - `chat-shell` 改为 `overflow: hidden`；
  - `messages` 改为 `flex:1; min-height:0; overflow:auto`。
- JS 改造：
  - 删除“消息变化必滚到底”效果；
  - 增加“仅在用户处于底部附近时自动跟随”逻辑；
  - 增加“回到底部”按钮状态。

**Step 3: 运行类型检查与构建**
- Run: `npm --prefix frontend run typecheck`
- Run: `npm --prefix frontend run build:teacher`

### Task 4: 文案与入口统一

**Files:**
- Modify: `frontend/apps/teacher/src/App.tsx`
- Modify: `README.md`

**Step 1: 最小实现**
- `GPTs` 全部改为 `技能`。
- 输入提示从 `@ 技能` 改为 `@ Agent | $ 技能`。
- 顶栏按钮与右侧页签命名保持一致。

**Step 2: 验证**
- Run: `npm --prefix frontend run build:teacher`

### Task 5: 全量验证

**Step 1: 运行后端相关测试**
- Run: `pytest tests/test_chat_job_flow.py tests/test_chat_start_flow.py -q`

**Step 2: 运行前端构建验证**
- Run: `npm --prefix frontend run typecheck && npm --prefix frontend run build:teacher`

**Step 3: 清理临时测试脚本（若为一次性脚本）**
- 删除 `invocation.selftest.mjs`（如不保留）。

