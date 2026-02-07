# App.py Composition Root Design

## Objective

将 `/Users/lvxiaoer/Documents/New project/services/api/app.py` 收敛为严格 Composition Root：仅保留路由定义、请求/响应映射、依赖注入装配、HTTP 错误映射。所有业务逻辑、状态持久化、任务调度、模型调用编排、算法逻辑迁移到独立 service 模块。

## Current State

- 当前 `app.py` 约 9840 行。
- 已完成第一阶段迁移（exam/assignment/chat foundation 等基础 service）。
- 仍有大量编排和领域逻辑残留在 `app.py`（尤其 chat orchestration、teacher memory、startup worker）。

## Design Principles

- Composition Root only：`app.py` 禁止新增业务逻辑。
- 分域绞杀式迁移：每批可独立回滚。
- 行为不变优先：API 契约与 JSON 结构保持稳定。
- YAGNI：只迁移现存逻辑，不引入新能力。
- 反膨胀机制：增加 line budget 和结构 guard 测试。

## Target Responsibilities

### `app.py` allowed

- `@app.get/post/...` 路由注册
- Request DTO 解析与轻量参数校验
- deps factory 组装
- 语义异常到 HTTP 响应映射

### `app.py` forbidden

- 文件/数据库持久化细节
- 队列扫描、重试、worker 循环
- 业务状态机推进
- LLM/agent 业务编排
- teacher memory 算法与评分/冲突处理

## Data Flow

统一采用：

`HTTP Request -> app.py 参数解析 -> service(input,deps) -> service result -> app.py 响应映射`

服务层输出语义异常（如 `not_found`、`conflict`、`invalid_state`、`upstream_error`），`app.py` 负责稳定映射到 4xx/5xx 与现有错误结构。

## Migration Plan (Steady Batch Mode)

### Batch A: Chat Orchestration Extraction

- 迁出 `chat/start/status/worker`、`run_agent`、`call_llm`、队列推进和状态更新逻辑到：
  - `chat_preflight.py`
  - `chat_runtime_service.py`
  - `chat_start_service.py`
  - `chat_worker_service.py`
  - `chat_status_service.py`
  - `chat_job_service.py`
  - `agent_service.py`
- `app.py` 中对应路由改为纯委托 + 映射。
- 验收目标：chat 域测试全绿；`app.py` 目标 `<= 8200` 行。

### Batch B: Teacher Memory Family Extraction

- 迁出 propose/apply/search/insights/auto 等 API 逻辑与算法块到 `teacher_memory_*_service.py`。
- proposal store/scoring/time/conflict/dedupe/session-index 等数据和策略逻辑全部服务化。
- 验收目标：teacher memory 相关 API 与服务测试全绿；`app.py` 目标 `<= 6800` 行。

### Batch C: Teacher Context/Workspace + Lesson/Chart

- 迁出 teacher context/workspace/session compaction 逻辑。
- 迁出 lesson core tool 与 chart agent run 逻辑。
- 验收目标：teacher/chat 联动回归通过；`app.py` 目标 `<= 5600` 行。

### Batch D: Startup/Worker Final Cleanup + Guardrails

- 迁出 startup worker 扫描、调度、重试与线程生命周期管理。
- 删除遗留模板文件：`services/api/* 2.py` 与 `tests/* 2.py`。
- 新增 guardrails：
  - line budget test（最终 `app.py <= 5000`）
  - composition-root structure test（禁止业务实现回流）
- 验收目标：全量回归通过，结构守卫通过。

## Testing Strategy

- 服务单测：覆盖迁出的核心逻辑与状态转换。
- 路由集成测：只验证 HTTP 契约、状态码和响应结构。
- 分批回归：每个 batch 固定最小回归集合。
- 最终回归：`tests` 全量通过 + guardrails 通过。

## Risks and Mitigations

- 风险：迁移时行为漂移（错误码/字段变化）。
  - 缓解：先补路由契约测试，再改委托。
- 风险：跨域依赖导致循环引用。
  - 缓解：统一通过 deps dataclass 注入，禁止 service 直接反向 import `app.py`。
- 风险：大批次改动难排障。
  - 缓解：按 batch 分提交，保持每批可单独回滚。

## Done Definition

- `app.py` 仅保留路由 + 编排 + DI + 错误映射。
- `app.py` 行数 `<= 5000`。
- 无 `* 2.py` 遗留文件。
- 全量测试与 guardrails 通过。
