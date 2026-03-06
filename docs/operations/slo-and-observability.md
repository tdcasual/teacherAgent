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
