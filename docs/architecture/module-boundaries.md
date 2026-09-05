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
- 应用编排：`services/api/chat_status_service.py`、`services/api/chat_job_processing_service.py`、`services/api/chat_job_processing/`
- 状态规则：`services/api/chat_job_state_machine.py`
- workflow 解析：`services/api/skill_auto_router.py`
- 路由真相优先放在 skill manifest；`services/api/skill_auto_router.py` 负责组合评分与降级，`services/api/skills/auto_route_rules.py` 只保留难以配置化的兜底启发式。
- 约束：
  - 所有状态迁移必须通过 `ChatJobStateMachine`
  - 不允许在路由层直接写入 job/lane 持久化状态
  - 老师端 workflow 解释（`requested -> effective -> reason -> confidence`）属于 chat application contract
  - 高频教学场景优先在 chat application 层补 workflow orchestration / preflight，不把“猜下一步”外包给模型

### Assignment Context
- 入口：`services/api/routes/assignment_routes.py`（listing / upload / delivery / generation）
- 应用编排：`services/api/assignment/application.py`
- 依赖注入：`services/api/assignment/deps.py`
- 学科 pack：`packs/subjects/<id>/`（`pack.yaml` + overlays），装载器 `services/api/subject_pack_service.py`
- 孤儿认领：`POST /auth/admin/assignments/{assignment_id}/claim`（`services/api/routes/auth_identity_route_handlers.py` + `assignment_meta_ownership_migrate_service.claim_assignment`）
- 约束：
  - 路由层仅调用 application 公开函数
  - assignment 编排逻辑不得回流到 `app_core.py`
  - 产品主线是 upload → confirm → progress，不再挂 exam 路由或 exam application
  - 未知 `subject_id` 回退 `packs/subjects/generic/`，禁止回退物理 pack
  - `generic` pack 缺失必须失败，不能静默用其他学科顶上

### Composition Root
- 模块：`services/api/app.py`、`services/api/container.py`
- 约束：
  - 新依赖通过容器挂载到 `app.state.container`
  - 禁止新增模块级全局依赖入口作为默认路径
  - 全员产品面 skill 以 `services/api/skills/product.py` 的 allow-list 为准（作业运营 / 作业生成 / 学生教练）
  - 学科 pack 的 `skill_affiliates` 只对**任教该学科**的老师开放（例如物理老师才看到 `physics-*`）；学生与未任教老师看不到
  - 布置作业走 `subject_id` + 作业工作流，不要求附属 skill
  - 不要在 `create_app()` 装配已卸载的 analysis/survey HTTP 子系统
  - `services/api/wiring/*` 只保留薄封装；作业编排走 `assignment/application.py`

### Leftover analysis / survey
- 考试、问卷、class_report、multimodal/analysis runtime 已从产品面删除，不是现行产品面。
- `docs/reference/analysis-*` 与 `docs/plans/` 中的分析域文档可作历史留存，不是运行时契约，也不是 CI 要求的产品身份。

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

## Frontend Boundaries (Teacher App)

- 应用编排入口：`frontend/apps/teacher/src/App.tsx`
- 应用壳层：`frontend/apps/teacher/src/features/layout/TeacherAppLayout.tsx`
- 顶栏与移动壳：`frontend/apps/teacher/src/features/layout/TeacherTopbar.tsx`、`frontend/apps/teacher/src/features/layout/useTeacherMobileShell.ts`
- 聊天主面板：`frontend/apps/teacher/src/features/chat/TeacherChatMainContent.tsx`
- 会话列表：`frontend/apps/teacher/src/features/chat/SessionSidebar.tsx`、`frontend/apps/teacher/src/features/chat/TeacherSessionRail.tsx`
- 工作台：`frontend/apps/teacher/src/features/workbench/TeacherWorkbench.tsx`
- 待发送 job：`frontend/apps/teacher/src/features/chat/useTeacherPendingChatJob.ts`（必须复用 `frontend/apps/shared/pendingChatJob.ts`，禁止再实现一份 parser）
- 约束：
  - `App.tsx` 只做跨模块状态编排与 hook 装配；壳层 JSX 留在 `TeacherAppLayout`，不得把 `.teacher-layout` / 移动 tab / 会话 sheet 回流到 `App.tsx`
  - 新 UI 区块优先进入 `features/*`，避免将复杂视图回流到 `App.tsx`
  - 布局/顶栏/移动 tab 不承载 chat send、assignment upload/confirm/progress 业务编排
  - `TeacherAppLayout` 可以组合 chat / workbench 表面；`features/chat` 与 `features/workbench` 不得反向依赖 `TeacherAppLayout` 或 `App.tsx`
  - E2E 稳定定位器必须使用 `data-testid`
  - 壳层 class（`.app.teacher`、`.teacher-layout`、`.teacher-mobile-shell-v2`）变更必须跑 `frontend/e2e/teacher-layout-sentinel.spec.ts`

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
