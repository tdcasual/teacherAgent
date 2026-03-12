# Module Boundaries

本文档定义后端与前端的模块边界，目的是降低耦合、减少回归范围、明确改动责任。

## Boundary Rules

1. 依赖方向必须单向：`routes -> application -> domain/services -> infrastructure`。
2. `routes` 仅做协议转换（HTTP 请求/响应），不承载业务编排。
3. `application` 负责用例编排与跨服务组合，不直接依赖 FastAPI 对象。
4. `domain/services` 承载业务规则；可依赖仓储接口，不依赖 HTTP 层。
5. `infrastructure` 负责外部系统与 IO，不反向引用上层业务编排。
6. 对老师高频链路，优先补显式 workflow 编排与前置校验，而不是把业务状态推给自由工具循环。
7. tool loop 是 workflow 的执行器，不是产品主流程的业务真相来源。
8. `tool_dispatch` 是最终工具授权边界；teacher skill 的 tool allow/deny 必须在这里做执行期校验，不能只依赖上游 prompt/runtime 限制。


## Backend Context Boundaries

### Chat Context
- 入口：`services/api/routes/chat_routes.py`
- 应用编排：`services/api/chat_status_service.py`、`services/api/chat_job_processing_service.py`
- 状态规则：`services/api/chat_job_state_machine.py`
- workflow 解析：`services/api/skill_auto_router.py`
- 约束：
  - 所有状态迁移必须通过 `ChatJobStateMachine`
  - 不允许在路由层直接写入 job/lane 持久化状态
  - 老师端 workflow 解释（`requested -> effective -> reason -> confidence`）属于 chat application contract
  - 高频教学场景优先在 chat application 层补 workflow orchestration / preflight，不把“猜下一步”外包给模型

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
  - analysis domain 的 specialist runtime 优先通过 `services/api/domains/runtime_builder.py` 组装；`services/api/wiring/*` 只保留薄封装或兼容入口
  - runtime / report 的 binding 优先由 manifest 元信息声明，并通过统一 resolver 与共享 binding registry 解析；避免在多个中心模块继续扩张 domain 专属 lookup 逻辑
  - analysis report plane 的 domain provider 优先由 manifest 元信息驱动装配，不再在应用层维护一份独立的按域硬编码真相表
  - strategy 元数据若引用不存在的 specialist 或 artifact，必须在装配期直接失败，而不是等运行时静默退化
  - 新增 analysis domain 前，先按 `docs/reference/analysis-domain-onboarding-template.md` 设计 manifest / strategy / report plane / review queue，再进入实现



### Analysis Ops Context
- 在线聚合层：`services/api/analysis_ops_service.py` 只读取持久化 metrics、review feedback 与报告 lineage 元数据，不在 HTTP 请求内做重放 diff。
- 在线写入层：`services/api/review_queue_service.py` 在 review queue 终态迁移时追加 `data/analysis/review_feedback.jsonl`；这属于 ops telemetry，不反向进入 memory 治理链路。
- HTTP 边界：`services/api/routes/analysis_report_routes.py` 仅暴露 `/teacher/analysis/ops` 的协议转换，不承载 compare 编排。
- 离线分析层：`scripts/export_analysis_ops_snapshot.py` 与 `scripts/compare_analysis_runs.py` 负责导出候选与显式 diff，属于 operator tooling，不应被 request path 直接调用。

## Frontend Boundaries (Student App)

- 应用编排入口：`frontend/apps/student/src/App.tsx`
- 聊天主面板：`frontend/apps/student/src/features/chat/ChatPanel.tsx`
- 会话编排与分组：`frontend/apps/student/src/hooks/useSessionManager.ts`
- 侧边栏容器：`frontend/apps/student/src/features/chat/SessionSidebar.tsx`
- 约束：
  - `App.tsx` 只做跨模块状态编排；聊天、会话、认证逻辑必须继续下沉到 `features/*` 或 `hooks/*`
  - 新 UI 区块优先进入 `features/*`，避免将复杂视图回流到 `App.tsx`
  - 会话分组/筛选规则优先放在 selector 或 hook 层，不在页面层重复实现
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
