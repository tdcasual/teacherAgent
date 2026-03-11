# 统一分析运行时契约（Analysis Runtime Contract）

Date: 2026-03-07

## 1. 目标与边界

- 本系统是教学 workflow 产品，不是开放式多 Agent 平台。
- `Coordinator` 仍然是唯一默认前台 Agent；specialist agent 只通过内部 handoff 执行，不直接抢占老师会话。
- A/B/C 三类分析能力统一走同一平台平面：`target resolver -> artifact adapter -> strategy selector -> specialist runtime -> analysis report / review queue`。
- 后续扩域时优先新增 fixture、adapter、strategy 与 rollout 配置，而不是复制一条平行架构。

## 2. 统一平台平面

### 2.1 Target Resolver

target resolver 负责把老师当前对话中的分析对象显式化，避免“默认猜最新报告”的隐式推测。

当前统一 contract：

- `target_type`
- `target_id`
- `analysis_type`
- `strategy_id`（可为空，由 selector 决定）
- `domain`

代表实现：

- `services/api/analysis_target_resolution_service.py`
- `services/api/chat_start_service.py`
- teacher workbench 中的显式目标选择

### 2.2 Artifact Adapter

artifact adapter 负责把不同来源输入归一化为 specialist 可消费的 artifact。

统一要求：

- 输入来源可以多样，但输出 artifact_type 必须稳定
- adapter 只做归一化与 provenance 保留，不直接输出老师结论
- adapter 必须显式给出 `confidence`、`missing_fields`、`provenance`

当前平台内建 artifact：

- `survey_evidence_bundle`
- `class_signal_bundle`
- `multimodal_submission_bundle`

manifest-driven 注册要求：

- domain 元数据应集中登记为 manifest，而不是散落在单个 wiring 文件中
- manifest 至少声明 `domain`、artifact adapter spec、strategy spec、specialist spec、rollout metadata、feature flags
- runtime 运行时注册可以继续绑定具体 runner / adapter，但元数据来源应优先来自 manifest registry
- manifest 还应声明最小 runtime binding 元信息，例如 `specialist_deps_factory`、`payload_constraint_key`、`teacher_context_constraint_key`；binding 值可为受控引用名，也可为运行时可解析的 callable，以减少中心 lookup 胶水
- specialist spec 应显式声明自身 runner binding；strategy selector 在装配阶段必须校验 `strategy -> specialist -> artifact` 的最小一致性，不允许静默 fallback
- manifest 还应声明 analysis report provider 装配元信息，使 report plane 不再依赖按 domain 手工硬编码 provider 表
- runtime / report 的命名 binding 应通过共享 binding registry 解析，避免在多个中心模块各自维护一份 lookup 真相
- domain specialist runtime 与 analysis report provider 都应优先通过统一 builder / registry 组装，而不是在单个 wiring 文件里为每个 domain 重复手写 glue

### 2.3 Strategy Selector

strategy selector 负责根据：

- `artifact_type`
- `task_kind`
- `role`
- `target_scope`
- `confidence`

选择：

- `strategy_id`
- `specialist_agent`
- `delivery_mode`
- `review_required`

当前代表策略：

- `survey.teacher.report`
- `survey.chat.followup`
- `class_signal.teacher.report`
- `video_homework.teacher.report`

## 3. Specialist Runtime

specialist runtime 负责治理 specialist 执行，不直接感知前台会话。

统一约束：

- 输入契约使用 `HandoffContract`
- 输出契约使用 `SpecialistAgentResult`
- specialist 只返回 `analysis_artifact`
- 不直接写长期 memory
- 不直接切换用户会话控制权

治理要求：

- budget 控制
- event sink / diag_log
- output schema 校验
- `invalid_output`、`timeout`、`specialist_execution_failed` 等可审计失败应优先 fail-closed，并按策略降级到 review queue 或 failed 状态
- 低置信度不直接展示给老师，而是走 review queue

specialist 的 `output_schema` 应优先使用 domain-specific typed artifact，例如 `survey.analysis_artifact`、`class_report.analysis_artifact`、`video_homework.analysis_artifact`，而不是长期停留在宽泛的 `analysis_artifact`。

当 specialist 输出不满足 typed schema 时，runtime 必须返回 `invalid_output`，而不是把不完整结果当作老师可读真相继续下游传播。

对于带 `teaching_recommendations` 的 typed artifact，仅仅“字段存在”并不足够；若建议列表为空，仍应视为 `invalid_output`，因为这类结果还不具备老师可用的最小交付质量。

对于更高风险域，可以在统一 runtime 内引入小型固定 job graph，例如 `analyze -> verify`。但这类 graph 必须是受控、有限、可审计的内部 orchestration，不应演进为自由 agent-to-agent 对话网。

当前 `video_homework` 域采用 fixed graph 试点：

- graph 必须显式声明 `graph_id`、`domain`、固定 `node_id` / `node_type`；
- 节点只允许受控类型：`extract` / `analyze` / `verify` / `merge`；
- 每个节点都必须带 budget cap，超限即视为 `budget_exceeded` 并终止整图；
- 任一节点出现 `invalid_output`、`timeout`、`specialist_execution_failed`，整图必须 fail-closed，由 orchestrator 统一降级到 review 或 failed；
- 该机制服务于高风险域提质，不表示平台支持开放式多 agent mesh。

## 4. Analysis Report Plane

analysis report plane 是老师侧统一读取面，不区分 survey / class_report / video_homework 的基础读取协议。

统一接口：

- `GET /teacher/analysis/reports`
- `GET /teacher/analysis/reports/{report_id}`
- `POST /teacher/analysis/reports/{report_id}/rerun`
- `GET /teacher/analysis/review-queue`
- `GET /teacher/analysis/metrics`

domain-specific facade 可存在，但应尽量只做轻量转发：

- `survey`
- `class_report`
- `video_homework`

这里的关键原则是统一 analysis report plane，而不是每个 domain 单独发明一套老师读取模型。

统一 report model 还应携带最小 lineage 字段，至少包括：

- `strategy_version`
- `prompt_version`
- `adapter_version`
- `runtime_version`

这样 report plane 不仅是统一读取面，也能成为统一审计与 replay 输入面。

当老师触发 rerun 时，统一返回体至少应携带 `previous_lineage` 与 `current_lineage`，以支持最小差异比较、回归核验与回滚判断。

## 5. Review Queue

review queue 是统一降级面，不是某个 domain 的私有补丁。

统一字段：

- `item_id`
- `domain`
- `report_id`
- `teacher_id`
- `target_type`
- `target_id`
- `status`
- `reason`
- `reason_code`
- `strategy_id`
- `confidence`
- `created_at`
- `updated_at`

统一规则：

- 当 artifact / specialist 置信度低于阈值时，进入 review queue
- review queue 项保留 domain / strategy_id / reason_code 信息，便于跨域筛选与 drift 分析
- review queue 不直接污染老师主界面和长期 memory
- reviewer 后续的 retry / reject / dismiss / resolve 结果应可导出为 feedback dataset，进入离线评测与质量治理闭环

## 6. Domain 映射

### 6.1 Survey

- domain: `survey`
- artifact: `survey_evidence_bundle`
- task_kind: `survey.analysis`
- specialist: `survey_analyst`
- primary target_scope: `class`

### 6.2 Class Report

- domain: `class_report`
- artifact: `class_signal_bundle`
- task_kind: `class_report.analysis`
- specialist: `class_signal_analyst`
- primary target_scope: `class`

### 6.3 Video Homework

- domain: `video_homework`
- artifact: `multimodal_submission_bundle`
- task_kind: `video_homework.analysis`
- specialist: `video_homework_analyst`
- primary target_scope: `student`

## 7. 扩展规则

新增能力时，优先按下面顺序扩：

1. 明确 target contract
2. 新增或复用 artifact adapter
3. 为 artifact + task_kind 加 strategy
4. 只有认知职责明显不同，才新增 specialist agent
5. 接入统一 analysis report plane 与 review queue
6. 补 fixture、离线 eval、rollout checklist

当 report 已写入 lineage 字段后，应能通过 replay harness 重建最小分析上下文，用于回归比较与排障。

## 8. 关联文档

- Survey 契约：`docs/reference/survey-analysis-contract.md`
- 多域 rollout checklist：`docs/operations/multi-domain-analysis-rollout-checklist.md`
- B/C 演进实施计划：`docs/plans/2026-03-07-agent-system-bc-evolution-implementation-plan.md`

## 9. Onboarding References

- Domain onboarding contract: `docs/reference/analysis-domain-onboarding-contract.md`
- Domain onboarding template: `docs/reference/analysis-domain-onboarding-template.md`
- Domain checklist: `docs/reference/analysis-domain-checklist.md`
- Capability matrix: `docs/reference/analysis-domain-capability-matrix.md`
- Extension plan template: `docs/plans/templates/analysis-domain-extension-template.md`
- Historical extension template: `docs/reference/analysis-domain-extension-template.md`

## 7. Reviewer Verify Contract

`video_homework.teacher.report` 现采用受控 `analyze -> verify` 图，但 `verify` 不再重复执行同一 analyst，而是固定走内部 `reviewer_analyst`：

- `analyze` 节点继续产出老师可见的 primary analysis artifact；
- `verify` 节点只读取上游结果，不直接改写老师可见 artifact；
- runtime 会把 `job_graph_previous_result`、`job_graph_results`、`job_graph_trace` 注入下游 handoff constraints；
- 若 `verify` 返回 reviewer critique（`approved` / `reason_codes` / `recommended_action` / `checked_sections`），graph result 必须把它放入 `review_metadata`，同时保留 primary artifact 作为 `final_result`；
- 若 reviewer 拒绝，orchestrator 必须 fail-closed 到 review queue；若 reviewer 通过，才允许交付 primary artifact。

reviewer critique 的最小 schema：

- `approved`: `bool`
- `critique_summary`: `str`
- `reason_codes`: `list[str]`
- `recommended_action`: `deliver | enqueue_review`
- `checked_sections`: `list[str]`

## 8. Strategy-Level Quality Gates

`/teacher/analysis/metrics` 现支持窗口化 specialist runtime 质量视图：

- 默认 `window_sec=3600`，即最近 1 小时滑窗；
- 支持 `group_by=strategy|agent`，用于输出 `specialist_quality_by_strategy` / `specialist_quality_by_agent`；
- strategy-level gate 用于避免某一策略质量劣化被全局平均掩盖；
- release-readiness 可按 `strategy_id` 读取对应分组阻断信号，而不是只看全局汇总。

## 9. Reviewer Critique V2

internal reviewer 现升级为 `reviewer_critique_v2` contract，在保留 `approved` / `reason_codes` / `recommended_action` / `checked_sections` 的同时，新增：

- `quality_score`：0.0 - 1.0 的结构化质量分；
- `issue_list`：逐条 issue，至少包含 `severity`、`section`、`detail`、`recommended_fix`、`reason_code`；
- reviewer 仍只作为内部 verify node，不直接替换 primary artifact；
- orchestrator 继续基于 reviewer metadata 决定 `deliver` 或 `enqueue_review`。

## 10. Review Feedback Closed Loop

review queue 不再只是人工兜底入口，也作为策略调优输入：

- `scripts/export_review_feedback_dataset.py` 负责把 review queue 样本归一化为 feedback dataset；
- dataset 除 `summary` / `drift_summary` 外，还应输出 `tuning_recommendations` 与 `feedback_loop_summary`；
- `scripts/build_review_drift_report.py` 用于快速查看 regression drift 与当前建议动作；
- `scripts/analysis_strategy_eval.py` 会消费 review feedback，并在评测报告里输出 `closed_loop_recommendations`；
- rollout 判断不仅看 fixture coverage，也要看是否仍存在高优先级 tuning recommendation。

## 8. Policy-Driven Gates And Feedback Rules

为避免每次调整发布门禁或 feedback 闭环规则都修改 Python 代码，统一 analysis plane 现在把以下可调项集中在 `config/analysis_policy.json`：

- `release_readiness.thresholds`：release-readiness 的 changed ratio、timeout/invalid/budget/fallback count/rate 与默认 `window_sec`；
- `review_feedback.*`：`reason_code -> action_type/default_priority/recommended_action/owner_hint` 映射，以及 recommendation priority 判定阈值；
- `strategy_eval.*`：各 domain 最低 fixture 数、required edge-case tags、评测闭环 recommendation 模板。

约束：

- 线上默认生效的是仓库内 `config/analysis_policy.json`；
- 离线评测或发布演练可通过脚本 `--policy-config <path>` 临时覆盖，但覆盖文件必须纳入变更记录；
- `build_analysis_release_readiness_report.py`、`build_review_drift_report.py`、`analysis_strategy_eval.py` 都应输出 policy 生效后的结果，而不是只反映代码默认值。
