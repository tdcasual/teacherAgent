# Agent Design P0-P2 Roadmap Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在不把项目演进成开放式多 agent 平台的前提下，继续强化 `teacherAgent` 的受控 workflow / analysis runtime，使其在装配真相、输出治理、版本追溯、运维观测、质量反馈、回放复现和新域接入方面达到可工业化扩展水平。

**Architecture:** 继续坚持“单一前台 coordinator + 内部 specialist handoff + 统一 analysis plane”的架构边界。P0 优先补控制面真相来源与结果可追溯；P1 把已有运行时信号变成运营与质量闭环；P2 再补 replay / onboarding 等平台化加固能力，避免过早引入开放 agent network。

**Tech Stack:** Python 3.13、FastAPI、Pydantic v2、pytest、现有 `services/api` runtime / domain / review queue / metrics 结构、`docs/reference` 契约文档、`docs/operations` 运维文档。

---

## Current State Snapshot

以下基础已经存在，可作为本路线图的起点，而不是重复建设：

- 统一主链路与 workflow 边界：`README.md`、`docs/reference/agent-runtime-contract.md`
- 多域 analysis plane 契约：`docs/reference/analysis-runtime-contract.md`
- manifest-driven runtime builder 基础版：`services/api/domains/runtime_builder.py`
- specialist governor / typed output schema：`services/api/specialist_agents/governor.py`、`services/api/specialist_agents/output_schemas.py`
- report lineage 字段基础版：`services/api/analysis_report_models.py`
- runtime metrics 聚合基础版：`services/api/analysis_metrics_service.py`
- review feedback summary 基础版：`services/api/review_feedback_service.py`
- replay lineage 重建脚本基础版：`scripts/replay_analysis_run.py`
- controlled job graph 原型：`services/api/specialist_agents/job_graph_runtime.py`

本计划重点不是“从零做一遍”，而是把这些基础版能力推进到真正可扩域、可运维、可回放的生产级状态。

---

## Milestone Overview

### P0 — 控制面与审计面补齐（1-2 周）

目标：让新增 domain 不需要复制 wiring，让 runtime 输出 fail-closed，让 report 成为可审计真相面。

交付结果：

- manifest 成为更完整的装配真相源
- specialist 输出校验覆盖 domain contract、降级路径、错误码与 report 行为
- analysis report lineage 从“字段存在”升级为“全链路稳定注入 + rerun 可比较”

### P1 — 运维闭环与质量闭环（1-2 周）

目标：让发布、回滚、review、质量追踪不再依赖人工抽样和经验判断。

交付结果：

- runtime 事件成为可统计、可导出、可报警的指标
- review queue 进入质量学习闭环
- 复杂高风险域支持受控 job graph，而不是演进为自由 agent mesh

### P2 — 平台加固与扩域工业化（1 周+）

目标：降低回归分析成本和新域接入成本。

交付结果：

- 可 replay / compare 的回放框架
- 标准 domain onboarding 模板与验收清单

---

## P0 Detailed Plan

### Task P0-1: Promote manifest into assembly truth source

**Why:** 当前 `runtime_builder` 已经收敛了大部分 runtime glue，但仍依赖 `_DEPS_FACTORY_LOOKUP`、`_RUNNER_LOOKUP`、`analysis_report_service` 中央注册等半手工装配点。新增第 4 个 domain 时仍要改中心文件，不够声明式。

**Files:**
- Modify: `services/api/domains/manifest_models.py`
- Modify: `services/api/domains/manifest_registry.py`
- Modify: `services/api/domains/runtime_builder.py`
- Modify: `services/api/wiring/survey_wiring.py`
- Modify: `services/api/analysis_report_service.py`
- Modify: `services/api/strategies/selector.py`
- Test: `tests/test_domain_runtime_builder.py`
- Test: `tests/test_domain_manifest_registry.py`
- Test: `tests/test_analysis_report_service.py`
- Doc: `docs/reference/analysis-runtime-contract.md`
- Doc: `docs/architecture/module-boundaries.md`

**Deliverables:**
- `DomainManifest` 明确声明 runtime / report / review / strategy 装配所需最小元信息
- 移除或最小化中心型 domain if/else 注册逻辑
- 新增 domain 时，默认流程接近“填 manifest + 实现 runner / adapter”

**Step 1: Write the failing tests**

- 为 `build_domain_specialist_runtime()` 添加测试，要求 manifest 缺少 runner binding、deps factory、payload key 或 report provider binding 时 fail-fast。
- 为 `analysis_report_service` 添加测试，要求 provider 可从 manifest-driven registry 构建，而不是手工硬编码三套 domain provider。
- 为 selector 添加测试，要求 domain metadata 与 strategy metadata 不一致时直接报错，而不是静默 fallback。

**Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest -q \
  tests/test_domain_runtime_builder.py \
  tests/test_domain_manifest_registry.py \
  tests/test_analysis_report_service.py
```

Expected: FAIL，因为当前 manifest 还不是 report/runtime 装配的唯一真相源。

**Step 3: Write minimal implementation**

- 在 `DomainManifest` 中新增或收敛以下概念：
  - runtime runner binding
  - deps factory binding
  - payload constraint key
  - report provider binding
  - review queue binding
  - default strategy metadata
- 在 `runtime_builder.py` 中抽出通用 binding resolver，避免多处重复 key 查找与错误处理。
- 在 `analysis_report_service.py` 中引入 manifest-driven provider assembly，减少中央硬编码 domain 表。
- 保持 `survey_wiring.py` 作为轻量门面，不再承载重复装配真相。

**Step 4: Run tests to verify they pass**

Run:

```bash
.venv/bin/python -m pytest -q \
  tests/test_domain_runtime_builder.py \
  tests/test_domain_manifest_registry.py \
  tests/test_analysis_report_service.py \
  tests/test_artifact_registry.py
```

Expected: PASS.

**Step 5: Update docs**

- 在 `docs/reference/analysis-runtime-contract.md` 写明 manifest 是哪些平面的 truth source。
- 在 `docs/architecture/module-boundaries.md` 写明 domain 扩展默认只改 manifest + domain-specific implementation，不复制 glue。

**Step 6: Commit**

```bash
git add services/api/domains/manifest_models.py services/api/domains/manifest_registry.py services/api/domains/runtime_builder.py services/api/wiring/survey_wiring.py services/api/analysis_report_service.py services/api/strategies/selector.py tests/test_domain_runtime_builder.py tests/test_domain_manifest_registry.py tests/test_analysis_report_service.py docs/reference/analysis-runtime-contract.md docs/architecture/module-boundaries.md
git commit -m "refactor(agents): make manifest the assembly truth source"
```

**Acceptance Criteria:**
- 新增 domain 不需要新增一组重复的 `build_*_specialist_runtime()` / `list_*_reports()` glue。
- manifest 缺关键 binding 时启动或构建阶段直接失败。
- report / review / runtime 读取面与 manifest 保持一致。

---

### Task P0-2: Harden specialist output validation and downgrade behavior

**Why:** 当前 typed schema 已具备基础能力，但还需要把“invalid_output 后如何处理”做成跨 domain 的统一 fail-closed 路径，避免错误结果进入 final report plane。

**Files:**
- Modify: `services/api/specialist_agents/output_schemas.py`
- Modify: `services/api/specialist_agents/governor.py`
- Modify: `services/api/specialist_agents/contracts.py`
- Modify: `services/api/survey_orchestrator_service.py`
- Modify: `services/api/class_report_orchestrator_service.py`
- Modify: `services/api/multimodal_orchestrator_service.py`
- Modify: `services/api/review_queue_service.py`
- Test: `tests/test_specialist_output_validation.py`
- Test: `tests/test_specialist_agent_governor.py`
- Test: `tests/test_class_report_orchestrator_service.py`
- Test: `tests/test_multimodal_orchestrator_service.py`
- Doc: `docs/reference/analysis-runtime-contract.md`

**Deliverables:**
- 每个 domain 的 output schema 明确必填字段、边界字段和 downgrade 规则
- `invalid_output`、`timeout`、`budget_exceeded` 等错误能稳定进入 review queue / failed 状态
- final report plane 不暴露不合格 artifact

**Step 1: Write the failing tests**

- 新增测试：specialist 输出缺 `confidence_and_gaps`、关键 recommendation 字段为空、结构错误时，governor 返回 `invalid_output`。
- 新增测试：orchestrator 在 `invalid_output` 时，不直接写 final report，而是写 review queue item / failed job metadata。
- 新增测试：review queue 记录 `reason_code=invalid_output` 并能进入汇总统计。

**Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest -q \
  tests/test_specialist_output_validation.py \
  tests/test_specialist_agent_governor.py \
  tests/test_class_report_orchestrator_service.py \
  tests/test_multimodal_orchestrator_service.py
```

Expected: FAIL，因为当前 schema 校验通过后到 orchestrator / report plane 的 downgrade 行为还不够统一。

**Step 3: Write minimal implementation**

- 扩展 `output_schemas.py` 的 domain-specific validator，明确必填字段和允许为空字段。
- 在 `governor.py` 统一产出可消费错误码，不只抛异常文本。
- 在各 orchestrator 中抽出统一的 `handle_specialist_failure()` 或等效 helper，集中决定：
  - 写 job failed 还是 review queued
  - 是否允许 rerun
  - 是否写 report stub
- 在 `review_queue_service.py` 保证 `invalid_output`、`low_confidence`、`timeout` 等 reason_code 规范化。

**Step 4: Run tests to verify they pass**

Run:

```bash
.venv/bin/python -m pytest -q \
  tests/test_specialist_output_validation.py \
  tests/test_specialist_agent_governor.py \
  tests/test_class_report_orchestrator_service.py \
  tests/test_multimodal_orchestrator_service.py \
  tests/test_review_queue_operations.py
```

Expected: PASS.

**Step 5: Update docs**

- 在 `docs/reference/analysis-runtime-contract.md` 增加“invalid_output fail-closed”条款。
- 明确 specialist 通过 schema 只是必要条件，低置信度或结构缺失仍可能降级到 review queue。

**Step 6: Commit**

```bash
git add services/api/specialist_agents/output_schemas.py services/api/specialist_agents/governor.py services/api/specialist_agents/contracts.py services/api/survey_orchestrator_service.py services/api/class_report_orchestrator_service.py services/api/multimodal_orchestrator_service.py services/api/review_queue_service.py tests/test_specialist_output_validation.py tests/test_specialist_agent_governor.py tests/test_class_report_orchestrator_service.py tests/test_multimodal_orchestrator_service.py docs/reference/analysis-runtime-contract.md
git commit -m "feat(agents): harden specialist invalid-output downgrade flow"
```

**Acceptance Criteria:**
- 不合格 specialist 输出无法进入老师可读 final report。
- 所有 domain 的 invalid_output 都能被统计、审计和 rerun。

---

### Task P0-3: Make lineage stable across write, read, rerun, and compare

**Why:** 当前 report model 已有 lineage 字段，但更像“字段存在”；还需要确保这些字段在 planner、runtime、adapter、report 持久化、rerun 和 diff 比较中稳定传播。

**Files:**
- Modify: `services/api/analysis_report_models.py`
- Modify: `services/api/analysis_report_service.py`
- Modify: `services/api/strategies/contracts.py`
- Modify: `services/api/strategies/planner.py`
- Modify: `services/api/artifacts/contracts.py`
- Modify: `services/api/specialist_agents/contracts.py`
- Modify: `services/api/survey_report_service.py`
- Modify: `services/api/class_report_service.py`
- Modify: `services/api/multimodal_report_service.py`
- Test: `tests/test_analysis_version_stamps.py`
- Test: `tests/test_analysis_report_service.py`
- Test: `tests/test_replay_analysis_run.py`
- Doc: `docs/reference/analysis-runtime-contract.md`
- Doc: `docs/operations/multi-domain-analysis-rollout-checklist.md`

**Deliverables:**
- lineage 字段来源统一、默认值统一、rerun 行为统一
- report detail / list / rerun payload 均带稳定 lineage
- replay / compare 可直接依赖 lineage 数据

**Step 1: Write the failing tests**

- 测试每个 domain 的 report detail 都携带 `strategy_version`、`prompt_version`、`adapter_version`、`runtime_version`。
- 测试 rerun 后能够拿到 previous lineage 与 current lineage，支持最小差异比较。
- 测试 replay 脚本在 lineage 缺失时 fail-fast，而不是静默填默认值。

**Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest -q \
  tests/test_analysis_version_stamps.py \
  tests/test_analysis_report_service.py \
  tests/test_replay_analysis_run.py
```

Expected: FAIL，因为 lineage 还没完全成为 write/read/rerun/replay 的硬契约。

**Step 3: Write minimal implementation**

- 在 strategy / artifact / specialist contract 中明确版本来源。
- 统一各 domain report writer 的 lineage 注入方式。
- rerun 时保留 previous lineage，输出差异摘要所需的最小字段。
- replay 脚本不再只是“兜底填 v1”，而是区分缺失、兼容默认和真实 lineage。

**Step 4: Run tests to verify they pass**

Run:

```bash
.venv/bin/python -m pytest -q \
  tests/test_analysis_version_stamps.py \
  tests/test_analysis_report_service.py \
  tests/test_analysis_report_routes.py \
  tests/test_replay_analysis_run.py
```

Expected: PASS.

**Step 5: Update docs**

- 在 contract 中写明 lineage 是 report plane 的强约束字段。
- 在 rollout checklist 中加入“比较前后版本 lineage”检查项。

**Step 6: Commit**

```bash
git add services/api/analysis_report_models.py services/api/analysis_report_service.py services/api/strategies/contracts.py services/api/strategies/planner.py services/api/artifacts/contracts.py services/api/specialist_agents/contracts.py services/api/survey_report_service.py services/api/class_report_service.py services/api/multimodal_report_service.py tests/test_analysis_version_stamps.py tests/test_analysis_report_service.py tests/test_replay_analysis_run.py docs/reference/analysis-runtime-contract.md docs/operations/multi-domain-analysis-rollout-checklist.md
git commit -m "feat(reports): stabilize lineage across report and rerun paths"
```

**Acceptance Criteria:**
- 任一 report 都能回答“用哪个策略版本、prompt 版本、adapter 版本、runtime 版本生成”。
- rerun / replay / compare 使用统一 lineage 输入，不依赖猜测。

---

## P1 Detailed Plan

### Task P1-1: Turn runtime events into exportable operational metrics

**Why:** 当前 `AnalysisMetricsService` 是很好的起点，但仍是内存聚合器，尚未成为发布、回滚、告警的正式运维面。

**Files:**
- Modify: `services/api/analysis_metrics_service.py`
- Modify: `services/api/specialist_agents/events.py`
- Modify: `services/api/specialist_agents/governor.py`
- Modify: `services/api/domains/runtime_builder.py`
- Modify: `services/api/settings.py`
- Modify: `services/api/routes/analysis_report_routes.py`
- Test: `tests/test_analysis_metrics_service.py`
- Test: `tests/test_specialist_agent_governor.py`
- Doc: `docs/operations/slo-and-observability.md`

**Deliverables:**
- 指标不只可 snapshot，还可暴露给运维系统
- 事件按 `domain / strategy_id / agent_id / phase / reason_code` 聚合
- domain rollout checklist 可引用这些指标

**Step 1: Write the failing tests**

- 增加 `run_count`、`fail_count`、`timeout_count`、`invalid_output_count`、`review_downgrade_count`、`rerun_count` 测试。
- 增加事件维度完整性测试：domain 或 strategy 缺失时拒绝计入关键指标，或单独计入 `unknown` bucket。
- 如果准备暴露 HTTP 指标接口，则增加最小 route contract 测试。

**Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest -q \
  tests/test_analysis_metrics_service.py \
  tests/test_specialist_agent_governor.py \
  tests/test_analysis_report_routes.py
```

Expected: FAIL，因为当前 metrics 还不是完整 operations surface。

**Step 3: Write minimal implementation**

- 扩展 `AnalysisMetricsService`，增加稳定指标名和可导出 snapshot schema。
- 在 governor / runtime builder / rerun path 中补齐事件 reason_code。
- 若仓库已有 observability 出口，接入该出口；否则先提供内部只读 metrics route 或管理接口。

**Step 4: Run tests to verify they pass**

Run:

```bash
.venv/bin/python -m pytest -q \
  tests/test_analysis_metrics_service.py \
  tests/test_specialist_agent_governor.py \
  tests/test_analysis_report_routes.py
```

Expected: PASS.

**Step 5: Update docs**

- 在 `docs/operations/slo-and-observability.md` 增加指标定义、采样维度、告警建议。

**Step 6: Commit**

```bash
git add services/api/analysis_metrics_service.py services/api/specialist_agents/events.py services/api/specialist_agents/governor.py services/api/domains/runtime_builder.py services/api/settings.py services/api/routes/analysis_report_routes.py tests/test_analysis_metrics_service.py tests/test_specialist_agent_governor.py docs/operations/slo-and-observability.md
git commit -m "feat(ops): promote specialist runtime events into metrics"
```

**Acceptance Criteria:**
- rollout / rollback 决策能直接看指标，不依赖人工抽样。
- invalid_output / timeout / rerun / review downgrade 都有稳定统计口径。

---

### Task P1-2: Make review queue a real quality feedback loop

**Why:** 当前 review queue 和 feedback summary 已经有了基础模型，但 reviewer 的结论还没有系统性回灌到离线评测、reason drift 分析和质量改进流程。

**Files:**
- Modify: `services/api/review_queue_service.py`
- Modify: `services/api/review_feedback_service.py`
- Modify: `services/api/analysis_report_service.py`
- Modify: `scripts/analysis_strategy_eval.py`
- Create: `scripts/export_review_feedback_dataset.py`
- Test: `tests/test_review_feedback_service.py`
- Test: `tests/test_review_queue_operations.py`
- Doc: `docs/operations/change-management-and-governance.md`
- Doc: `docs/operations/multi-domain-analysis-rollout-checklist.md`

**Deliverables:**
- review 操作日志具备结构化导出能力
- reviewer 修正可以进入离线评测集 / 训练数据候选集
- 可按 domain / strategy / reason_code 分析 drift

**Step 1: Write the failing tests**

- 测试 review queue 的 claim / resolve / reject / dismiss / retry 结果能导出成统一 feedback dataset。
- 测试 reason_code / disposition / operator_note 可被聚合到 drift summary。
- 测试 analysis eval 脚本可消费 feedback dataset 并输出按 domain / reason_code 的统计。

**Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest -q \
  tests/test_review_feedback_service.py \
  tests/test_review_queue_operations.py \
  tests/test_analysis_strategy_eval.py
```

Expected: FAIL，因为目前 feedback 还停留在 summary 层。

**Step 3: Write minimal implementation**

- 在 `review_feedback_service.py` 中增加 export payload builder。
- 在 `review_queue_service.py` 中保证关键信息写全：domain、strategy、reason_code、reviewer action、resolution note。
- 新增 `scripts/export_review_feedback_dataset.py`，把 review 结果转成 eval 可用数据。
- 在 `analysis_strategy_eval.py` 中增加 feedback dataset 输入能力。

**Step 4: Run tests to verify they pass**

Run:

```bash
.venv/bin/python -m pytest -q \
  tests/test_review_feedback_service.py \
  tests/test_review_queue_operations.py \
  tests/test_analysis_strategy_eval.py
```

Expected: PASS.

**Step 5: Update docs**

- 在 change management 文档中写明 review feedback 是上线后的质量输入源。
- 在 rollout checklist 中加入 review drift 与 recurring reason_code 监控项。

**Step 6: Commit**

```bash
git add services/api/review_queue_service.py services/api/review_feedback_service.py services/api/analysis_report_service.py scripts/analysis_strategy_eval.py scripts/export_review_feedback_dataset.py tests/test_review_feedback_service.py tests/test_review_queue_operations.py tests/test_analysis_strategy_eval.py docs/operations/change-management-and-governance.md docs/operations/multi-domain-analysis-rollout-checklist.md
git commit -m "feat(review): turn review queue into a quality feedback loop"
```

**Acceptance Criteria:**
- reviewer 结论不再只留在工单层，而能进入离线质量改进流程。
- 可解释哪些 domain / strategy / reason_code 正在漂移。

---

### Task P1-3: Pilot controlled job graph for high-risk domains

**Why:** 当前 `SpecialistJobGraphRuntime` 是原型级顺序执行器。下一步应在 `video_homework` 这类高风险域试点固定图，而不是引入自由多 agent 对话网。

**Files:**
- Modify: `services/api/specialist_agents/job_graph_models.py`
- Modify: `services/api/specialist_agents/job_graph_runtime.py`
- Modify: `services/api/multimodal_orchestrator_service.py`
- Modify: `services/api/domains/manifest_registry.py`
- Modify: `services/api/domains/runtime_builder.py`
- Test: `tests/test_specialist_job_graph_runtime.py`
- Test: `tests/test_multimodal_orchestrator_service.py`
- Doc: `docs/reference/analysis-runtime-contract.md`

**Deliverables:**
- 固定 job graph 支持 `extract -> analyze -> verify -> merge` 之类的有限步骤
- 每个节点仍受 budget / timeout / schema / event 约束
- graph 失败后能稳定降级到 review / failed，而不是半成品输出

**Step 1: Write the failing tests**

- 增加 job graph 节点 budget 超限测试。
- 增加 verify 节点 invalid_output 时整图失败并进入降级路径的测试。
- 增加 `video_homework` orchestrator 使用固定图时仍能输出统一 report / review contract 的测试。

**Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest -q \
  tests/test_specialist_job_graph_runtime.py \
  tests/test_multimodal_orchestrator_service.py
```

Expected: FAIL，因为当前 graph 还只是轻量顺序执行，没有完整治理和 domain 接入。

**Step 3: Write minimal implementation**

- 在 `job_graph_models.py` 中增加节点类型、最大边界、可选 fallback 元信息。
- 在 `job_graph_runtime.py` 中引入节点级事件、失败中止、budget 校验。
- 在 `multimodal_orchestrator_service.py` 中仅为 `video_homework` 接入固定 graph，避免扩散到所有 domain。

**Step 4: Run tests to verify they pass**

Run:

```bash
.venv/bin/python -m pytest -q \
  tests/test_specialist_job_graph_runtime.py \
  tests/test_multimodal_orchestrator_service.py \
  tests/test_specialist_agent_governor.py
```

Expected: PASS.

**Step 5: Update docs**

- 在 contract 中明确：这是 controlled orchestration，不是开放 agent network。

**Step 6: Commit**

```bash
git add services/api/specialist_agents/job_graph_models.py services/api/specialist_agents/job_graph_runtime.py services/api/multimodal_orchestrator_service.py services/api/domains/manifest_registry.py services/api/domains/runtime_builder.py tests/test_specialist_job_graph_runtime.py tests/test_multimodal_orchestrator_service.py docs/reference/analysis-runtime-contract.md
git commit -m "feat(video-homework): add controlled specialist job graph"
```

**Acceptance Criteria:**
- 高风险域可拆步骤提质，但不会引入自由 agent mesh。
- job graph 与单 specialist runtime 共用同一治理规则。

---

## P2 Detailed Plan

### Task P2-1: Upgrade replay into a real compareable replay harness

**Why:** 当前 `replay_analysis_run.py` 主要重建 lineage 上下文，还不支持真实重跑、版本比较和差异摘要输出。

**Files:**
- Modify: `scripts/replay_analysis_run.py`
- Modify: `services/api/analysis_report_service.py`
- Modify: `services/api/strategies/planner.py`
- Create: `scripts/compare_analysis_runs.py`
- Test: `tests/test_replay_analysis_run.py`
- Test: `tests/test_analysis_report_service.py`
- Doc: `docs/reference/analysis-runtime-contract.md`
- Doc: `docs/operations/multi-domain-analysis-rollout-checklist.md`

**Deliverables:**
- 给定 report + artifact + lineage，可在不同策略版本下重跑
- 自动输出最小 diff summary
- 为回归分析、灰度比较、事故排查提供统一脚本

**Step 1: Write the failing tests**

- 测试 replay 能读取 stored report payload、artifact meta、lineage 并构建完整 replay request。
- 测试 compare 脚本能输出 summary diff，而不是原始大 JSON diff。
- 测试缺 artifact / lineage 时 fail-fast。

**Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest -q \
  tests/test_replay_analysis_run.py \
  tests/test_analysis_report_service.py
```

Expected: FAIL，因为当前 replay 还不支持完整 replay / compare。

**Step 3: Write minimal implementation**

- 扩展 replay request model，包含 artifact payload、strategy target、lineage。
- 增加 `compare_analysis_runs.py` 输出固定结构 diff：summary、confidence、recommendations、reason_code 变化。
- 在 report writer 中保证 replay 必需字段可取回。

**Step 4: Run tests to verify they pass**

Run:

```bash
.venv/bin/python -m pytest -q \
  tests/test_replay_analysis_run.py \
  tests/test_analysis_report_service.py
```

Expected: PASS.

**Step 5: Update docs**

- 写明 replay 适用场景：回归比较、灰度评估、事故分析。

**Step 6: Commit**

```bash
git add scripts/replay_analysis_run.py scripts/compare_analysis_runs.py services/api/analysis_report_service.py services/api/strategies/planner.py tests/test_replay_analysis_run.py tests/test_analysis_report_service.py docs/reference/analysis-runtime-contract.md docs/operations/multi-domain-analysis-rollout-checklist.md
git commit -m "feat(replay): add comparable analysis replay harness"
```

**Acceptance Criteria:**
- 任一 report 都可被 replay 或 compare，而不是只能人工阅读 JSON。
- 质量退化定位从“线上猜”变成“离线可复现”。

---

### Task P2-2: Build a standard domain onboarding template

**Why:** 当前 domain 扩展规则已经写进 contract，但还缺一个真正面向工程落地的模板和验收清单，新人扩域仍需要读很多隐性约定。

**Files:**
- Create: `docs/reference/analysis-domain-onboarding-template.md`
- Create: `docs/reference/analysis-domain-checklist.md`
- Modify: `docs/reference/analysis-runtime-contract.md`
- Modify: `docs/INDEX.md`
- Modify: `docs/architecture/module-boundaries.md`
- Test: `tests/test_architecture_doc_paths.py`

**Deliverables:**
- 新 domain onboarding 模板
- 新 domain checklist
- 文档导航和架构文档中能直接找到扩域路径

**Step 1: Write the failing tests**

- 增加文档路径测试，确保新模板文档被纳入 `docs/INDEX.md`。
- 如已有文档契约测试，补充约束：新模板必须列出 manifest、artifact、strategy、specialist、report plane、review queue、fixtures、flags、docs。

**Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest -q tests/test_architecture_doc_paths.py
```

Expected: FAIL，因为文档模板和导航尚未齐备。

**Step 3: Write minimal implementation**

- 新增 onboarding template，覆盖：
  - manifest
  - artifact adapter
  - strategy selector
  - specialist runner
  - report provider
  - review queue
  - fixtures / eval
  - rollout flags
  - observability
- 新增 checklist，用于 PR 和上线前核对。

**Step 4: Run tests to verify they pass**

Run:

```bash
.venv/bin/python -m pytest -q tests/test_architecture_doc_paths.py
```

Expected: PASS.

**Step 5: Update docs index**

- 把新模板加入 `docs/INDEX.md` 和 `analysis-runtime-contract` 交叉引用。

**Step 6: Commit**

```bash
git add docs/reference/analysis-domain-onboarding-template.md docs/reference/analysis-domain-checklist.md docs/reference/analysis-runtime-contract.md docs/INDEX.md docs/architecture/module-boundaries.md tests/test_architecture_doc_paths.py
git commit -m "docs(analysis): add domain onboarding template and checklist"
```

**Acceptance Criteria:**
- 新域接入从“读隐性经验”变成“按模板完成”。
- PR reviewer 能直接按 checklist 验收 domain 完整性。

---

## Recommended Execution Order

按以下顺序执行，收益最高：

1. `P0-1` manifest 装配真相源
2. `P0-2` output validation + downgrade 一致化
3. `P0-3` lineage 稳定传播
4. `P1-1` operational metrics
5. `P1-2` review feedback loop
6. `P1-3` controlled job graph pilot
7. `P2-1` replay + compare harness
8. `P2-2` onboarding template

排序理由：

- 先补控制面和审计面，避免后续所有运维能力建立在不稳定契约上。
- 再补 metrics / review / graph，形成可观测与质量闭环。
- 最后做 replay 与 onboarding，把经验固化成平台资产。

---

## Verification Strategy

每个 task 都遵循同一验证方式：

- 先写失败测试，再写最小实现
- 先跑最小测试集，再跑相邻回归测试
- 需要文档变更时，同时更新 contract / operations / index
- 每个 task 完成后单独 commit，避免一次性大改难回滚

建议最终回归命令集合：

```bash
.venv/bin/python -m pytest -q \
  tests/test_domain_runtime_builder.py \
  tests/test_domain_manifest_registry.py \
  tests/test_specialist_output_validation.py \
  tests/test_specialist_agent_governor.py \
  tests/test_analysis_version_stamps.py \
  tests/test_analysis_metrics_service.py \
  tests/test_review_feedback_service.py \
  tests/test_specialist_job_graph_runtime.py \
  tests/test_replay_analysis_run.py \
  tests/test_analysis_report_service.py
```

---

## Success Definition

当以下条件全部满足时，本路线图视为完成：

- 新增 analysis domain 时，装配接近声明式接入
- specialist 输出不再以“非空 dict”作为通过标准
- report plane 成为可靠 audit surface
- rollout / rollback 有指标支撑
- review queue 成为质量学习闭环，而不是只做收容
- 高风险域可用 controlled graph 提质，而不引入 agent mesh
- 历史 report 可以 replay / compare
- 新域接入有清晰模板和 checklist

Plan complete and saved to `docs/plans/2026-03-08-agent-design-p0-p2-roadmap.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

Which approach?
