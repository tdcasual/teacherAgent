# Agent System B/C Evolution Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在保留当前教学 workflow 主链与单前台 `Coordinator` 的前提下，把现有问卷多 Agent V1 演进为一套可复用的平台骨架，以支持 B（更多报告/问卷来源）和 C（多模态作业，优先短视频作业）两类新能力。

**Architecture:** 先把 A 阶段已经验证过的 survey 模式抽象成通用的 `target resolver + artifact adapter + strategy selector + specialist runtime + delivery/review` 五层骨架，再分别用 B 和 C 两个垂直切片验证平台抽象。整个演进过程中，前台仍然只有 `Coordinator`，specialist agent 不直接拥有用户会话；新来源优先扩 `adapter + artifact schema`，新任务优先扩 `strategy`，只有认知职责明显不同才新增 specialist。

**Tech Stack:** Python 3.13、FastAPI、Pydantic、现有 `application / deps / routes / wiring / workers` 分层、pytest、Vitest、React teacher workbench、现有文件存储 + 可替换 metadata repository。

---

## Context and Assumptions

1. 当前 A 已完成：问卷 webhook -> `survey_evidence_bundle` -> `survey_analyst` -> teacher report / review queue / workbench UI。
2. 本计划中的 **B** 指“更多报告/问卷来源接入”，包括自托管问卷系统、网页导出、PDF 报告等；目标不是再复制一套 `survey_*` 代码，而是复用通用分析骨架。
3. 本计划中的 **C** 指“多模态作业输入”，优先支持学生短视频作业；V1 重点是把视频/字幕/抽帧等证据变成老师可读分析结果，不做复杂自动评分真值写回。
4. 不把系统升级成开放式多 Agent 平台，不做前台 agent 自由协作，不做动态 marketplace。
5. 每个任务都遵守 `@superpowers:test-driven-development` 和 `@superpowers:verification-before-completion`：先写失败测试，再做最小实现，再做验证。

## Success Gates

在宣布“已支持 B/C 平台级扩展”之前，必须同时满足以下条件：

1. `Coordinator` 已从“关键词 + 最新报告猜测”升级到显式 target resolution，不再默认依赖最新 `analysis_ready` report。
2. 系统已存在统一 artifact 层，A/B/C 都通过 `artifact_type + strategy + handoff` 进入 specialist runtime，而不是每个域自己发明编排入口。
3. specialist runtime 已具备最小治理能力：budget、timeout、事件埋点、失败分类、fallback policy。
4. teacher 可见报告已升级为统一 analysis report 面，survey/class-report/video-homework 都能进入同一类读取、review、rerun 契约。
5. B 至少支持两种以上报告来源接入，并复用同一条 evidence pipeline。
6. C 至少支持短视频作业从上传证据到老师可读反馈的闭环，并具备 review queue 与 rerun 入口。
7. 评测样例、release checklist、rollout guardrails 已覆盖 A/B/C 三类策略。

## Non-Goals

- 不构建通用多 agent 聊天平台。
- 不让 specialist agent 直接拥有老师前台会话。
- 不在本阶段做学生长期画像真值写回。
- 不在 C 阶段一次性支持所有音视频格式与复杂自动评分 rubric。
- 不在第一轮就强制把存储完全迁移到数据库；先建立抽象，再决定是否迁移实现。

## Execution Rules

每个任务执行时遵守同一微循环：

1. 先补最小失败测试或 fixture。
2. 跑目标测试确认失败原因与任务目标一致。
3. 做最小实现，不顺手扩 scope。
4. 跑任务级验证命令。
5. 通过后立即提交一个小 commit。
6. 若任务跨后端 / 前端 / 文档三层，顺序必须是：后端契约 -> specialist/runtime -> UI -> docs/rollout。

---

## Phase A: Generalize the Control Plane

### Task 1: 提取显式 target resolver，替代“最新报告猜测”

**Files:**
- Create: `services/api/analysis_target_models.py`
- Create: `services/api/analysis_target_resolution_service.py`
- Modify: `services/api/agent_service.py`
- Modify: `services/api/tool_dispatch_service.py`
- Modify: `services/common/tool_registry.py`
- Test: `tests/test_analysis_target_resolution_service.py`
- Test: `tests/test_survey_chat_handoff.py`

**Steps:**
1. 在 `tests/test_analysis_target_resolution_service.py` 中先写失败测试，覆盖：显式 `report_id` 优先、会话最近选择对象回落、同老师多个报告时禁止“拿最新猜测”的歧义路径。
2. 在 `services/api/analysis_target_models.py` 中定义统一 target contract：`target_type`、`target_id`、`artifact_type`、`teacher_id`、`source_domain`、`resolution_reason`。
3. 在 `services/api/analysis_target_resolution_service.py` 中实现 target resolver：按显式参数、会话上下文、工具返回值、单一候选对象顺序解析，不允许在多候选时静默猜测。
4. 在 `services/common/tool_registry.py` 与 `services/api/tool_dispatch_service.py` 中为 analysis/report 类工具补 `report_id`、`target_id` 参数路径，减少 Coordinator 只能靠自然语言反解对象的情况。
5. 在 `services/api/agent_service.py` 中替换当前 survey handoff 的“最新 `analysis_ready` 报告”逻辑，统一通过 target resolver 决定 handoff 输入对象。
6. 跑目标测试，确认 handoff 只在目标对象明确时发生；目标不明确时，Coordinator 返回“需要确认对象”而不是误选。

**Validation:**
- Run: `python3.13 -m pytest -q tests/test_analysis_target_resolution_service.py tests/test_survey_chat_handoff.py`
- Expected: PASS。

**Acceptance:**
- Coordinator 不再通过“最新报告”猜对象。
- A/B/C 三类分析对象都可复用同一 target resolution contract。

**Commit:**
```bash
git add services/api/analysis_target_models.py services/api/analysis_target_resolution_service.py services/api/agent_service.py services/api/tool_dispatch_service.py services/common/tool_registry.py tests/test_analysis_target_resolution_service.py tests/test_survey_chat_handoff.py
git commit -m "feat(analysis): add explicit target resolution for coordinator handoff"
```

### Task 2: 提取通用 artifact contract 与 adapter registry

**Files:**
- Create: `services/api/artifacts/__init__.py`
- Create: `services/api/artifacts/contracts.py`
- Create: `services/api/artifacts/registry.py`
- Create: `services/api/artifacts/runtime.py`
- Modify: `services/api/survey_bundle_models.py`
- Modify: `services/api/wiring/survey_wiring.py`
- Test: `tests/test_artifact_contracts.py`
- Test: `tests/test_artifact_registry.py`

**Steps:**
1. 先写失败测试，固定 artifact envelope、adapter spec、按 `artifact_type` 查询 adapter、未知 adapter 的失败方式。
2. 在 `services/api/artifacts/contracts.py` 定义统一 artifact contract：`artifact_type`、`schema_version`、`subject_scope`、`evidence_refs`、`confidence`、`missing_fields`、`provenance`。
3. 在 `services/api/artifacts/registry.py` 定义 adapter 注册结构：`adapter_id`、`accepted_inputs`、`output_artifact_type`、`task_kinds`、`validation_rules`。
4. 在 `services/api/artifacts/runtime.py` 中提供统一 adapter 运行入口，保证 survey、class-report、video-homework 以后都走同一 adapter runtime。
5. 让 `services/api/survey_bundle_models.py` 与 `services/api/wiring/survey_wiring.py` 适配新 artifact contract，但保持现有 survey V1 读写兼容。
6. 跑目标测试，确认 registry/runtme 已具备“新增来源先注册 adapter”的扩展方式。

**Validation:**
- Run: `python3.13 -m pytest -q tests/test_artifact_contracts.py tests/test_artifact_registry.py`
- Expected: PASS。

**Acceptance:**
- 新来源接入的第一落点是 adapter registry，而不是新写一套 orchestrator。
- `survey_evidence_bundle` 已成为通用 artifact 层的一个实例，而不是孤立 domain 类型。

**Commit:**
```bash
git add services/api/artifacts/__init__.py services/api/artifacts/contracts.py services/api/artifacts/registry.py services/api/artifacts/runtime.py services/api/survey_bundle_models.py services/api/wiring/survey_wiring.py tests/test_artifact_contracts.py tests/test_artifact_registry.py
git commit -m "feat(artifacts): add generic artifact contracts and adapter registry"
```

### Task 3: 引入 strategy selector 与 handoff planner

**Files:**
- Create: `services/api/strategies/__init__.py`
- Create: `services/api/strategies/contracts.py`
- Create: `services/api/strategies/selector.py`
- Create: `services/api/strategies/planner.py`
- Modify: `services/api/agent_service.py`
- Modify: `services/api/survey_orchestrator_service.py`
- Test: `tests/test_strategy_selector.py`
- Test: `tests/test_strategy_planner.py`

**Steps:**
1. 先写失败测试，覆盖：同一 artifact 在不同任务目标下选不同 strategy、低置信度 artifact 被强制路由到 review/结构化策略、未知组合返回显式“不支持”。
2. 在 `services/api/strategies/contracts.py` 中定义 `strategy_id`、`accepted_artifacts`、`task_kinds`、`specialist_agent`、`review_policy`、`delivery_mode`。
3. 在 `services/api/strategies/selector.py` 中实现选择器，根据角色、artifact type、task kind、confidence 与 target scope 决定 strategy。
4. 在 `services/api/strategies/planner.py` 中实现 handoff planner：把 strategy 结果转换为 `HandoffContract`、delivery/review 决策和 fallback policy。
5. 让 `services/api/survey_orchestrator_service.py` 与 `services/api/agent_service.py` 不再手写 survey 特例 handoff，而是通过 strategy selector + planner 产出 handoff。
6. 跑目标测试，确认“新增业务方式优先扩 strategy，不优先扩 coordinator if/else”。

**Validation:**
- Run: `python3.13 -m pytest -q tests/test_strategy_selector.py tests/test_strategy_planner.py`
- Expected: PASS。

**Acceptance:**
- Strategy Layer 成为真实运行时对象，而不是只存在于设计文档里的概念。
- A/B/C 三类能力以后都按 `artifact + task_kind -> strategy` 扩展。

**Commit:**
```bash
git add services/api/strategies/__init__.py services/api/strategies/contracts.py services/api/strategies/selector.py services/api/strategies/planner.py services/api/agent_service.py services/api/survey_orchestrator_service.py tests/test_strategy_selector.py tests/test_strategy_planner.py
git commit -m "feat(strategy): add strategy selector and handoff planner"
```

---

## Phase B: Harden Runtime Governance and Unified Report Plane

### Task 4: 强化 specialist runtime 治理能力

**Files:**
- Create: `services/api/specialist_agents/governor.py`
- Create: `services/api/specialist_agents/events.py`
- Modify: `services/api/specialist_agents/runtime.py`
- Modify: `services/api/specialist_agents/registry.py`
- Modify: `services/api/wiring/survey_wiring.py`
- Test: `tests/test_specialist_agent_governor.py`
- Test: `tests/test_specialist_agent_runtime.py`

**Steps:**
1. 先写失败测试，固定 runtime 必须执行 budget 校验、timeout、异常分类和 event 记录；runner 抛错不能直接泄漏原始 traceback 给上层。
2. 在 `services/api/specialist_agents/governor.py` 中实现统一 governor：执行前校验 budget、执行中记录耗时/步骤、执行后归一化 status 与 confidence。
3. 在 `services/api/specialist_agents/events.py` 中定义 specialist 生命周期事件结构：`prepared`、`started`、`completed`、`failed`、`fallback`。
4. 修改 `services/api/specialist_agents/runtime.py` 让所有 specialist 都经过 governor，而不是直接 `runner(request)`。
5. 修改 `services/api/specialist_agents/registry.py` 与 `services/api/wiring/survey_wiring.py`，把 budgets / output_schema / evaluation_suite 真正用于 runtime，而不只是存元数据。
6. 跑目标测试，确认 runtime 已具备最小治理闭环。

**Validation:**
- Run: `python3.13 -m pytest -q tests/test_specialist_agent_governor.py tests/test_specialist_agent_runtime.py`
- Expected: PASS。

**Acceptance:**
- specialist runtime 具备统一治理，而不是“注册即可裸跑”。
- 后续新增 agent 的治理成本固定在 runtime 层，不散落到各 domain orchestrator。

**Commit:**
```bash
git add services/api/specialist_agents/governor.py services/api/specialist_agents/events.py services/api/specialist_agents/runtime.py services/api/specialist_agents/registry.py services/api/wiring/survey_wiring.py tests/test_specialist_agent_governor.py tests/test_specialist_agent_runtime.py
git commit -m "feat(agents): add runtime governance for specialist execution"
```

### Task 5: 建立统一 analysis report 读模型与路由

**Files:**
- Create: `services/api/analysis_report_models.py`
- Create: `services/api/analysis_report_service.py`
- Create: `services/api/routes/analysis_report_routes.py`
- Modify: `services/api/api_models.py`
- Modify: `services/api/app_routes.py`
- Modify: `services/api/tool_dispatch_service.py`
- Modify: `services/common/tool_registry.py`
- Test: `tests/test_analysis_report_service.py`
- Test: `tests/test_analysis_report_routes.py`
- Test: `tests/test_tool_dispatch_types.py`

**Steps:**
1. 先写失败测试，固定 teacher 可按 domain/strategy/status/target_type 读取统一 analysis report summary/detail，并支持 rerun/review 操作。
2. 在 `services/api/analysis_report_models.py` 中定义统一 teacher 可见报告模型：`analysis_type`、`target_type`、`target_id`、`strategy_id`、`status`、`confidence`、`summary`、`review_required`。
3. 在 `services/api/analysis_report_service.py` 中建立统一读模型层，让 survey/class-report/video-homework 都可注册到同一报告平面。
4. 在 `services/api/routes/analysis_report_routes.py` 中提供统一读取接口，并在 `services/api/app_routes.py` 注册；保留旧 survey routes 一段时间作为兼容 facade。
5. 在 `services/common/tool_registry.py` 与 `services/api/tool_dispatch_service.py` 中增加通用 report 工具，例如 `analysis.report.list/get/rerun`，并保留 survey 工具兼容到迁移完成。
6. 跑目标测试，确认 teacher UI 与 Coordinator 都可逐步从 survey 专用 read model 切到统一 report plane。

**Validation:**
- Run: `python3.13 -m pytest -q tests/test_analysis_report_service.py tests/test_analysis_report_routes.py tests/test_tool_dispatch_types.py`
- Expected: PASS。

**Acceptance:**
- teacher 可见报告不再以 survey 为唯一中心对象。
- B/C 能直接落到统一 report plane，而不必复制 `survey_report_service.py` 模式。

**Commit:**
```bash
git add services/api/analysis_report_models.py services/api/analysis_report_service.py services/api/routes/analysis_report_routes.py services/api/api_models.py services/api/app_routes.py services/api/tool_dispatch_service.py services/common/tool_registry.py tests/test_analysis_report_service.py tests/test_analysis_report_routes.py tests/test_tool_dispatch_types.py
git commit -m "feat(reports): add unified analysis report read plane"
```

### Task 6: 提取 review queue 与 metadata repository 抽象

**Files:**
- Create: `services/api/analysis_metadata_repository.py`
- Create: `services/api/review_queue_models.py`
- Create: `services/api/review_queue_service.py`
- Modify: `services/api/survey_repository.py`
- Modify: `services/api/survey_review_queue_service.py`
- Modify: `services/api/survey_report_service.py`
- Test: `tests/test_analysis_metadata_repository.py`
- Test: `tests/test_review_queue_service.py`
- Test: `tests/test_survey_review_queue_service.py`

**Steps:**
1. 先写失败测试，固定 review item 的状态（queued/claimed/resolved/rejected）、teacher/domain 过滤、以及 file-backed metadata repository 的替换接口。
2. 在 `services/api/analysis_metadata_repository.py` 中定义统一 metadata repository protocol，先保留 file-backed 实现，不急着迁移 DB。
3. 在 `services/api/review_queue_models.py` 与 `services/api/review_queue_service.py` 中建立 domain-agnostic review queue contract，支持 survey/class-report/video-homework 共用同一 review 面。
4. 修改 `services/api/survey_repository.py`、`services/api/survey_review_queue_service.py`、`services/api/survey_report_service.py` 让 survey V1 也通过新抽象工作。
5. 保持现有 JSON/JSONL 存储结构兼容，但新增必要的 operation 字段，避免以后多人 review 时完全不可查询。
6. 跑目标测试，确认抽象已建立且 survey 旧路径未回归。

**Validation:**
- Run: `python3.13 -m pytest -q tests/test_analysis_metadata_repository.py tests/test_review_queue_service.py tests/test_survey_review_queue_service.py`
- Expected: PASS。

**Acceptance:**
- review queue 成为统一平台层，而不是 survey 专属能力。
- 后续若迁移到 DB，只需要替换 repository 实现，不需要重写 orchestrator。

**Commit:**
```bash
git add services/api/analysis_metadata_repository.py services/api/review_queue_models.py services/api/review_queue_service.py services/api/survey_repository.py services/api/survey_review_queue_service.py services/api/survey_report_service.py tests/test_analysis_metadata_repository.py tests/test_review_queue_service.py tests/test_survey_review_queue_service.py
git commit -m "feat(review): add generic review queue and metadata repository"
```

---

## Phase C: Refactor A onto the New Platform

### Task 7: 让 survey V1 跑在新的 artifact / strategy / report plane 上

**Files:**
- Modify: `services/api/survey_orchestrator_service.py`
- Modify: `services/api/routes/survey_routes.py`
- Modify: `services/api/survey_report_service.py`
- Modify: `services/api/wiring/survey_wiring.py`
- Modify: `services/api/specialist_agents/survey_analyst.py`
- Test: `tests/test_survey_orchestrator_service.py`
- Test: `tests/test_survey_report_service.py`
- Test: `tests/test_survey_analyst_agent.py`

**Steps:**
1. 先补失败测试，固定 survey 新路径仍然产出与旧契约兼容的 teacher report/detail，同时底层已通过 strategy selector / analysis report plane 运行。
2. 修改 `services/api/survey_orchestrator_service.py`，让 intake -> bundle -> strategy -> handoff -> delivery -> review 统一走平台抽象。
3. 修改 `services/api/specialist_agents/survey_analyst.py`，把输入输出契约绑定到通用 artifact/report 面，但保持 survey V1 的输出字段与 prompt 不变。
4. 修改 `services/api/survey_report_service.py` 与 `services/api/routes/survey_routes.py`，把它们收敛为兼容 facade，而不是长期的一等平台接口。
5. 修改 `services/api/wiring/survey_wiring.py`，让 survey 只负责本 domain 的 adapter/spec 注册，不再承担通用平台 wiring 逻辑。
6. 跑目标测试，确认 A 完整迁移后行为不变。

**Validation:**
- Run: `python3.13 -m pytest -q tests/test_survey_orchestrator_service.py tests/test_survey_report_service.py tests/test_survey_analyst_agent.py tests/test_survey_chat_handoff.py`
- Expected: PASS。

**Acceptance:**
- survey V1 成为平台化后的第一个“内建 strategy”，而不是一条孤立旁路。
- 迁移 A 后，B/C 才有资格继续落地。

**Commit:**
```bash
git add services/api/survey_orchestrator_service.py services/api/routes/survey_routes.py services/api/survey_report_service.py services/api/wiring/survey_wiring.py services/api/specialist_agents/survey_analyst.py tests/test_survey_orchestrator_service.py tests/test_survey_report_service.py tests/test_survey_analyst_agent.py tests/test_survey_chat_handoff.py
git commit -m "refactor(survey): migrate survey v1 onto generic analysis platform"
```

### Task 8: 升级 Coordinator 与 teacher workbench，使目标选择显式化

**Files:**
- Create: `frontend/apps/teacher/src/features/workbench/hooks/useAnalysisReports.ts`
- Create: `frontend/apps/teacher/src/features/workbench/workflow/AnalysisReportSection.tsx`
- Create: `frontend/apps/teacher/src/features/workbench/workflow/AnalysisReportSection.test.tsx`
- Modify: `frontend/apps/teacher/src/App.tsx`
- Modify: `frontend/apps/teacher/src/features/workbench/tabs/WorkflowTab.tsx`
- Modify: `frontend/apps/teacher/src/types/workflow.ts`
- Modify: `frontend/apps/shared/featureFlags.ts`
- Test: `tests/test_analysis_target_resolution_service.py`
- Test: `frontend/apps/teacher/src/features/workbench/workflow/AnalysisReportSection.test.tsx`

**Steps:**
1. 先写前端单测和 target resolution 失败测试，固定老师可以显式选择 report/analysis 对象，不再被动依赖“最新一条”。
2. 在 `useAnalysisReports.ts` 中封装统一 analysis report list/detail/rerun/review API，而不是只服务 survey。
3. 在 `AnalysisReportSection.tsx` 中提供通用选择面：domain、strategy、状态、对象摘要、review 标记、rerun 入口。
4. 修改 `frontend/apps/teacher/src/App.tsx`、`WorkflowTab.tsx`、`workflow.ts`，让 survey/class-report/video-homework 都能用统一 workbench 区块承载。
5. 调整 `services/api/analysis_target_resolution_service.py` 与 Coordinator 交互，确保 UI 选择的对象能成为 handoff 输入，而不是重新猜。
6. 跑目标测试和 teacher build，确认显式目标选择路径稳定。

**Validation:**
- Run: `python3.13 -m pytest -q tests/test_analysis_target_resolution_service.py`
- Run: `cd frontend && npm run test:unit -- apps/teacher/src/features/workbench/workflow/AnalysisReportSection.test.tsx`
- Run: `cd frontend && npm run build:teacher`
- Expected: PASS。

**Acceptance:**
- 老师端 analysis/report 入口已经平台化。
- 后续 B/C 新能力可以直接接入同一 workbench 面，而不是各自加一个专属 section。

**Commit:**
```bash
git add frontend/apps/teacher/src/features/workbench/hooks/useAnalysisReports.ts frontend/apps/teacher/src/features/workbench/workflow/AnalysisReportSection.tsx frontend/apps/teacher/src/features/workbench/workflow/AnalysisReportSection.test.tsx frontend/apps/teacher/src/App.tsx frontend/apps/teacher/src/features/workbench/tabs/WorkflowTab.tsx frontend/apps/teacher/src/types/workflow.ts frontend/apps/shared/featureFlags.ts tests/test_analysis_target_resolution_service.py
git commit -m "feat(teacher-ui): add explicit analysis target selection and unified report section"
```

---

## Phase D: Deliver B (More Report / Questionnaire Sources)

### Task 9: 建立 class-report artifact 与多来源 adapter

**Files:**
- Create: `services/api/class_signal_bundle_models.py`
- Create: `services/api/report_adapters/__init__.py`
- Create: `services/api/report_adapters/self_hosted_form_adapter.py`
- Create: `services/api/report_adapters/web_export_report_adapter.py`
- Create: `services/api/report_adapters/pdf_report_adapter.py`
- Modify: `services/api/artifacts/registry.py`
- Modify: `services/api/upload_text_service.py`
- Test: `tests/test_class_signal_bundle_models.py`
- Test: `tests/test_self_hosted_form_adapter.py`
- Test: `tests/test_web_export_report_adapter.py`
- Test: `tests/test_pdf_report_adapter.py`

**Steps:**
1. 先写失败测试，覆盖自托管问卷 JSON、网页导出 HTML、PDF 摘要三种来源都能落到统一 `class_signal_bundle`。
2. 在 `services/api/class_signal_bundle_models.py` 中定义比 survey 更宽的班级报告 artifact：允许保留 question-like、theme-like、risk-like 信号，而不要求所有来源都长得像问卷。
3. 在 `services/api/report_adapters/` 中实现三种 adapter，把输入映射到统一 artifact contract，并记录缺失字段与 provenance。
4. 在 `services/api/artifacts/registry.py` 中注册这些 adapter，确保 B 的扩展方式是“新 provider = 新 adapter”。
5. 只在 `services/api/upload_text_service.py` 放共用型解析能力，不把 provider 专用规则写死在通用服务中。
6. 跑目标测试，确认 B 的第一个核心目标——多来源输入归一化——已经成立。

**Validation:**
- Run: `python3.13 -m pytest -q tests/test_class_signal_bundle_models.py tests/test_self_hosted_form_adapter.py tests/test_web_export_report_adapter.py tests/test_pdf_report_adapter.py`
- Expected: PASS。

**Acceptance:**
- B 至少已有 3 类来源可复用同一 artifact 骨架。
- 后续新 provider 接入只需要新增 adapter 与 fixture，而不是新建整条系统。

**Commit:**
```bash
git add services/api/class_signal_bundle_models.py services/api/report_adapters/__init__.py services/api/report_adapters/self_hosted_form_adapter.py services/api/report_adapters/web_export_report_adapter.py services/api/report_adapters/pdf_report_adapter.py services/api/artifacts/registry.py services/api/upload_text_service.py tests/test_class_signal_bundle_models.py tests/test_self_hosted_form_adapter.py tests/test_web_export_report_adapter.py tests/test_pdf_report_adapter.py
git commit -m "feat(class-report): add multi-source report adapters and class signal bundle"
```

### Task 10: 实现 B 的 `Class Signal Analyst` 与 report 交付链路

**Files:**
- Create: `services/api/specialist_agents/class_signal_analyst.py`
- Create: `prompts/v1/teacher/agents/class_signal_analyst.md`
- Create: `services/api/class_report_orchestrator_service.py`
- Create: `services/api/class_report_service.py`
- Create: `services/api/routes/class_report_routes.py`
- Modify: `services/api/app_routes.py`
- Modify: `services/api/wiring/survey_wiring.py`
- Test: `tests/test_class_signal_analyst.py`
- Test: `tests/test_class_report_orchestrator_service.py`
- Test: `tests/test_class_report_routes.py`

**Steps:**
1. 先写失败测试，覆盖 class-report 正常分析、低置信度进入 review、teacher 可读取报告详情三条路径。
2. 实现 `Class Signal Analyst`，专注“班级信号归纳 + 教学建议 + 缺口说明”，不要一开始引入学生级画像或自动动作生成。
3. 在 `services/api/class_report_orchestrator_service.py` 中把 B 的 artifact -> strategy -> specialist -> report plane 串起来，沿用平台层已有 contract。
4. 在 `services/api/class_report_service.py` 和 `services/api/routes/class_report_routes.py` 中暴露 B 的 domain 入口；如果 analysis report plane 已足够，则 route 只做轻量 facade。
5. 在 wiring 中把新 specialist 与 strategy 注册进去，并复用既有 runtime governor / review queue / delivery plane。
6. 跑目标测试，确认 B 已具备第一条完整业务闭环。

**Validation:**
- Run: `python3.13 -m pytest -q tests/test_class_signal_analyst.py tests/test_class_report_orchestrator_service.py tests/test_class_report_routes.py`
- Expected: PASS。

**Acceptance:**
- B 已不是“多输入的 survey”，而是一条更泛化的班级报告分析能力。
- 平台抽象已被第二个垂直切片验证通过。

**Commit:**
```bash
git add services/api/specialist_agents/class_signal_analyst.py prompts/v1/teacher/agents/class_signal_analyst.md services/api/class_report_orchestrator_service.py services/api/class_report_service.py services/api/routes/class_report_routes.py services/api/app_routes.py services/api/wiring/survey_wiring.py tests/test_class_signal_analyst.py tests/test_class_report_orchestrator_service.py tests/test_class_report_routes.py
git commit -m "feat(class-report): add class signal analysis specialist and orchestrator"
```

---

## Phase E: Deliver C (Multimodal Homework / Short Video)

### Task 11: 建立多模态作业 contract 与 media extraction pipeline

**Files:**
- Create: `services/api/multimodal_submission_models.py`
- Create: `services/api/multimodal_repository.py`
- Create: `services/api/media_extract_service.py`
- Create: `services/api/media_segment_models.py`
- Create: `services/api/routes/multimodal_routes.py`
- Modify: `services/api/app_routes.py`
- Modify: `services/api/paths.py`
- Modify: `services/api/settings.py`
- Test: `tests/test_multimodal_submission_models.py`
- Test: `tests/test_media_extract_service.py`
- Test: `tests/test_multimodal_routes.py`

**Steps:**
1. 先写失败测试，覆盖短视频作业的基本 contract：上传元数据、转写片段、抽帧证据、提取失败 fallback。
2. 在 `services/api/multimodal_submission_models.py` 与 `services/api/media_segment_models.py` 中定义视频作业 artifact：媒体文件、时间片段、字幕/ASR、关键帧、teacher/student scope、provenance。
3. 在 `services/api/media_extract_service.py` 中实现第一版抽取流水线接口：转写、OCR、关键帧/字幕合并；V1 允许用 mock/external service adapter 占位，不要把供应商强耦合写死。
4. 在 `services/api/multimodal_repository.py` 与 `services/api/paths.py` 中建立多模态作业的元数据与衍生文件布局，避免复用 survey/job 路径。
5. 在 `services/api/routes/multimodal_routes.py` 与 `services/api/settings.py` 中暴露受控入口与资源限制配置（时长、大小、抽取超时）。
6. 跑目标测试，确认 C 的底层证据抽取 contract 已成立。

**Validation:**
- Run: `python3.13 -m pytest -q tests/test_multimodal_submission_models.py tests/test_media_extract_service.py tests/test_multimodal_routes.py`
- Expected: PASS。

**Acceptance:**
- C 的第一个核心问题——把视频/字幕/抽帧变成可消费 artifact——已经有稳定契约。
- 后续 specialist 只消费 artifact，不直接操作原始视频文件。

**Commit:**
```bash
git add services/api/multimodal_submission_models.py services/api/multimodal_repository.py services/api/media_extract_service.py services/api/media_segment_models.py services/api/routes/multimodal_routes.py services/api/app_routes.py services/api/paths.py services/api/settings.py tests/test_multimodal_submission_models.py tests/test_media_extract_service.py tests/test_multimodal_routes.py
git commit -m "feat(multimodal): add multimodal submission contracts and media extraction pipeline"
```

### Task 12: 实现 `Video Homework Analyst` 与 C 的老师交付面

**Files:**
- Create: `services/api/specialist_agents/video_homework_analyst.py`
- Create: `prompts/v1/teacher/agents/video_homework_analyst.md`
- Create: `services/api/multimodal_orchestrator_service.py`
- Create: `services/api/multimodal_report_service.py`
- Create: `frontend/apps/teacher/src/features/workbench/workflow/VideoHomeworkAnalysisSection.tsx`
- Create: `frontend/apps/teacher/src/features/workbench/workflow/VideoHomeworkAnalysisSection.test.tsx`
- Modify: `frontend/apps/teacher/src/App.tsx`
- Modify: `frontend/apps/teacher/src/features/workbench/tabs/WorkflowTab.tsx`
- Modify: `frontend/apps/teacher/src/types/workflow.ts`
- Test: `tests/test_video_homework_analyst.py`
- Test: `tests/test_multimodal_orchestrator_service.py`

**Steps:**
1. 先写失败测试，固定视频作业分析输出至少包含：完成度概览、表达/展示信号、证据片段引用、教学建议、confidence/gaps。
2. 实现 `Video Homework Analyst`，让它只做“老师可读反馈与证据组织”，不要在第一轮就承担自动打分真值回写。
3. 在 `services/api/multimodal_orchestrator_service.py` 中把 media artifact -> strategy -> specialist -> unified analysis report plane 串起来，并沿用 review queue。
4. 在 `services/api/multimodal_report_service.py` 中处理老师可见摘要与详情；尽量复用统一 analysis report plane，避免再次复制 survey/class-report 报告模型。
5. 在 teacher workbench 中增加视频作业分析区块，并复用已有 unified report selection；必要时只增加 domain-specific detail renderer。
6. 跑目标测试与 teacher build，确认 C 的第一条闭环已经可演示、可 review、可 rerun。

**Validation:**
- Run: `python3.13 -m pytest -q tests/test_video_homework_analyst.py tests/test_multimodal_orchestrator_service.py`
- Run: `cd frontend && npm run test:unit -- apps/teacher/src/features/workbench/workflow/VideoHomeworkAnalysisSection.test.tsx`
- Run: `cd frontend && npm run build:teacher`
- Expected: PASS。

**Acceptance:**
- C 已有完整但克制的第一版闭环。
- 视频能力通过新 artifact 与 strategy 接入平台，而不是旁路系统。

**Commit:**
```bash
git add services/api/specialist_agents/video_homework_analyst.py prompts/v1/teacher/agents/video_homework_analyst.md services/api/multimodal_orchestrator_service.py services/api/multimodal_report_service.py frontend/apps/teacher/src/features/workbench/workflow/VideoHomeworkAnalysisSection.tsx frontend/apps/teacher/src/features/workbench/workflow/VideoHomeworkAnalysisSection.test.tsx frontend/apps/teacher/src/App.tsx frontend/apps/teacher/src/features/workbench/tabs/WorkflowTab.tsx frontend/apps/teacher/src/types/workflow.ts tests/test_video_homework_analyst.py tests/test_multimodal_orchestrator_service.py
git commit -m "feat(multimodal): add video homework specialist and teacher delivery"
```

---

## Phase F: Evaluation, Rollout, and Migration Guardrails

### Task 13: 扩展跨域评测、fixtures 与 rollout 文档

**Files:**
- Create: `scripts/analysis_strategy_eval.py`
- Create: `tests/fixtures/analysis_reports/self_hosted_basic.json`
- Create: `tests/fixtures/analysis_reports/web_export_basic.json`
- Create: `tests/fixtures/multimodal/video_homework_basic.json`
- Create: `docs/reference/analysis-runtime-contract.md`
- Create: `docs/operations/multi-domain-analysis-rollout-checklist.md`
- Modify: `docs/INDEX.md`
- Modify: `docs/reference/survey-analysis-contract.md`
- Modify: `tests/test_docs_architecture_presence.py`
- Modify: `tests/test_ci_backend_hardening_workflow.py`
- Test: `tests/test_analysis_strategy_eval.py`
- Test: `tests/test_docs_architecture_presence.py`
- Test: `tests/test_ci_backend_hardening_workflow.py`

**Steps:**
1. 先写失败测试，固定新的跨域评测脚本、fixtures、contract 文档和 rollout checklist 都必须存在并被索引。
2. 在 `scripts/analysis_strategy_eval.py` 中实现统一离线评测：A/B/C 三类 artifact 的 coverage、missing rate、confidence buckets、expectation failures。
3. 准备 B/C 的最小 golden fixtures，让 class-report 和 video-homework 都至少有一组可跑样例。
4. 在 `docs/reference/analysis-runtime-contract.md` 中写清统一平台层 contract：target resolver、artifact adapter、strategy selector、specialist runtime、delivery/review。
5. 在 `docs/operations/multi-domain-analysis-rollout-checklist.md` 中写出 B/C 的 shadow -> beta -> release -> rollback 策略，并与 survey checklist 衔接。
6. 更新 `docs/INDEX.md` 和 CI 守卫测试，然后跑目标测试与离线评测脚本。

**Validation:**
- Run: `python3.13 -m pytest -q tests/test_analysis_strategy_eval.py tests/test_docs_architecture_presence.py tests/test_ci_backend_hardening_workflow.py`
- Run: `python3.13 scripts/analysis_strategy_eval.py --fixtures tests/fixtures --json --summary-only`
- Expected: PASS。

**Acceptance:**
- A/B/C 三类能力已具备统一评测与发布门禁。
- 后续新增 strategy/agent 的成本主要变成“加 fixture + 加 eval + 加 rollout 配置”，而不是重写架构。

**Commit:**
```bash
git add scripts/analysis_strategy_eval.py tests/fixtures/analysis_reports tests/fixtures/multimodal docs/reference/analysis-runtime-contract.md docs/operations/multi-domain-analysis-rollout-checklist.md docs/INDEX.md docs/reference/survey-analysis-contract.md tests/test_analysis_strategy_eval.py tests/test_docs_architecture_presence.py tests/test_ci_backend_hardening_workflow.py
git commit -m "docs(analysis): add cross-domain eval and rollout guardrails"
```

---

## Suggested Delivery Order

推荐按以下里程碑推进，而不是 A/B/C 同时并行：

1. `M1`: Task 1-4
   - 把 control plane、artifact、strategy、runtime 治理抽象出来
2. `M2`: Task 5-8
   - 得到统一 analysis report/review/teacher UI 平面，并让 survey 成为平台内建策略
3. `M3`: Task 9-10
   - 交付 B：多报告/问卷来源分析
4. `M4`: Task 11-12
   - 交付 C：短视频作业分析闭环
5. `M5`: Task 13
   - 补齐跨域评测、文档与发布门禁

## Final Verification

全部任务完成后，执行一次跨域最小全链路验证：

**Backend platform + A/B/C targeted:**
```bash
python3.13 -m pytest -q \
  tests/test_analysis_target_resolution_service.py \
  tests/test_artifact_contracts.py \
  tests/test_artifact_registry.py \
  tests/test_strategy_selector.py \
  tests/test_strategy_planner.py \
  tests/test_specialist_agent_governor.py \
  tests/test_specialist_agent_runtime.py \
  tests/test_analysis_report_service.py \
  tests/test_analysis_report_routes.py \
  tests/test_review_queue_service.py \
  tests/test_analysis_metadata_repository.py \
  tests/test_survey_*.py \
  tests/test_class_signal_analyst.py \
  tests/test_class_report_orchestrator_service.py \
  tests/test_class_report_routes.py \
  tests/test_multimodal_submission_models.py \
  tests/test_media_extract_service.py \
  tests/test_multimodal_routes.py \
  tests/test_video_homework_analyst.py \
  tests/test_multimodal_orchestrator_service.py
```

**Frontend targeted:**
```bash
cd frontend && npm run test:unit -- \
  apps/teacher/src/features/workbench/workflow/AnalysisReportSection.test.tsx \
  apps/teacher/src/features/workbench/workflow/VideoHomeworkAnalysisSection.test.tsx
cd frontend && npm run build:teacher
```

**Docs / eval / rollout:**
```bash
python3.13 scripts/analysis_strategy_eval.py --fixtures tests/fixtures --json --summary-only
python3.13 -m pytest -q tests/test_docs_architecture_presence.py tests/test_ci_backend_hardening_workflow.py
```

## Acceptance Criteria

- `Coordinator` 仍然是唯一默认前台 Agent，specialist agent 不直接抢占用户会话。
- A/B/C 三类能力都通过统一 `artifact + strategy + runtime + report/review` 平面运行。
- B 新增来源时主要新增 adapter；C 新增模态时主要新增 artifact + extraction pipeline；两者都不需要复制 survey 的整条架构。
- 低置信度结果统一进入 review queue，不直接污染老师主界面和长期 memory。
- 老师端通过统一 analysis report/workbench 面读取不同 domain 的分析结果。
- 平台具备最小评测、发布、回滚与观察闭环，能支持后续继续扩新 agent/新作业方式。
