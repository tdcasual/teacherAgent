# SLO And Observability Baseline

Last updated: 2026-02-12

## Scope

This baseline covers API runtime operability for `services/api` and provides
auditable evidence for:

- SLO definitions
- runtime metrics endpoint contract
- dashboard configuration artifact

## SLO Definitions

All SLOs are measured on API requests excluding local development-only traffic.

1. `SLO-API-Availability`
   - Objective: HTTP success rate >= `99.0%` over rolling 30 days.
   - SLI: `1 - http_error_rate` where error means `status_code >= 500`.
2. `SLO-API-Latency-P95`
   - Objective: `p95 <= 1.0s` over rolling 30 days.
   - SLI: `http_latency_sec.p95` from `/ops/metrics`.
3. `SLO-API-Incident-Detection`
   - Objective: 5xx error rate breach is detectable within 5 minutes.
   - SLI source: `http_5xx_total` and `http_error_rate`.

## Runtime Metrics Contract

The API exposes two governance endpoints:

- `GET /ops/metrics`
  - Returns `{"ok": true, "metrics": ...}`.
  - Includes:
    - `http_requests_total`
    - `http_5xx_total`
    - `http_error_rate`
    - `http_latency_sec.p50/p95/p99`
    - `requests_by_route`
    - `errors_by_route`
    - `slo.latency_p95_ok`
    - `slo.error_rate_ok`
- `GET /ops/slo`
  - Returns current SLO status projection for availability and latency.
  - Includes quick-triage runtime fields:
    - `uptime_sec`
    - `inflight_requests`
    - `http_requests_total`
    - `http_error_rate`
    - `http_latency_p95_sec`

## Dashboard Evidence

Dashboard config is versioned at:

- `ops/dashboards/backend-slo-overview.json`

This artifact is intended to be imported into Grafana (JSON model) and includes
panels for request volume, error rate, latency p95, and SLO status.

对于统一 analysis runtime，还应补充 specialist 维度指标。当前 `/ops/metrics.metrics.analysis_runtime` 与 `GET /teacher/analysis/metrics` 暴露统一 snapshot：

- `schema_version`：当前为 `v1`，作为运维面稳定契约；
- `counters.run_count`：按 runtime `started` 事件统计真实执行尝试次数；
- `counters.fail_count`：按 runtime `failed` 事件统计失败次数；
- `counters.timeout_count`：统计 reason_code=`timeout` 的失败；
- `counters.invalid_output_count`：统计 reason_code=`invalid_output` 的失败；
- `counters.review_downgrade_count`：统计进入 review queue 的自动降级次数；
- `counters.rerun_count`：统计教师或运维触发的 rerun 请求次数；
- `by_phase`：包含 `prepared` / `started` / `completed` / `failed`，以及治理辅助阶段 `review_downgraded` / `rerun_requested`；
- `by_domain`：至少区分 `survey` / `class_report` / `video_homework`，缺失上下文统一落入 `unknown` bucket；
- `by_strategy`：可按 `strategy_id` 聚合，缺失上下文统一落入 `unknown` bucket；
- `by_agent`：可按 specialist `agent_id` 聚合，缺失上下文统一落入 `unknown` bucket；
- `by_reason`：至少记录 `timeout`、`budget_exceeded`、`invalid_output`、`specialist_execution_failed` 以及 review downgrade 的原因分布。
- runtime snapshot 应持久化到本地 metrics store，避免进程重启后丢失 analysis runtime 与 workflow routing 统计。
- `workflow_routing`：至少暴露 resolution / outcome counters，以及 `by_effective_skill`、`by_resolution_mode`、`by_outcome`。

## Operational Runbook Hooks

Alert thresholds (initial):

- Warning: `http_error_rate > 0.005` for 5 minutes.
- Critical: `http_error_rate > 0.01` for 5 minutes.
- Warning: `http_latency_sec.p95 > 1.0` for 10 minutes.

Review cadence:

- Weekly: inspect SLO burn and route-level hot spots.
- Monthly: revise SLO targets if product requirements change.

## 发布前门禁

所有 M/H 发布在进入生产前，都应补充以下可审计证据：

1. 运行 `scripts/quality/check_backend_quality_budget.py`，确认后端质量预算未超线；
2. 运行 `scripts/quality/check_complexity_budget.py`，确认复杂度预算未回退；
3. 检查 `/ops/metrics`，确认 `http_error_rate` 与 `http_latency_sec.p95` 无异常；
4. 检查 `/ops/slo`，确认当前 SLO 状态与发布预期一致。

## 回滚后核验

当发布后执行回滚时，必须再次读取 `/ops/metrics` 与 `/ops/slo`，并记录：

- 回滚后 5xx 错误率是否回落；
- 回滚后 P95 延迟是否恢复；
- 是否仍存在 inflight 请求堆积；
- 是否需要继续执行事件响应 runbook。

## Specialist Runtime Quality Gates

针对 unified analysis runtime，除通用错误率外，还应持续观察 specialist 质量门禁：

- `success_rate`：`completed_count / run_count`
- `timeout_rate`：`timeout_count / run_count`
- `invalid_output_rate`：`invalid_output_count / run_count`
- `budget_rejection_rate`：`budget_rejection_count / run_count`
- `fallback_rate`：`fallback_count / run_count`

初始发布阈值：

- `timeout_rate <= 0.05`
- `invalid_output_rate <= 0.05`
- `budget_rejection_rate <= 0.02`
- `fallback_rate <= 0.10`

观测入口：

- `/teacher/analysis/metrics` 返回原始 runtime snapshot 与派生 `specialist_quality`；
- `scripts/build_analysis_release_readiness_report.py` 会把 `specialist_quality` 作为发布阻断信号；
- 若 `specialist_quality.ready_for_release = false`，M/H 发布默认不得继续放量。

建议告警：

- Warning：任一 specialist rate 连续两个观测周期越线；
- Critical：`timeout_rate` 或 `fallback_rate` 连续越线且 review queue unresolved item 同时上升。

## Windowed And Grouped Specialist Quality

当前推荐的质量观测方式：

- 默认观察窗口：最近 `3600` 秒；
- 默认读取路径：`GET /teacher/analysis/metrics?window_sec=3600`；
- 按策略观测：`GET /teacher/analysis/metrics?window_sec=3600&group_by=strategy`；
- 按 agent 观测：`GET /teacher/analysis/metrics?window_sec=3600&group_by=agent`。

运维建议：

- 日常巡检优先看 1h 滑窗，发现异常后再扩大到更长窗口；
- 灰度/放量前优先看 `specialist_quality_by_strategy`，不要只看全局 `specialist_quality`；
- `video_homework.teacher.report` 这类高风险策略，默认必须通过 strategy-level gate 才允许继续放量。

## Closed-Loop Review Signals

建议的 P9 运行顺序：

- 先导出 review feedback dataset：`./.venv/bin/python scripts/export_review_feedback_dataset.py --input <review_queue.jsonl>`
- 再生成 drift + tuning 建议：`./.venv/bin/python scripts/build_review_drift_report.py --input <review_feedback.jsonl>`
- 最后在离线评测里消费 feedback：`./.venv/bin/python scripts/analysis_strategy_eval.py --fixtures tests/fixtures --review-feedback <dataset.json> --json --summary-only`

运维上需要重点观察：

- `feedback_loop_summary.high_priority_count`
- `tuning_recommendations` 是否持续集中在单一 `strategy_id`
- `invalid_output` / `missing_fields` / `low_confidence` 是否重复出现且未在后续评测中下降

## Policy File And Override Workflow

- 做正式放量前，推荐直接跑统一门禁：`./.venv/bin/python scripts/quality/check_analysis_preflight.py --fixtures tests/fixtures --review-feedback <dataset.jsonl> --metrics <metrics.json> --baseline-dir <baseline_dir> --candidate-dir <candidate_dir>`；

- 调整 policy 前先跑：`./.venv/bin/python scripts/quality/check_analysis_policy.py`；若只做预览可加 `--print-only`；
当前 analysis 质量门禁与反馈闭环规则默认来自 `config/analysis_policy.json`。建议操作方式：

- 查看全局默认策略：直接审阅 `config/analysis_policy.json`；
- 做灰度/预演时，用临时 policy 文件调用：
  - `./.venv/bin/python scripts/build_analysis_release_readiness_report.py ... --policy-config <policy.json>`
  - `./.venv/bin/python scripts/build_review_drift_report.py --input <dataset.json> --policy-config <policy.json>`
  - `./.venv/bin/python scripts/analysis_strategy_eval.py --fixtures tests/fixtures --review-feedback <dataset.json> --json --summary-only --policy-config <policy.json>`
- 若只调整阈值/推荐规则而不改 runtime 代码，仍应保留上述三类输出，证明 change 只改变 policy，不改变实现语义边界。

运维解释口径：

- `window_sec=3600` 只是默认 policy，不再视为硬编码契约；
- 若 strategy-level gate、feedback priority 或 required edge-case 发生变化，应首先检查对应 policy diff，而不是先怀疑 runtime 逻辑漂移。

主 CI 已执行统一 analysis preflight gate，因此本地预演失败通常意味着后续 PR 也会在 analysis rollout guardrails 阶段被阻断。

CI 会上传 `analysis-rollout-artifacts`，其中至少包含 `analysis-policy.json` 与 `analysis-preflight.json`；GitHub job summary 则提供快速结论摘要。
