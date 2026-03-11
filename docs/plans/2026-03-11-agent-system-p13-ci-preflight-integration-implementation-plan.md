# Agent System P13 CI Preflight Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 把 `analysis policy gate` 与统一 `analysis preflight gate` 接入主 CI 流水线，使其成为真实的持续门禁，而不是仅供本地手工执行的脚本。

**Architecture:** 保持现有 `.github/workflows/ci.yml` 的 `Run analysis rollout guardrails` 阶段，只在该阶段前置 `check_analysis_policy.py` 并追加 `check_analysis_preflight.py`。为避免在 CI 中动态拼装输入，新增一组稳定的仓库内 preflight fixture（metrics、review_feedback、baseline/candidate reports），让 gate 可直接运行且输出可审计。

**Tech Stack:** GitHub Actions、Python 3.13、pytest、现有 analysis quality scripts。

---

### Task 1: Add failing CI and fixture tests

**Files:**
- Modify: `tests/test_ci_backend_hardening_workflow.py`
- Create: `tests/test_analysis_preflight_ci_fixtures.py`

**Step 1: Write the failing test**

新增测试要求：
- CI workflow 必须执行 `scripts/quality/check_analysis_policy.py`；
- CI workflow 必须执行 `scripts/quality/check_analysis_preflight.py`，并传入仓库内 fixture 路径；
- 仓库内 preflight fixture 文件齐全且可被脚本消费。

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m pytest -q tests/test_ci_backend_hardening_workflow.py tests/test_analysis_preflight_ci_fixtures.py`

Expected: FAIL。

---

### Task 2: Add stable CI fixture bundle for analysis preflight

**Files:**
- Create: `tests/fixtures/analysis_preflight/metrics.json`
- Create: `tests/fixtures/analysis_preflight/review_feedback.jsonl`
- Create: `tests/fixtures/analysis_preflight/baseline/report_1.json`
- Create: `tests/fixtures/analysis_preflight/candidate/report_1.json`

**Step 1: Write minimal fixture content**

- metrics 使用最小 passing snapshot；
- review feedback 保持空数据或无阻断数据；
- baseline/candidate 使用 shadow compare 的稳定 passing 报告对。

**Step 2: Verify fixtures are consumable**

Run: `./.venv/bin/python scripts/quality/check_analysis_preflight.py --fixtures tests/fixtures --review-feedback tests/fixtures/analysis_preflight/review_feedback.jsonl --metrics tests/fixtures/analysis_preflight/metrics.json --baseline-dir tests/fixtures/analysis_preflight/baseline --candidate-dir tests/fixtures/analysis_preflight/candidate`

Expected: PASS。

---

### Task 3: Wire the new gates into CI and docs

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `docs/operations/change-management-and-governance.md`
- Modify: `docs/operations/slo-and-observability.md`

**Step 1: Implement minimal workflow change**

- 在 analysis rollout guardrails 阶段加入 `scripts/quality/check_analysis_policy.py`；
- 随后运行 `scripts/quality/check_analysis_preflight.py` 并传入静态 fixture 路径；
- 保留已有 contract checker / strategy eval / pytest guardrails，避免替换式改造。

**Step 2: Run tests to verify it passes**

Run: `./.venv/bin/python -m pytest -q tests/test_ci_backend_hardening_workflow.py tests/test_analysis_preflight_ci_fixtures.py tests/test_analysis_preflight_gate.py`

Expected: PASS。

---

### Task 4: Final verification

**Files:**
- Reference: `.github/workflows/ci.yml`
- Reference: `scripts/quality/check_analysis_policy.py`
- Reference: `scripts/quality/check_analysis_preflight.py`

**Step 1: Run focused verification**

Run: `./.venv/bin/python -m pytest -q tests/test_ci_backend_hardening_workflow.py tests/test_analysis_preflight_ci_fixtures.py tests/test_analysis_preflight_gate.py tests/test_analysis_policy_service.py tests/test_analysis_policy_quality_gate.py tests/test_analysis_release_readiness_report.py tests/test_review_feedback_service.py tests/test_review_drift_report.py tests/test_analysis_strategy_eval.py tests/test_analysis_shadow_compare_report.py tests/test_analysis_domain_contract_checker.py`

Expected: PASS。

**Step 2: Run broader verification**

Run: `./.venv/bin/python -m pytest -q tests/test_reviewer_analyst.py tests/test_specialist_job_graph_runtime.py tests/test_strategy_selector.py tests/test_multimodal_orchestrator_service.py tests/test_specialist_metrics_service.py tests/test_analysis_metrics_service.py tests/test_analysis_release_readiness_report.py tests/test_analysis_report_routes.py tests/test_review_feedback_service.py tests/test_review_drift_report.py tests/test_analysis_strategy_eval.py tests/test_replay_analysis_run.py tests/test_analysis_policy_service.py tests/test_analysis_policy_quality_gate.py tests/test_analysis_shadow_compare_report.py tests/test_analysis_domain_contract_checker.py tests/test_analysis_preflight_gate.py tests/test_ci_backend_hardening_workflow.py tests/test_analysis_preflight_ci_fixtures.py`

Expected: PASS。
