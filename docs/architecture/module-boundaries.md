# Module Boundaries

本文档定义后端与前端的模块边界，目的是降低耦合、减少回归范围、明确改动责任。

## Boundary Rules

1. 依赖方向必须单向：`routes -> application -> domain/services -> infrastructure`。
2. `routes` 仅做协议转换（HTTP 请求/响应），不承载业务编排。
3. `application` 负责用例编排与跨服务组合，不直接依赖 FastAPI 对象。
4. `domain/services` 承载业务规则；可依赖仓储接口，不依赖 HTTP 层。
5. `infrastructure` 负责外部系统与 IO，不反向引用上层业务编排。

## Backend Context Boundaries

### Chat Context
- 入口：`services/api/routes/chat_routes.py`
- 应用编排：`services/api/chat_status_service.py`、`services/api/chat_job_processing_service.py`
- 状态规则：`services/api/chat_job_state_machine.py`
- 约束：
  - 所有状态迁移必须通过 `ChatJobStateMachine`
  - 不允许在路由层直接写入 job/lane 持久化状态

### Exam Context
- 入口：`services/api/routes/exam_routes.py`
- 应用编排：`services/api/exam/application.py`
- 依赖注入：`services/api/exam/deps.py`
- 约束：
  - 任何新的考试聚合逻辑放入 `exam/application.py`
  - `app_core.py` 只保留组合根职责，不新增 exam 编排逻辑

### Assignment Context
- 入口：`services/api/routes/assignment_routes.py`
- 应用编排：`services/api/assignment/application.py`
- 依赖注入：`services/api/assignment/deps.py`
- 约束：
  - 路由层仅调用 application 公开函数
  - assignment 编排逻辑不得回流到 `app_core.py`

### Composition Root
- 模块：`services/api/app.py`、`services/api/container.py`
- 约束：
  - 新依赖通过容器挂载到 `app.state.container`
  - 禁止新增模块级全局依赖入口作为默认路径

## Frontend Boundaries (Student App)

- 会话壳层：`frontend/apps/student/src/features/session/StudentSessionShell.tsx`
- 聊天面板：`frontend/apps/student/src/features/chat/StudentChatPanel.tsx`
- 工作台容器：`frontend/apps/student/src/features/workbench/StudentWorkbench.tsx`
- 约束：
  - `App.tsx` 负责状态管理与编排，不直接扩展大型 UI 结构
  - 新 UI 区块优先进入 `features/*`，避免继续膨胀单文件
  - E2E 稳定定位器必须使用 `data-testid`

## Forbidden Dependency Patterns

- `routes/*` 直接访问底层存储实现（绕过 application/service）
- `application/*` 导入 FastAPI 的 `Request`/`Response`
- `features/*` 之间循环依赖
- 未经容器注册直接读取新的全局 singleton

## Change Checklist

每次跨模块改动前，按以下清单自检：

1. 新增依赖是否符合单向边界？
2. 业务编排是否停留在 application 层？
3. 是否补充/更新了对应 context 的测试？
4. 是否需要在 `docs/architecture/ownership-map.md` 更新责任归属？
