# Agent System P14 CI Analysis Artifacts Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让 analysis CI 门禁不仅阻断，还能稳定产出可审计的 JSON artifact 与 GitHub job summary，便于发布审计、回滚复盘和跨人协作查看。

**Architecture:** 不改变现有 `check_analysis_policy.py` / `check_analysis_preflight.py` 的门禁语义，只补充结构化输出能力和 CI 编排。`check_analysis_policy.py` 增加 `--output`；`.github/workflows/ci.yml` 在 analysis rollout 阶段把 policy/preflight JSON 写入固定目录、生成 `GITHUB_STEP_SUMMARY` 摘要，并通过 `actions/upload-artifact` 上传。

**Tech Stack:** Python 3.13、GitHub Actions、pytest、现有 analysis quality scripts。

---

### Task 1: Add failing tests for artifact and summary wiring

**Files:**
- Modify: `tests/test_analysis_policy_quality_gate.py`
- Modify: `tests/test_ci_backend_hardening_workflow.py`

**Step 1: Write the failing test**

新增测试要求：
- `check_analysis_policy.py --output <path>` 会写出 JSON report；
- CI workflow 会把 analysis policy / preflight JSON 写入固定 artifact 目录；
- CI workflow 会使用 `actions/upload-artifact` 上传该目录；
- CI workflow 会向 `GITHUB_STEP_SUMMARY` 写 analysis gate 摘要。

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m pytest -q tests/test_analysis_policy_quality_gate.py tests/test_ci_backend_hardening_workflow.py`

Expected: FAIL。

---

### Task 2: Implement structured artifact output and CI summary

**Files:**
- Modify: `scripts/quality/check_analysis_policy.py`
- Modify: `.github/workflows/ci.yml`

**Step 1: Write minimal implementation**

- `check_analysis_policy.py` 支持 `--output`；
- CI 创建 `analysis-artifacts/` 目录；
- policy / preflight gate 分别写 JSON 到该目录；
- 新增 `always()` summary step，从 JSON 中提取关键字段写入 `GITHUB_STEP_SUMMARY`；
- 新增 `always()` artifact upload step 上传 `analysis-artifacts/`。

**Step 2: Run test to verify it passes**

Run: `./.venv/bin/python -m pytest -q tests/test_analysis_policy_quality_gate.py tests/test_ci_backend_hardening_workflow.py`

Expected: PASS。

---

### Task 3: Update docs and verify

**Files:**
- Modify: `docs/operations/change-management-and-governance.md`
- Modify: `docs/operations/slo-and-observability.md`

**Step 1: Update docs**

补充：
- CI artifact 名称和用途；
- GitHub summary 中应关注哪些字段；
- 发布复盘时优先读取哪份 JSON。

**Step 2: Run focused verification**

Run: `./.venv/bin/python -m pytest -q tests/test_analysis_policy_quality_gate.py tests/test_ci_backend_hardening_workflow.py tests/test_analysis_preflight_gate.py tests/test_analysis_preflight_ci_fixtures.py`

Expected: PASS。

**Step 3: Run broader verification**

Run: `./.venv/bin/python -m pytest -q tests/test_analysis_policy_service.py tests/test_analysis_policy_quality_gate.py tests/test_analysis_release_readiness_report.py tests/test_review_feedback_service.py tests/test_review_drift_report.py tests/test_analysis_strategy_eval.py tests/test_analysis_shadow_compare_report.py tests/test_analysis_domain_contract_checker.py tests/test_analysis_preflight_gate.py tests/test_analysis_preflight_ci_fixtures.py tests/test_ci_backend_hardening_workflow.py tests/test_docs_architecture_presence.py tests/test_architecture_doc_paths.py tests/test_reviewer_analyst.py tests/test_specialist_job_graph_runtime.py tests/test_strategy_selector.py tests/test_multimodal_orchestrator_service.py tests/test_specialist_metrics_service.py tests/test_analysis_metrics_service.py tests/test_analysis_report_routes.py tests/test_replay_analysis_run.py`

Expected: PASS。
