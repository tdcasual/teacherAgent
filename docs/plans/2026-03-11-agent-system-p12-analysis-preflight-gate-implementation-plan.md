# Agent System P12 Analysis Preflight Gate Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 新增统一 analysis 预发布 gate，把 policy 校验、domain contract check、review drift、strategy eval、shadow compare 与 release-readiness 聚合成一个可审计、可阻断的离线命令。

**Architecture:** 新建 `scripts/quality/check_analysis_preflight.py`，直接复用已有 `check_analysis_domain_contract`、`build_analysis_shadow_compare_report`、`build_review_feedback_dataset`、`evaluate_fixture_tree`、`build_analysis_release_readiness_report`，避免重复实现检查逻辑。脚本只负责装配输入、生成 combined report、统一退出码和 blocking issue 汇总。

**Tech Stack:** Python 3.13、pytest、现有 analysis scripts、JSON artifacts。

---

### Task 1: Add preflight gate tests first

**Files:**
- Create: `tests/test_analysis_preflight_gate.py`

**Step 1: Write the failing test**

新增测试要求：
- 给定有效 policy、metrics、review feedback、shadow compare 输入时，preflight gate 输出 `ok=true`；
- 当 release-readiness 被阻断或 strategy eval 未 ready 时，preflight gate 返回非零并输出明确 blocking issues；
- CLI 支持 `--policy-config`、`--fixtures`、`--review-feedback`、`--metrics`、`--baseline-dir`、`--candidate-dir`。

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m pytest -q tests/test_analysis_preflight_gate.py`

Expected: FAIL。

---

### Task 2: Implement unified preflight gate

**Files:**
- Create: `scripts/quality/check_analysis_preflight.py`
- Modify: `scripts/build_review_drift_report.py` (only if tiny helper extraction is useful)

**Step 1: Write minimal implementation**

- 读取并校验 policy；
- 运行 contract check；
- 从 review feedback 输入构建 drift dataset；
- 跑 strategy eval；
- 跑 shadow compare；
- 用以上结果生成 release-readiness；
- 汇总 `ok`、`blocking_issues`、`warnings` 与子报告摘要。

**Step 2: Run test to verify it passes**

Run: `./.venv/bin/python -m pytest -q tests/test_analysis_preflight_gate.py`

Expected: PASS。

---

### Task 3: Document and verify end to end

**Files:**
- Modify: `docs/operations/change-management-and-governance.md`
- Modify: `docs/operations/slo-and-observability.md`
- Modify: `docs/operations/multi-domain-analysis-rollout-checklist.md`
- Modify: `docs/reference/analysis-runtime-contract.md`

**Step 1: Update docs**

补充：
- 一键 preflight gate 命令；
- 与单脚本检查的关系；
- 失败后优先修哪一层（policy / contract / drift / eval / release-readiness）。

**Step 2: Run focused verification**

Run: `./.venv/bin/python -m pytest -q tests/test_analysis_preflight_gate.py tests/test_analysis_policy_service.py tests/test_analysis_policy_quality_gate.py tests/test_analysis_release_readiness_report.py tests/test_review_feedback_service.py tests/test_review_drift_report.py tests/test_analysis_strategy_eval.py tests/test_analysis_shadow_compare_report.py tests/test_analysis_domain_contract_checker.py`

Expected: PASS。

**Step 3: Run broader verification**

Run: `./.venv/bin/python -m pytest -q tests/test_reviewer_analyst.py tests/test_specialist_job_graph_runtime.py tests/test_strategy_selector.py tests/test_multimodal_orchestrator_service.py tests/test_specialist_metrics_service.py tests/test_analysis_metrics_service.py tests/test_analysis_release_readiness_report.py tests/test_analysis_report_routes.py tests/test_review_feedback_service.py tests/test_review_drift_report.py tests/test_analysis_strategy_eval.py tests/test_replay_analysis_run.py tests/test_analysis_policy_service.py tests/test_analysis_policy_quality_gate.py tests/test_analysis_shadow_compare_report.py tests/test_analysis_domain_contract_checker.py tests/test_analysis_preflight_gate.py`

Expected: PASS。
