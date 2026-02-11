# 2026-02-11 激进技术栈升级设计（Support-first）

## 背景与目标

当前项目可用，但存在两类支持性风险：

1. 运行时生命周期风险：Node 20 临近 EOL（2026-04-30）。
2. 工具链维护风险：Vite 5 / 旧 esbuild 路径已出现中危告警，且升级窗口正在收窄。

本设计采用“激进策略”，目标是在一次窗口内把维护基线抬升到未来 18~24 个月：

- 前端：React 18 → 19，Vite 5 → 7，插件与类型定义同步跨代。
- 后端：Python 3.11 → 3.13（直接升级，不走 3.12 过渡），FastAPI/Uvicorn/Pydantic 等主干依赖同步升级。
- 基础设施：Docker/CI 统一运行时版本，避免开发、CI、生产三套不一致。

## 范围定义

### In Scope

- 运行时升级
  - Dockerfile：`python:3.11-slim` → `python:3.13-slim`
  - Dockerfile/CI：Node 20 → Node 24
- 前端依赖升级
  - `react` / `react-dom` / `@types/react` / `@types/react-dom` 到 19 主线
  - `vite` 到 7 主线，`@vitejs/plugin-react` 到 5 主线
  - `vite-plugin-pwa` 到 1 主线
- 后端依赖升级
  - FastAPI、Uvicorn、Pydantic、Requests、Redis client、RQ、PyYAML、ReportLab 等
- 验证与发布
  - 完整构建、smoke、E2E、异步链路回归、回滚预案

### Out of Scope

- 新功能开发
- 接口协议变更（字段增删、路由重命名）
- 数据存储架构变更（Redis/Qdrant 逻辑改造）

## 架构策略

核心原则：**先运行时，后依赖，最后代码适配**。

1. **运行时层（Runtime Layer）**
   - 只改 Python/Node 版本，不改业务依赖。
   - 目标是确认镜像可构建、服务可启动、健康检查可通过。

2. **依赖层（Dependency Layer）**
   - 前后端依赖一次跨代升级，保持对外 API 协议不变。
   - 目标是把问题集中在“库兼容性”，而不是“运行时 + 库”混杂。

3. **适配层（Adaptation Layer）**
   - 修复 React 19、Vite 7、RQ 2.x、Python 3.13 触发的行为差异。
   - 目标是达到既有功能等价，不引入新行为。

## 组件与数据流影响

### 前端链路

- Teacher/Student 双端继续通过 HTTP 与 API 通信。
- 保持 `vite.student.config.ts` 与 `vite.teacher.config.ts` 双入口，不在本次合并构建策略。
- React 19 适配重点：渲染入口、严格模式副作用、第三方组件兼容。

### 后端链路

- API 同步路径：查询、页面初始数据、轻量处理。
- API 异步路径：OCR、报告生成、批处理任务。
- 异步执行继续使用 Redis + RQ worker，任务结果落地 `data/uploads/output`。

### 关键不变约束

- HTTP 路由与请求/响应契约不改。
- 异步任务 payload 结构不改。
- 业务级开关（环境变量语义）不改。

## 错误处理与回滚策略

发布采用“短冻结 + 一次切换 + 48 小时回滚窗”。

### 阻断条件（Fail Fast）

任一条件命中即阻断上线：

- 镜像构建失败。
- 关键服务无法通过健康检查。
- 后端 smoke 或前端 E2E 任一失败。
- OCR/导出/队列任务关键路径失败。

### 运行期回滚阈值（保持当前）

- 10 分钟窗口内 5xx 超过 1%。
- 关键异步任务失败率超过 2%。
- 队列持续积压且无法在观察窗口回落。

命中阈值直接回滚到上一版镜像与 lockfile，不做在线拼补。

## 测试闸门（四层）

1. **静态层**
   - 前端 `typecheck`
   - 后端 import/启动健康检查

2. **后端 Smoke 层**
   - 复用现有 pytest smoke 组合

3. **前端 E2E 层**
   - teacher E2E
   - student E2E
   - mobile menu 相关专项

4. **升级专项回归层**
   - 上传文档（含失败兜底）
   - OCR 任务
   - 报告导出
   - 异步任务状态轮询

通过标准：四层全部绿灯才允许发布。

## 实施顺序（建议）

### Stage 0：基线冻结

- 记录当前 lockfile、镜像 tag、CI 通过状态。
- 产出回滚清单（明确回滚命令和版本号）。

### Stage 1：运行时升级

- Python 直接升 3.13（Docker + CI）。
- Node 统一升 24（Docker + CI）。
- 仅验证启动、构建、健康检查。

### Stage 2：依赖升级

- 前端升级到 React 19 + Vite 7 主线。
- 后端升级 FastAPI/Uvicorn/Pydantic/RQ 等核心依赖。
- 跑完整四层测试闸门。

### Stage 3：兼容性清理

- 处理警告、弃用 API、运行时行为差异。
- 对回归失败点做最小修复。

### Stage 4：发布与观察

- 切生产。
- 48 小时观察关键指标，按阈值触发自动回滚决策。

## 已确认决策

- 升级策略：激进策略。
- Python 目标版本：直接 3.13。
- 回滚阈值：保持当前阈值（不加严）。

## 风险清单与缓释

1. **React 19 生态兼容风险**
   - 缓释：优先检查核心 UI 库与 Markdown 渲染相关依赖；不可兼容则锁版本并提交后续替换计划。

2. **RQ 2.x 行为变更风险**
   - 缓释：专项覆盖任务重试、超时、失败入库、worker 启停场景。

3. **Python 3.13 三方包轮子（wheel）可用性风险**
   - 缓释：提前在 CI 和本地容器构建验证，必要时临时 pin 到兼容子版本。

4. **一次跨代导致问题定位困难**
   - 缓释：坚持分层推进（运行时→依赖→适配），每层独立可验证与可回退。

