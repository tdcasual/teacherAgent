# Agent System 6-Week Ordered Execution Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 把 `docs/plans/2026-03-09-agent-system-6week-roadmap-design.md` 中确认的 6 周治理优先路线图，拆成严格可执行的任务顺序、依赖关系、验证命令与提交节奏，便于在独立 worktree 中按顺序落地。

**Architecture:** 保持 `Coordinator` 为唯一默认前台 agent，沿用统一 analysis plane：`target resolver -> artifact adapter -> strategy selector -> specialist runtime -> analysis report / review queue`。执行顺序按“先控制面与审计面，再质量闭环，最后运营化与扩域工业化”的原则推进，严禁跳过前置治理直接扩域。

**Tech Stack:** Python 3.13、FastAPI、Pydantic v2、pytest、现有 `services/api` runtime / review queue / metrics 架构、`docs/reference` 契约文档、`docs/operations` 运维文档、teacher workbench。

---

## Source Documents

本执行计划基于以下已确认文档：

- `docs/plans/2026-03-09-agent-system-6week-roadmap-design.md`
- `docs/plans/2026-03-08-agent-design-p0-p2-roadmap.md`
- `docs/plans/2026-03-07-agent-system-priority-optimization-plan.md`
- `docs/plans/2026-03-08-agent-design-review-and-optimization-design.md`

如执行过程中出现冲突，以本文件的**执行顺序与依赖关系**为准，以 `2026-03-08-agent-design-p0-p2-roadmap.md` 的**文件范围与测试命令**为准。

---

## Execution Rules

1. 所有开发在独立 worktree 中进行。
2. 严格按顺序执行，未完成前置 gate 不进入下一任务。
3. 每个任务遵循：`先写失败测试 -> 跑红 -> 最小实现 -> 跑绿 -> 补文档 -> 跑相邻回归 -> 单独 commit`。
4. 每个任务只解决该任务范围内的问题，不顺手重构无关模块。
5. 若某任务验证失败，先修复该任务，再继续，不允许带红进入下一阶段。

---

## Phase 0: Preparation

### Task 0: Create isolated workspace and capture baseline

**Depends on:** None

**Files:**
- Reference: `docs/plans/2026-03-09-agent-system-6week-roadmap-design.md`
- Reference: `docs/plans/2026-03-08-agent-design-p0-p2-roadmap.md`

**Step 1: Create worktree**

Run:

```bash
git worktree add .worktrees/agent-6week-plan -b codex/agent-6week-plan
```

Expected: 新 worktree 创建成功。

**Step 2: Enter worktree and inspect status**

Run:

```bash
cd .worktrees/agent-6week-plan
git status --short
```

Expected: 工作区干净。

**Step 3: Run baseline targeted suite**

Run:

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

Expected: 记录当前基线，通过或失败都要保存输出结论。

**Step 4: Record baseline note**

在本地执行笔记或任务跟踪中记录：当前通过数、失败数、已知 flaky 测试。

**Step 5: No commit**

本任务不提交代码，完成后进入 `P0-1`。

---

## Phase 1: P0 Stabilization and Control-Plane Closure

### Task 1: P0-1 manifest assembly truth source

**Depends on:** Task 0

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

**Step 1: Write failing tests**

补测试覆盖以下行为：

- manifest 缺少 runner binding、deps factory、payload key 或 report provider binding 时 fail-fast；
- report provider 可从 manifest-driven registry 构建，而不是手工硬编码三套 domain provider；
- domain metadata 与 strategy metadata 不一致时 selector 报错，而不是静默 fallback。

**Step 2: Run red tests**

Run:

```bash
.venv/bin/python -m pytest -q \
  tests/test_domain_runtime_builder.py \
  tests/test_domain_manifest_registry.py \
  tests/test_analysis_report_service.py
```

Expected: FAIL。

**Step 3: Implement minimal code**

- 收敛 `DomainManifest` 的 runtime / report / review / strategy 装配元信息；
- 在 `runtime_builder.py` 提取通用 binding resolver；
- 在 `analysis_report_service.py` 改成 manifest-driven provider assembly；
- 保持 `survey_wiring.py` 为轻量门面。

**Step 4: Run green tests**

Run:

```bash
.venv/bin/python -m pytest -q \
  tests/test_domain_runtime_builder.py \
  tests/test_domain_manifest_registry.py \
  tests/test_analysis_report_service.py \
  tests/test_strategy_selector.py
```

Expected: PASS。

**Step 5: Update docs**

更新运行时契约和模块边界文档，明确 manifest 是装配真相源。

**Step 6: Run neighboring regression**

Run:

```bash
.venv/bin/python -m pytest -q \
  tests/test_domain_runtime_builder.py \
  tests/test_domain_manifest_registry.py \
  tests/test_analysis_report_service.py \
  tests/test_strategy_selector.py \
  tests/test_docs_architecture_presence.py
```

Expected: PASS。

**Step 7: Commit**

```bash
git add services/api/domains/manifest_models.py services/api/domains/manifest_registry.py services/api/domains/runtime_builder.py services/api/wiring/survey_wiring.py services/api/analysis_report_service.py services/api/strategies/selector.py tests/test_domain_runtime_builder.py tests/test_domain_manifest_registry.py tests/test_analysis_report_service.py docs/reference/analysis-runtime-contract.md docs/architecture/module-boundaries.md
git commit -m "feat(domains): promote manifest into assembly truth source"
```

**Gate:** 不满足“新增 domain 不再改多处中心 lookup”前，不进入 Task 2。

---

### Task 2: P0-2 specialist output validation and downgrade consistency

**Depends on:** Task 1

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

**Step 1: Write failing tests**

覆盖以下路径：

- 缺关键字段、结构错误或 recommendation 空壳时返回 `invalid_output`；
- orchestrator 在 `invalid_output` 时不写 final report，而是写 review / failed；
- review queue 记录规范 reason code 并可统计。

**Step 2: Run red tests**

Run:

```bash
.venv/bin/python -m pytest -q \
  tests/test_specialist_output_validation.py \
  tests/test_specialist_agent_governor.py \
  tests/test_class_report_orchestrator_service.py \
  tests/test_multimodal_orchestrator_service.py
```

Expected: FAIL。

**Step 3: Implement minimal code**

- 明确各 domain 的 typed output schema；
- 统一 governor 错误码输出；
- 在 orchestrator 中统一 specialist failure 处理；
- 规范 review queue 的 `invalid_output`、`timeout`、`low_confidence` 等 code。

**Step 4: Run green tests**

Run:

```bash
.venv/bin/python -m pytest -q \
  tests/test_specialist_output_validation.py \
  tests/test_specialist_agent_governor.py \
  tests/test_class_report_orchestrator_service.py \
  tests/test_multimodal_orchestrator_service.py \
  tests/test_review_queue_operations.py
```

Expected: PASS。

**Step 5: Update docs**

在运行时契约中写清 `invalid_output fail-closed` 与 downgrade 规则。

**Step 6: Run neighboring regression**

Run:

```bash
.venv/bin/python -m pytest -q \
  tests/test_specialist_output_validation.py \
  tests/test_specialist_agent_governor.py \
  tests/test_class_report_orchestrator_service.py \
  tests/test_multimodal_orchestrator_service.py \
  tests/test_analysis_report_service.py
```

Expected: PASS。

**Step 7: Commit**

```bash
git add services/api/specialist_agents/output_schemas.py services/api/specialist_agents/governor.py services/api/specialist_agents/contracts.py services/api/survey_orchestrator_service.py services/api/class_report_orchestrator_service.py services/api/multimodal_orchestrator_service.py services/api/review_queue_service.py tests/test_specialist_output_validation.py tests/test_specialist_agent_governor.py tests/test_class_report_orchestrator_service.py tests/test_multimodal_orchestrator_service.py docs/reference/analysis-runtime-contract.md
git commit -m "feat(agents): harden specialist invalid-output downgrade flow"
```

**Gate:** 所有 domain 的不合格 specialist 输出都必须无法进入老师可读 final report。

---

### Task 3: P0-3 stable lineage across write/read/rerun/replay

**Depends on:** Task 2

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

**Step 1: Write failing tests**

新增测试要求：

- 每个 domain 的 report detail 带齐 `strategy_version`、`prompt_version`、`adapter_version`、`runtime_version`；
- rerun 能看到 `previous lineage` 与 `current lineage`；
- replay 在 lineage 缺失时 fail-fast。

**Step 2: Run red tests**

Run:

```bash
.venv/bin/python -m pytest -q \
  tests/test_analysis_version_stamps.py \
  tests/test_analysis_report_service.py \
  tests/test_replay_analysis_run.py
```

Expected: FAIL。

**Step 3: Implement minimal code**

- 明确 strategy / artifact / specialist contract 的版本来源；
- 统一各 domain report writer 的 lineage 注入；
- rerun 保留 previous lineage；
- replay 区分缺失、兼容默认和真实 lineage。

**Step 4: Run green tests**

Run:

```bash
.venv/bin/python -m pytest -q \
  tests/test_analysis_version_stamps.py \
  tests/test_analysis_report_service.py \
  tests/test_analysis_report_routes.py \
  tests/test_replay_analysis_run.py
```

Expected: PASS。

**Step 5: Update docs**

在契约与 rollout checklist 中把 lineage 定义成强约束字段。

**Step 6: Run P0 regression checkpoint**

Run:

```bash
.venv/bin/python -m pytest -q \
  tests/test_domain_runtime_builder.py \
  tests/test_domain_manifest_registry.py \
  tests/test_specialist_output_validation.py \
  tests/test_specialist_agent_governor.py \
  tests/test_analysis_version_stamps.py \
  tests/test_analysis_report_service.py \
  tests/test_replay_analysis_run.py
```

Expected: PASS。

**Step 7: Commit**

```bash
git add services/api/analysis_report_models.py services/api/analysis_report_service.py services/api/strategies/contracts.py services/api/strategies/planner.py services/api/artifacts/contracts.py services/api/specialist_agents/contracts.py services/api/survey_report_service.py services/api/class_report_service.py services/api/multimodal_report_service.py tests/test_analysis_version_stamps.py tests/test_analysis_report_service.py tests/test_replay_analysis_run.py docs/reference/analysis-runtime-contract.md docs/operations/multi-domain-analysis-rollout-checklist.md
git commit -m "feat(reports): stabilize lineage across report and rerun paths"
```

**Gate:** 任何 report 都必须能回答“由哪个策略 / prompt / adapter / runtime 版本生成”。

---

### Task 4: P0 integration checkpoint

**Depends on:** Task 3

**Files:**
- Reference: `services/api/domains/runtime_builder.py`
- Reference: `services/api/specialist_agents/governor.py`
- Reference: `services/api/analysis_report_service.py`
- Reference: `docs/reference/analysis-runtime-contract.md`

**Step 1: Run P0 full verification**

Run:

```bash
.venv/bin/python -m pytest -q \
  tests/test_domain_runtime_builder.py \
  tests/test_domain_manifest_registry.py \
  tests/test_specialist_output_validation.py \
  tests/test_specialist_agent_governor.py \
  tests/test_analysis_version_stamps.py \
  tests/test_analysis_report_service.py \
  tests/test_replay_analysis_run.py \
  tests/test_review_queue_operations.py
```

Expected: PASS。

**Step 2: Review changed docs and routes**

人工检查以下事实是否成立：

- manifest 已成为装配真相源；
- invalid_output fail-closed 已进入契约；
- lineage 已进入 report plane 强约束；
- review queue reason code 可审计。

**Step 3: No code change unless bug found**

若无问题，不额外提交；若发现集成 bug，单开修复 commit，不夹带新功能。

**Gate:** P0 红线未清零前，不进入 P1。

---

## Phase 2: P1 Quality Loop and Controlled Operability

### Task 5: P1-1 runtime events into operational metrics

**Depends on:** Task 4

**Files:**
- Modify: `services/api/analysis_metrics_service.py`
- Modify: `services/api/specialist_agents/events.py`
- Modify: `services/api/specialist_agents/governor.py`
- Modify: `services/api/domains/runtime_builder.py`
- Modify: `services/api/settings.py`
- Modify: `services/api/routes/analysis_report_routes.py`
- Test: `tests/test_analysis_metrics_service.py`
- Test: `tests/test_specialist_agent_governor.py`
- Test: `tests/test_analysis_report_routes.py`
- Doc: `docs/operations/slo-and-observability.md`

**Step 1: Write failing tests**

覆盖：`run_count`、`fail_count`、`timeout_count`、`invalid_output_count`、`review_downgrade_count`、`rerun_count`，以及关键维度缺失的处理逻辑。

**Step 2: Run red tests**

Run:

```bash
.venv/bin/python -m pytest -q \
  tests/test_analysis_metrics_service.py \
  tests/test_specialist_agent_governor.py \
  tests/test_analysis_report_routes.py
```

Expected: FAIL。

**Step 3: Implement minimal code**

- 扩展 metrics snapshot schema；
- 在 governor / runtime builder / rerun path 中补事件 reason code；
- 暴露只读 metrics route 或管理接口。

**Step 4: Run green tests**

Run:

```bash
.venv/bin/python -m pytest -q \
  tests/test_analysis_metrics_service.py \
  tests/test_specialist_agent_governor.py \
  tests/test_analysis_report_routes.py
```

Expected: PASS。

**Step 5: Update docs**

在 `docs/operations/slo-and-observability.md` 增加指标定义、维度与告警建议。

**Step 6: Commit**

```bash
git add services/api/analysis_metrics_service.py services/api/specialist_agents/events.py services/api/specialist_agents/governor.py services/api/domains/runtime_builder.py services/api/settings.py services/api/routes/analysis_report_routes.py tests/test_analysis_metrics_service.py tests/test_specialist_agent_governor.py tests/test_analysis_report_routes.py docs/operations/slo-and-observability.md
git commit -m "feat(ops): promote specialist runtime events into metrics"
```

**Gate:** rollout / rollback 必须已有可用指标口径。

---

### Task 6: P1-2 review queue into quality feedback loop

**Depends on:** Task 5

**Files:**
- Modify: `services/api/review_queue_service.py`
- Modify: `services/api/review_feedback_service.py`
- Modify: `services/api/analysis_report_service.py`
- Modify: `scripts/analysis_strategy_eval.py`
- Create: `scripts/export_review_feedback_dataset.py`
- Test: `tests/test_review_feedback_service.py`
- Test: `tests/test_review_queue_operations.py`
- Test: `tests/test_analysis_strategy_eval.py`
- Doc: `docs/operations/change-management-and-governance.md`
- Doc: `docs/operations/multi-domain-analysis-rollout-checklist.md`

**Step 1: Write failing tests**

覆盖：review 操作日志导出 feedback dataset、drift summary 聚合、eval 脚本消费 feedback dataset。

**Step 2: Run red tests**

Run:

```bash
.venv/bin/python -m pytest -q \
  tests/test_review_feedback_service.py \
  tests/test_review_queue_operations.py \
  tests/test_analysis_strategy_eval.py
```

Expected: FAIL。

**Step 3: Implement minimal code**

- 增加 export payload builder；
- 确保 queue log 写全 `domain`、`strategy`、`reason_code`、`reviewer action`、`resolution note`；
- 新增 feedback dataset 导出脚本；
- 让 eval 脚本可消费反馈数据。

**Step 4: Run green tests**

Run:

```bash
.venv/bin/python -m pytest -q \
  tests/test_review_feedback_service.py \
  tests/test_review_queue_operations.py \
  tests/test_analysis_strategy_eval.py
```

Expected: PASS。

**Step 5: Update docs**

补充 change management 与 rollout checklist 中的 feedback loop 说明。

**Step 6: Run neighboring regression**

Run:

```bash
.venv/bin/python -m pytest -q \
  tests/test_review_feedback_service.py \
  tests/test_review_queue_operations.py \
  tests/test_analysis_strategy_eval.py \
  tests/test_analysis_report_service.py
```

Expected: PASS。

**Step 7: Commit**

```bash
git add services/api/review_queue_service.py services/api/review_feedback_service.py services/api/analysis_report_service.py scripts/analysis_strategy_eval.py scripts/export_review_feedback_dataset.py tests/test_review_feedback_service.py tests/test_review_queue_operations.py tests/test_analysis_strategy_eval.py docs/operations/change-management-and-governance.md docs/operations/multi-domain-analysis-rollout-checklist.md
git commit -m "feat(review): turn review queue into a quality feedback loop"
```

**Gate:** reviewer 结论必须能进入离线质量改进流程。

---

### Task 7: P1-3 controlled job graph pilot for high-risk domain

**Depends on:** Task 6

**Files:**
- Modify: `services/api/specialist_agents/job_graph_models.py`
- Modify: `services/api/specialist_agents/job_graph_runtime.py`
- Modify: `services/api/multimodal_orchestrator_service.py`
- Modify: `services/api/domains/manifest_registry.py`
- Modify: `services/api/domains/runtime_builder.py`
- Test: `tests/test_specialist_job_graph_runtime.py`
- Test: `tests/test_multimodal_orchestrator_service.py`
- Doc: `docs/reference/analysis-runtime-contract.md`

**Step 1: Write failing tests**

覆盖：节点 budget 超限、verify 节点 invalid_output 触发整图失败、`video_homework` 仍输出统一 report / review contract。

**Step 2: Run red tests**

Run:

```bash
.venv/bin/python -m pytest -q \
  tests/test_specialist_job_graph_runtime.py \
  tests/test_multimodal_orchestrator_service.py
```

Expected: FAIL。

**Step 3: Implement minimal code**

- 增加固定节点类型与节点级治理；
- 在 job graph runtime 中引入节点事件、失败中止、budget 校验；
- 仅在 `video_homework` 域试点接入固定图。

**Step 4: Run green tests**

Run:

```bash
.venv/bin/python -m pytest -q \
  tests/test_specialist_job_graph_runtime.py \
  tests/test_multimodal_orchestrator_service.py \
  tests/test_specialist_agent_governor.py
```

Expected: PASS。

**Step 5: Update docs**

明确这是 controlled orchestration，不是开放 agent network。

**Step 6: Commit**

```bash
git add services/api/specialist_agents/job_graph_models.py services/api/specialist_agents/job_graph_runtime.py services/api/multimodal_orchestrator_service.py services/api/domains/manifest_registry.py services/api/domains/runtime_builder.py tests/test_specialist_job_graph_runtime.py tests/test_multimodal_orchestrator_service.py docs/reference/analysis-runtime-contract.md
git commit -m "feat(video-homework): add controlled specialist job graph"
```

**Gate:** 高风险域可拆步骤提质，但不得破坏统一 runtime 治理规则。

---

### Task 8: P1 integration checkpoint

**Depends on:** Task 7

**Files:**
- Reference: `services/api/analysis_metrics_service.py`
- Reference: `services/api/review_feedback_service.py`
- Reference: `services/api/specialist_agents/job_graph_runtime.py`
- Reference: `docs/operations/slo-and-observability.md`

**Step 1: Run P1 verification bundle**

Run:

```bash
.venv/bin/python -m pytest -q \
  tests/test_analysis_metrics_service.py \
  tests/test_review_feedback_service.py \
  tests/test_review_queue_operations.py \
  tests/test_analysis_strategy_eval.py \
  tests/test_specialist_job_graph_runtime.py \
  tests/test_multimodal_orchestrator_service.py \
  tests/test_specialist_agent_governor.py
```

Expected: PASS。

**Step 2: Manual checkpoint review**

确认以下事实：

- metrics 已可支撑 rollout / rollback；
- review queue 已形成 feedback dataset；
- controlled job graph 仅服务高风险域，不外溢成开放多 agent 模式。

**Step 3: No commit unless fix required**

如需修集成问题，单独提交 `fix(analysis): resolve P1 integration regression`。

**Gate:** P1 闭环未打通前，不进入 P2。

---

## Phase 3: P2 Operability and Industrialized Extension

### Task 9: P2-1 replay plus compare harness

**Depends on:** Task 8

**Files:**
- Modify: `scripts/replay_analysis_run.py`
- Modify: `services/api/analysis_report_service.py`
- Modify: `services/api/strategies/planner.py`
- Create: `scripts/compare_analysis_runs.py`
- Test: `tests/test_replay_analysis_run.py`
- Test: `tests/test_analysis_report_service.py`
- Doc: `docs/reference/analysis-runtime-contract.md`
- Doc: `docs/operations/multi-domain-analysis-rollout-checklist.md`

**Step 1: Write failing tests**

覆盖：完整 replay request 构建、compare 脚本输出固定结构 diff、缺 artifact / lineage fail-fast。

**Step 2: Run red tests**

Run:

```bash
.venv/bin/python -m pytest -q \
  tests/test_replay_analysis_run.py \
  tests/test_analysis_report_service.py
```

Expected: FAIL。

**Step 3: Implement minimal code**

- 扩展 replay request model；
- 新增 compare 脚本输出 `summary / confidence / recommendations / reason_code` diff；
- 保证 report writer 可取回 replay 必需字段。

**Step 4: Run green tests**

Run:

```bash
.venv/bin/python -m pytest -q \
  tests/test_replay_analysis_run.py \
  tests/test_analysis_report_service.py
```

Expected: PASS。

**Step 5: Update docs**

写清 replay 的场景：回归比较、灰度评估、事故分析。

**Step 6: Commit**

```bash
git add scripts/replay_analysis_run.py scripts/compare_analysis_runs.py services/api/analysis_report_service.py services/api/strategies/planner.py tests/test_replay_analysis_run.py tests/test_analysis_report_service.py docs/reference/analysis-runtime-contract.md docs/operations/multi-domain-analysis-rollout-checklist.md
git commit -m "feat(replay): add comparable analysis replay harness"
```

**Gate:** 任一 report 都必须可 replay 或 compare，而不是只能人工看 JSON。

---

### Task 10: P2-2 domain onboarding template and checklist

**Depends on:** Task 9

**Files:**
- Create: `docs/reference/analysis-domain-onboarding-template.md`
- Create: `docs/reference/analysis-domain-checklist.md`
- Modify: `docs/reference/analysis-runtime-contract.md`
- Modify: `docs/INDEX.md`
- Modify: `docs/architecture/module-boundaries.md`
- Test: `tests/test_architecture_doc_paths.py`

**Step 1: Write failing tests**

覆盖：新模板文档已进入 `docs/INDEX.md`；模板必须列出 manifest、artifact、strategy、specialist、report plane、review queue、fixtures、flags、docs。

**Step 2: Run red tests**

Run:

```bash
.venv/bin/python -m pytest -q tests/test_architecture_doc_paths.py
```

Expected: FAIL。

**Step 3: Implement minimal code**

新增 onboarding template 与 checklist，并在导航与契约中加入交叉引用。

**Step 4: Run green tests**

Run:

```bash
.venv/bin/python -m pytest -q tests/test_architecture_doc_paths.py
```

Expected: PASS。

**Step 5: Commit**

```bash
git add docs/reference/analysis-domain-onboarding-template.md docs/reference/analysis-domain-checklist.md docs/reference/analysis-runtime-contract.md docs/INDEX.md docs/architecture/module-boundaries.md tests/test_architecture_doc_paths.py
git commit -m "docs(analysis): add domain onboarding template and checklist"
```

**Gate:** 新域接入必须从“读隐性经验”升级为“按模板执行”。

---

### Task 11: Final regression and release-readiness verification

**Depends on:** Task 10

**Files:**
- Reference: `docs/operations/multi-domain-analysis-rollout-checklist.md`
- Reference: `docs/operations/slo-and-observability.md`
- Reference: `docs/reference/analysis-runtime-contract.md`

**Step 1: Run final regression suite**

Run:

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

Expected: PASS。

**Step 2: Re-read success definition**

逐条核对以下 8 项：

- 新增 analysis domain 时，装配接近声明式接入；
- specialist 输出不再以“非空 dict”作为通过标准；
- report plane 成为可靠 audit surface；
- rollout / rollback 有指标支撑；
- review queue 成为质量学习闭环；
- 高风险域可用 controlled graph 提质；
- 历史 report 可以 replay / compare；
- 新域接入有清晰模板和 checklist。

**Step 3: Run git diff review**

Run:

```bash
git status --short
git diff --stat
```

Expected: 仅包含本路线图范围内的改动。

**Step 4: Optional integration commit or PR prep**

如果需要合并前整理，可追加一个纯文档或发布准备 commit；否则直接进入 code review / PR。

---

## Week Mapping

- `Week 1`: Task 0, Task 1
- `Week 2`: Task 2, Task 3, Task 4
- `Week 3`: Task 5, Task 6
- `Week 4`: Task 7, Task 8
- `Week 5`: Task 9
- `Week 6`: Task 10, Task 11

---

## Stop Conditions

出现以下任一情况时，暂停后续任务并先修复当前阶段：

- P0 任一 gate 未通过；
- 回归测试引入跨 domain 破坏；
- lineage 出现 silent fallback；
- review queue 输出无法导出 feedback dataset；
- controlled job graph 开始侵入低风险域；
- 最终回归中出现未知新失败。

---

## Handoff

Plan complete and saved to `docs/plans/2026-03-09-agent-system-6week-ordered-execution-plan.md`.

推荐执行方式：

1. **Subagent-Driven (this session)** — 按 Task 0 -> Task 11 逐个执行，每个任务完成后做一次 review。
2. **Parallel Session (separate)** — 在独立 worktree 中打开新会话，使用 `executing-plans` 按本计划批量推进。
