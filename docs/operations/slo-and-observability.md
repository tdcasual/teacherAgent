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
