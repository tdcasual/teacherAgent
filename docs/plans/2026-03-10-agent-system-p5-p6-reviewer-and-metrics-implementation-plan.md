# Agent System P5 P6 Reviewer And Metrics Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在现有统一 analysis plane 上，为高风险视频作业策略补内部 reviewer specialist，并把 specialist runtime 事件提升为可门禁的质量指标与 release-readiness 信号。

**Architecture:** 不重做现有 domain/runtime/report 结构。P5 复用当前 `video_homework` controlled job graph，把 `verify` 从“再次跑同一 analyst”升级为“读取上游输出的 reviewer specialist”；P6 复用现有 `AnalysisMetricsService` 事件汇总，在其上补 `specialist_metrics_service` 派生速率、budget/fallback 计数和 release-readiness gate。继续保持 `Coordinator` 是唯一前台 agent，reviewer 只作为内部节点存在。

**Tech Stack:** Python 3.13、pytest、FastAPI、现有 `services/api/specialist_agents/*`、`services/api/analysis_metrics_service.py`、`scripts/build_analysis_release_readiness_report.py`、`docs/reference/analysis-runtime-contract.md`、`docs/operations/slo-and-observability.md`。

---

### Task 1: Add reviewer specialist for high-risk video homework strategy

**Files:**
- Create: `services/api/specialist_agents/reviewer_analyst.py`
- Modify: `services/api/specialist_agents/output_schemas.py`
- Modify: `services/api/specialist_agents/job_graph_models.py`
- Modify: `services/api/specialist_agents/job_graph_runtime.py`
- Modify: `services/api/strategies/contracts.py`
- Modify: `services/api/strategies/selector.py`
- Modify: `services/api/domains/manifest_registry.py`
- Modify: `services/api/domains/binding_registry.py`
- Modify: `services/api/multimodal_orchestrator_service.py`
- Create: `tests/test_reviewer_analyst.py`
- Modify: `tests/test_specialist_job_graph_runtime.py`
- Modify: `tests/test_strategy_selector.py`
- Modify: `tests/test_multimodal_orchestrator_service.py`
- Modify: `docs/reference/analysis-runtime-contract.md`

**Step 1: Write the failing tests**

新增测试要求：
- reviewer specialist 能读取上游 analyst 输出并给出 `approved` / `reason_codes` / `recommended_action`；
- job graph runtime 会把上游结果注入后续节点约束；
- `video_homework.teacher.report` 这种高风险策略会带 reviewer agent；
- multimodal orchestrator 在 reviewer 否决时进入 review queue，在 reviewer 通过时仍交付 primary analysis artifact。

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m pytest -q tests/test_reviewer_analyst.py tests/test_specialist_job_graph_runtime.py tests/test_strategy_selector.py tests/test_multimodal_orchestrator_service.py`

Expected: FAIL。

**Step 3: Write minimal implementation**

- reviewer specialist 先采用规则型 critique，不新增自由 agent 协商；
- job graph runtime 为后续节点注入 `job_graph_previous_result` / `job_graph_results`；
- graph result 增加 `review_metadata`，使 verifier 不污染最终老师可见 artifact；
- selector / manifest 只为指定视频作业策略开启 reviewer agent；
- multimodal orchestrator 的 `verify` 节点改为 reviewer，review 失败则 fail-closed 到 review queue。

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python -m pytest -q tests/test_reviewer_analyst.py tests/test_specialist_job_graph_runtime.py tests/test_strategy_selector.py tests/test_multimodal_orchestrator_service.py`

Expected: PASS。

---

### Task 2: Promote specialist runtime quality signals into release gates

**Files:**
- Create: `services/api/specialist_agents/metrics_service.py`
- Modify: `services/api/analysis_metrics_service.py`
- Modify: `services/api/specialist_agents/governor.py`
- Modify: `services/api/routes/analysis_report_routes.py`
- Modify: `scripts/build_analysis_release_readiness_report.py`
- Create: `tests/test_specialist_metrics_service.py`
- Modify: `tests/test_analysis_metrics_service.py`
- Modify: `tests/test_analysis_release_readiness_report.py`
- Modify: `tests/test_analysis_report_routes.py`
- Modify: `docs/operations/slo-and-observability.md`
- Modify: `docs/operations/change-management-and-governance.md`

**Step 1: Write the failing tests**

新增测试要求：
- specialist metrics service 能输出 `success_rate`、`timeout_rate`、`invalid_output_rate`、`budget_rejection_rate`、`fallback_rate`；
- governor/metrics 能稳定记录 `budget_exceeded`、`specialist_execution_failed` 对应的 budget/fallback 计数；
- `/teacher/analysis/metrics` 返回派生的 `specialist_quality`；
- release-readiness 在 specialist invalid/timeout/budget/fallback 超阈值时阻断发布。

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m pytest -q tests/test_specialist_metrics_service.py tests/test_analysis_metrics_service.py tests/test_analysis_release_readiness_report.py tests/test_analysis_report_routes.py`

Expected: FAIL。

**Step 3: Write minimal implementation**

- 在 `AnalysisMetricsService` 中补 `budget_rejection_count`、`fallback_count` 计数；
- 新建 `specialist_metrics_service.py`，从 metrics snapshot 派生质量速率与 gate summary；
- `/teacher/analysis/metrics` 附带 `specialist_quality`；
- release-readiness 支持 `specialist_quality` 输入与阈值阻断；
- 在 `slo-and-observability.md` 写清阈值、告警建议与 go/no-go 使用方式。

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python -m pytest -q tests/test_specialist_metrics_service.py tests/test_analysis_metrics_service.py tests/test_analysis_release_readiness_report.py tests/test_analysis_report_routes.py`

Expected: PASS。

---

### Task 3: Final regression

**Files:**
- Reference: `services/api/specialist_agents/reviewer_analyst.py`
- Reference: `services/api/specialist_agents/metrics_service.py`
- Reference: `scripts/build_analysis_release_readiness_report.py`

**Step 1: Run backend regression**

Run: `./.venv/bin/python -m pytest -q tests/test_reviewer_analyst.py tests/test_specialist_job_graph_runtime.py tests/test_strategy_selector.py tests/test_multimodal_orchestrator_service.py tests/test_specialist_metrics_service.py tests/test_analysis_metrics_service.py tests/test_analysis_release_readiness_report.py tests/test_analysis_report_routes.py tests/test_review_feedback_service.py tests/test_replay_analysis_run.py`

Expected: PASS。

**Step 2: Run script self-check**

Run: `./.venv/bin/python scripts/build_analysis_release_readiness_report.py --help`

Expected: exit 0。

**Step 3: Run diff guard**

Run: `git diff --check`

Expected: PASS。
