# Maintainability And Architecture Refactor Report (2026-02-12)

## Scope

This report summarizes closure status for the two governance concerns raised on
2026-02-12:

1. operability/runtime governance (`可观测性/运行治理`)
2. technical-debt control (`技术债控制`)

## Metric Snapshot

- app_core lines: baseline `1374`, current `696`, delta `-678` (`-49.3%`)
- teacher App.tsx lines: current `730` (target `< 800`)
- student App.tsx lines: baseline `1767`, current `1128`, delta `-639` (`-36.2%`)
- student chunk size (main): baseline `686.08 kB`, current `46.78 kB`, delta `-639.30 kB`
- student chunk size (largest emitted js): current `265.16 kB` (`katex-vendor-Bo7mie23.js`)
- app_core import fan-out: `top_level_imports=150` (budget `<=150`), `relative_modules=90` (budget `<=90`)

## Target Check

| Target | Result | Status |
| --- | --- | --- |
| `app_core.py` reduce by >=35% | `1374 -> 696` | Met |
| `frontend/apps/student/src/App.tsx` reduce to `< 1200` | `1128` | Met |
| `frontend/apps/teacher/src/App.tsx` reduce to `< 800` | `730` | Met |
| student main chunk `< 550 kB` | `46.78 kB` | Met |
| route module size budget `< 140` | max route module `79` lines | Met |
| app_core import fan-out budgets | `150/90` at enforced limits | Met |

## Operability Governance Evidence

- Runtime metrics store added at `services/api/observability.py`.
- Request middleware in `services/api/app.py` now records:
  - request volume (`http_requests_total`)
  - 5xx volume/error rate (`http_5xx_total`, `http_error_rate`)
  - latency histogram and percentiles (`http_latency_sec`)
  - in-flight requests (`inflight_requests`)
- New governance endpoints:
  - `GET /ops/metrics`
  - `GET /ops/slo` (now includes `uptime_sec` and `inflight_requests` for quick operations triage)
- SLO baseline and dashboard artifacts are versioned:
  - `docs/operations/slo-and-observability.md`
  - `ops/dashboards/backend-slo-overview.json`

## Debt-Control Guardrails

- Added/updated CI-enforced tests:
  - `tests/test_tech_debt_targets.py`
  - `tests/test_app_core_structure.py`
  - `tests/test_app_core_import_fanout.py`
  - `tests/test_assignment_wiring_structure.py`
  - `tests/test_chat_wiring_structure.py`
  - `tests/test_exam_wiring_structure.py`
  - `tests/test_misc_wiring_structure.py`
  - `tests/test_teacher_student_wiring_structure.py`
  - `tests/test_worker_skill_wiring_structure.py`
  - `tests/test_teacher_frontend_structure.py`
  - `tests/test_observability_store.py`
  - `tests/test_ops_endpoints.py`
  - `tests/test_operability_evidence.py`
- CI workflow now has `Run maintainability guardrails` step in `.github/workflows/ci.yml`.

## Final Verification Commands

- `python3 -m pytest -q tests/test_ops_endpoints.py`
- `python3 -m pytest -q tests/test_observability_store.py tests/test_operability_evidence.py tests/test_tech_debt_targets.py`
- `python3 -m pytest -q tests/test_app_core_import_fanout.py tests/test_app_core_structure.py`

## Residual Risk And Next Tightening

1. `app_core` fan-out is exactly at budget limits (`150/90`), so the next change set should target headroom (`<140/<80`) to avoid brittle CI failures.
2. `chat_wiring.py` and `worker_wiring.py` still contain the largest private coupling pockets; they are the best next debt-paydown targets.
3. `/ops/*` endpoints are currently auth-protected when `AUTH_REQUIRED=1`; if external scraping is needed later, introduce a dedicated service-role token policy instead of opening them anonymously.
