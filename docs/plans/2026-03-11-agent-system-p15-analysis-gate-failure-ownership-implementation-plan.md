# Agent System P15 Analysis Gate Failure Ownership Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 给 analysis policy / contract / eval / preflight failures增加统一分类、责任归属与修复建议摘要，便于 CI summary、发布审计和回滚复盘快速定位 owner。

**Architecture:** 不重写现有 gate 逻辑；新增一个轻量 ownership helper，把 blocking issue code 与高优先级 tuning recommendation 统一映射为 `owner_hint / owner_label / failure_type / recommended_action`。`check_analysis_preflight.py` 在保留原始 `blocking_issues` 的同时输出 `classified_blocking_issues` 与 `ownership_summary`，CI summary 只消费这些结构化字段。

**Tech Stack:** Python 3.13、pytest、现有 analysis quality scripts、docs/architecture/ownership-map.md。

---

### Task 1: Add failing ownership tests first

**Files:**
- Create: `tests/test_analysis_gate_ownership_service.py`
- Modify: `tests/test_analysis_preflight_gate.py`
- Modify: `tests/test_ci_backend_hardening_workflow.py`

**Step 1: Write the failing test**

新增测试要求：
- release-readiness 类失败会映射到 Runtime / Platform/API 等 owner；
- `strategy_eval_not_ready_for_expansion` 会映射到 Evaluation owner；
- invalid policy 会输出 `policy_validation_failed` 并归到 Platform/API；
- CI summary step 会读取 preflight artifact 中的 `ownership_summary` / `classified_blocking_issues`。

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m pytest -q tests/test_analysis_gate_ownership_service.py tests/test_analysis_preflight_gate.py tests/test_ci_backend_hardening_workflow.py`

Expected: FAIL。

---

### Task 2: Implement failure classification and ownership summary

**Files:**
- Create: `services/api/analysis_gate_ownership_service.py`
- Modify: `scripts/quality/check_analysis_preflight.py`
- Modify: `.github/workflows/ci.yml`

**Step 1: Write minimal implementation**

- 定义 blocking issue code -> owner/failure_type/default action 映射；
- 复用 review feedback recommendation 的 `owner_hint` 作为辅助 owner 线索；
- preflight 输出 `classified_blocking_issues` 与 `ownership_summary.by_owner` / `ownership_summary.top_actions`；
- CI summary 优先展示 owner 汇总和第一批修复建议。

**Step 2: Run test to verify it passes**

Run: `./.venv/bin/python -m pytest -q tests/test_analysis_gate_ownership_service.py tests/test_analysis_preflight_gate.py tests/test_ci_backend_hardening_workflow.py`

Expected: PASS。

---

### Task 3: Update docs and verify

**Files:**
- Modify: `docs/reference/analysis-runtime-contract.md`
- Modify: `docs/operations/change-management-and-governance.md`
- Modify: `docs/operations/slo-and-observability.md`

**Step 1: Update docs**

补充：
- `classified_blocking_issues` 与 `ownership_summary` 字段语义；
- 读 summary 时如何按 owner 分派修复；
- policy / contract / eval / runtime 各类失败的默认处理顺序。

**Step 2: Run focused verification**

Run: `./.venv/bin/python -m pytest -q tests/test_analysis_gate_ownership_service.py tests/test_analysis_preflight_gate.py tests/test_ci_backend_hardening_workflow.py tests/test_analysis_policy_service.py tests/test_analysis_policy_quality_gate.py`

Expected: PASS。

**Step 3: Run broader verification**

Run: `./.venv/bin/python -m pytest -q tests/test_analysis_policy_service.py tests/test_analysis_policy_quality_gate.py tests/test_analysis_release_readiness_report.py tests/test_review_feedback_service.py tests/test_review_drift_report.py tests/test_analysis_strategy_eval.py tests/test_analysis_shadow_compare_report.py tests/test_analysis_domain_contract_checker.py tests/test_analysis_preflight_gate.py tests/test_analysis_preflight_ci_fixtures.py tests/test_ci_backend_hardening_workflow.py tests/test_analysis_gate_ownership_service.py tests/test_docs_architecture_presence.py tests/test_architecture_doc_paths.py tests/test_reviewer_analyst.py tests/test_specialist_job_graph_runtime.py tests/test_strategy_selector.py tests/test_multimodal_orchestrator_service.py tests/test_specialist_metrics_service.py tests/test_analysis_metrics_service.py tests/test_analysis_report_routes.py tests/test_replay_analysis_run.py`

Expected: PASS。
