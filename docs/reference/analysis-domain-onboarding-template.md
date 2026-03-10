# Analysis Domain Onboarding Template

用于新增新的 analysis domain，并把隐性经验转成可执行工程模板。

## 1. Domain 定义

在开始实现前，先明确以下真相源：

- `domain_id`
- 用户面向的 `display_name`
- 主要 `target_type` / `target_scope`
- 统一 plane 上的 `analysis_type`
- 是否需要 shadow / beta / review-only 阶段

推荐先在 `services/api/domains/manifest_registry.py` 设计 manifest，再去写具体 runner。

## 2. Manifest 模板

manifest 必须覆盖以下字段：

- domain 基本信息：`domain_id`、`display_name`、`rollout_stage`
- artifact adapter 声明：输入来源、稳定 `artifact_type`、schema version
- strategy 声明：`strategy_id`、`delivery_mode`、`review_policy`、budget、typed return schema
- specialist 声明：`agent_id`、`task_kinds`、`output_schema`、evaluation suite
- runtime binding：`specialist_deps_factory`、payload constraint key、teacher context key
- report binding：report provider factory，确保统一挂入 analysis report plane
- feature flags：域级开关、资源限制、review-only/disabled 策略相关配置

## 3. Artifact 与 Strategy

每个新域都应先定义 artifact，再定义 strategy：

- artifact 必须稳定暴露 `confidence`、`missing_fields`、`provenance`
- strategy 必须明确 `strategy_id`、`strategy_version`、`review_required` 的触发条件
- strategy selector 必须能根据 role / task_kind / artifact_type 做出稳定选择
- replay / compare 需要能从 report detail 中取回 artifact payload、lineage、analysis artifact

## 4. Specialist 与 Controlled Orchestration

specialist runner 必须遵守统一 runtime 约束：

- 只接受 `HandoffContract`
- 只返回 typed `analysis_artifact`
- 不直接 takeover 老师会话
- 不直接写长期 memory
- 必须受 budget / timeout / schema validation / event sink 约束

如果域风险较高，可采用 controlled orchestration，例如固定 `extract -> analyze -> verify -> merge` 图；不要引入自由 agent mesh。

## 5. Report Plane 与 Review Queue

新域必须统一接入 analysis report plane：

- `GET /teacher/analysis/reports`
- `GET /teacher/analysis/reports/{report_id}`
- `POST /teacher/analysis/reports/{report_id}/rerun`
- `GET /teacher/analysis/review-queue`
- `GET /teacher/analysis/metrics`

review queue 至少应保留：

- `domain`
- `strategy_id`
- `reason`
- `reason_code`
- `disposition`
- `operator_note`

## 6. Fixtures、Eval 与 Observability

新增 domain 时必须同步补齐：

- fixtures：happy path、low confidence、missing fields、provider noise、资源边界
- offline eval：`scripts/analysis_strategy_eval.py` 可纳入该域
- replay/compare：`scripts/replay_analysis_run.py` 与 `scripts/compare_analysis_runs.py` 可读取该域 report
- capability matrix：`docs/reference/analysis-domain-capability-matrix.md` 可快速核对已有 domain 的 rollout 阶段与平台能力面
- observability：`/ops/metrics.metrics.analysis_runtime` 和 `GET /teacher/analysis/metrics` 中能看到该域指标
- review feedback：可导出 feedback dataset，并按 `domain / strategy_id / reason_code` 分析 drift

## 7. Rollout Flags 与文档

- 可执行 contract check：`./.venv/bin/python scripts/check_analysis_domain_contract.py --json`
- CI 必须执行 `scripts/check_analysis_domain_contract.py --json`，确保 manifest / binding / docs / replay-compare 能力没有漂移。
上线前至少补齐：

- feature flags
- rollout checklist
- analysis runtime contract 引用
- docs index 导航
- release notes / go-live summary（如进入 beta 或 release）

建议 PR 描述直接引用 `docs/reference/analysis-domain-checklist.md` 逐项验收。
