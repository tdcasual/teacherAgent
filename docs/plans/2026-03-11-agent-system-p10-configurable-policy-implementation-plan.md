# Agent System P10 Configurable Policy Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 把 analysis plane 中当前硬编码的发布门禁阈值、review feedback 推荐规则与 strategy eval rollout 要求提炼为统一可配置 policy，避免后续每次调门限都改 Python 代码。

**Architecture:** 新增一个轻量 `analysis_policy_service` 从 `config/analysis_policy.json` 读取并补全默认值，继续保持现有 service/script 结构不变。`build_analysis_release_readiness_report.py`、`review_feedback_service.py`、`analysis_strategy_eval.py` 只改为消费 policy，并保留显式参数优先级，避免破坏现有调用方。

**Tech Stack:** Python 3.13、pytest、JSON config、现有 `services/api/*` 和 `scripts/*`。

---

### Task 1: Add a shared analysis policy config and loader

**Files:**
- Create: `config/analysis_policy.json`
- Create: `services/api/analysis_policy_service.py`
- Create: `tests/test_analysis_policy_service.py`

**Step 1: Write the failing test**

新增测试要求：
- loader 在未传自定义配置时返回默认 policy；
- loader 能从 JSON 文件读取并只覆盖指定字段；
- 缺失 section/key 时会自动补默认值，避免调用方做 defensive merge。

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m pytest -q tests/test_analysis_policy_service.py`

Expected: FAIL。

**Step 3: Write minimal implementation**

- 定义 policy 默认结构：
  - `release_readiness.thresholds`
  - `review_feedback.reason_recommendation_specs`
  - `review_feedback.priority_rules`
  - `strategy_eval.minimum_fixture_count_by_domain`
  - `strategy_eval.required_edge_case_tags`
  - `strategy_eval.closed_loop_recommendations`
- 提供 `load_analysis_policy()` / `load_analysis_policy_from_path()` / `merge_analysis_policy()`。

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python -m pytest -q tests/test_analysis_policy_service.py`

Expected: PASS。

---

### Task 2: Make release-readiness gates read thresholds from policy

**Files:**
- Modify: `scripts/build_analysis_release_readiness_report.py`
- Modify: `tests/test_analysis_release_readiness_report.py`

**Step 1: Write the failing test**

新增测试要求：
- 可通过 `policy` 覆盖 timeout / invalid / budget / fallback / window 阈值；
- CLI 支持 `--policy-config` 并将配置阈值写入输出 `thresholds`；
- 显式 CLI / 函数参数优先于 policy 默认值。

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m pytest -q tests/test_analysis_release_readiness_report.py`

Expected: FAIL。

**Step 3: Write minimal implementation**

- 新增 threshold resolve helper；
- CLI 增加 `--policy-config`；
- 输出中保留实际生效阈值，方便审计。

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python -m pytest -q tests/test_analysis_release_readiness_report.py`

Expected: PASS。

---

### Task 3: Make review feedback recommendation rules configurable

**Files:**
- Modify: `services/api/review_feedback_service.py`
- Modify: `scripts/build_review_drift_report.py`
- Modify: `tests/test_review_feedback_service.py`
- Modify: `tests/test_review_drift_report.py`

**Step 1: Write the failing test**

新增测试要求：
- policy 可覆盖 `reason_code -> action_type/default_priority/recommended_action/owner_hint`；
- policy 可调整 priority 判定阈值；
- drift report CLI 支持 `--policy-config` 并输出配置后的 recommendations。

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m pytest -q tests/test_review_feedback_service.py tests/test_review_drift_report.py`

Expected: FAIL。

**Step 3: Write minimal implementation**

- 把静态 spec 常量迁移为 default policy；
- recommendation builder 接受 `policy`；
- priority 规则从 policy 读取并保留 unknown reason fallback。

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python -m pytest -q tests/test_review_feedback_service.py tests/test_review_drift_report.py`

Expected: PASS。

---

### Task 4: Make strategy eval rollout requirements configurable

**Files:**
- Modify: `scripts/analysis_strategy_eval.py`
- Modify: `tests/test_analysis_strategy_eval.py`

**Step 1: Write the failing test**

新增测试要求：
- policy 可覆盖每个 domain 的最低 fixture 数；
- policy 可覆盖 required edge-case tags；
- policy 可覆盖 closed-loop recommendation 文案/优先级；
- CLI 支持 `--policy-config`。

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m pytest -q tests/test_analysis_strategy_eval.py`

Expected: FAIL。

**Step 3: Write minimal implementation**

- `evaluate_fixture_tree()` 接受 `policy`；
- rollout/closed-loop helper 从 policy 读取 requirement；
- CLI 加 `--policy-config` 并把 policy 生效结果纳入输出。

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python -m pytest -q tests/test_analysis_strategy_eval.py`

Expected: PASS。

---

### Task 5: Update docs and run focused regression

**Files:**
- Modify: `docs/reference/analysis-runtime-contract.md`
- Modify: `docs/operations/slo-and-observability.md`
- Modify: `docs/operations/change-management-and-governance.md`
- Reference: `config/analysis_policy.json`

**Step 1: Update docs**

补充：
- analysis policy 文件位置与作用域；
- 哪些阈值/推荐规则已配置化；
- 变更 policy 后需要运行的脚本与门禁命令。

**Step 2: Run focused regression**

Run: `./.venv/bin/python -m pytest -q tests/test_analysis_policy_service.py tests/test_analysis_release_readiness_report.py tests/test_review_feedback_service.py tests/test_review_drift_report.py tests/test_analysis_strategy_eval.py`

Expected: PASS。

**Step 3: Run broader regression**

Run: `./.venv/bin/python -m pytest -q tests/test_reviewer_analyst.py tests/test_specialist_job_graph_runtime.py tests/test_strategy_selector.py tests/test_multimodal_orchestrator_service.py tests/test_specialist_metrics_service.py tests/test_analysis_metrics_service.py tests/test_analysis_release_readiness_report.py tests/test_analysis_report_routes.py tests/test_review_feedback_service.py tests/test_review_drift_report.py tests/test_analysis_strategy_eval.py tests/test_replay_analysis_run.py`

Expected: PASS。
