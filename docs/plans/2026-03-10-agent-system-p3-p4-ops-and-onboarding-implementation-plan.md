# Agent System P3 P4 Ops And Onboarding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在现有统一 analysis plane 基础上，补齐 teacher workbench 的跨域运营面板与安全批量重跑能力，并把 domain onboarding 升级为更明确的契约与可复用计划模板。

**Architecture:** 不新造独立控制台，也不重做路由体系；后端在统一 analysis report route 上补 ops summary 与 bulk rerun，前端在现有 `AnalysisReportSection` 中挂一个轻量 `AnalysisOpsSection` 子组件。文档面不推翻已经存在的 onboarding template/checklist，而是在其之上补 canonical onboarding contract 与 plan template，并把它们接入 runtime contract 与 docs index。

**Tech Stack:** Python 3.13、FastAPI、Pydantic v2、pytest、React 19、Vitest、现有 `services/api/analysis_report_service.py`、`services/api/routes/analysis_report_routes.py`、teacher workbench analysis section、`docs/reference` 与 `docs/plans/templates`。

---

### Task 1: Add analysis ops summary and bulk rerun API

**Files:**
- Modify: `services/api/api_models.py`
- Modify: `services/api/analysis_report_service.py`
- Modify: `services/api/routes/analysis_report_routes.py`
- Create: `tests/test_analysis_report_ops_routes.py`
- Modify: `tests/test_analysis_report_service.py`

**Step 1: Write the failing tests**

新增测试要求：
- `GET /teacher/analysis/reports` 返回 `summary`，至少包含 `total_reports`、`review_required_reports`、`status_counts`、`domains[]`；
- `POST /teacher/analysis/reports/bulk-rerun` 支持按 `report_ids[]` 安全批量重跑；
- 批量重跑返回 `requested_count`、`accepted_count`、`items[]`，并限制空列表/超限输入。

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m pytest -q tests/test_analysis_report_ops_routes.py tests/test_analysis_report_service.py`

Expected: FAIL。

**Step 3: Write minimal implementation**

- 在 `list_analysis_reports()` 中基于当前 items + queued review queue 生成结构化 `summary`；
- 新增 bulk rerun request model，要求非空 `report_ids` 且限制最大批量；
- 复用现有 `rerun_analysis_report()`，按显式 `report_ids` 批量执行，避免隐式全量操作；
- 在 route 中暴露 `/teacher/analysis/reports/bulk-rerun`。

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python -m pytest -q tests/test_analysis_report_ops_routes.py tests/test_analysis_report_service.py tests/test_analysis_report_routes.py`

Expected: PASS。

---

### Task 2: Add workbench analysis ops surface

**Files:**
- Modify: `frontend/apps/teacher/src/features/workbench/hooks/useAnalysisReports.ts`
- Modify: `frontend/apps/teacher/src/features/workbench/workflow/AnalysisReportSection.tsx`
- Create: `frontend/apps/teacher/src/features/workbench/workflow/AnalysisOpsSection.tsx`
- Create: `frontend/apps/teacher/src/features/workbench/workflow/AnalysisOpsSection.test.tsx`
- Modify: `frontend/apps/teacher/src/features/workbench/workflow/AnalysisReportSection.test.tsx`
- Modify: `frontend/apps/teacher/src/types/workflow.ts`

**Step 1: Write the failing tests**

新增测试要求：
- `AnalysisOpsSection` 能显示总报告数、待复核数、分域计数；
- 当当前筛选结果非空时，显示“批量重跑当前筛选”安全操作；
- 批量操作按钮会把当前筛选结果的 `report_id` 列表交给 hook action；
- `AnalysisReportSection` 继续保留当前选择/详情/单条 rerun 行为。

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm run test:unit -- apps/teacher/src/features/workbench/workflow/AnalysisOpsSection.test.tsx apps/teacher/src/features/workbench/workflow/AnalysisReportSection.test.tsx`

Expected: FAIL。

**Step 3: Write minimal implementation**

- 在 workflow types 中增加 analysis ops summary 类型；
- hook 读取 reports `summary`，并暴露 bulk rerun action；
- `AnalysisOpsSection` 展示 counters、domain chips、review queue 快照、bulk rerun 按钮；
- `AnalysisReportSection` 组合该 ops section，不重复实现现有列表/详情 UI。

**Step 4: Run test to verify it passes**

Run: `cd frontend && npm run test:unit -- apps/teacher/src/features/workbench/workflow/AnalysisOpsSection.test.tsx apps/teacher/src/features/workbench/workflow/AnalysisReportSection.test.tsx`

Expected: PASS。

**Step 5: Run focused frontend build**

Run: `cd frontend && npm run build:teacher`

Expected: PASS。

---

### Task 3: Standardize onboarding contract and extension plan template

**Files:**
- Create: `docs/reference/analysis-domain-onboarding-contract.md`
- Create: `docs/plans/templates/analysis-domain-extension-template.md`
- Modify: `docs/reference/analysis-runtime-contract.md`
- Modify: `docs/reference/analysis-domain-onboarding-template.md`
- Modify: `docs/reference/analysis-domain-checklist.md`
- Modify: `docs/INDEX.md`
- Modify: `tests/test_docs_architecture_presence.py`
- Modify: `tests/test_architecture_doc_paths.py`

**Step 1: Write the failing tests**

新增测试要求：
- 新 contract 文档和 plan template 都已存在并被 `docs/INDEX.md` 索引；
- `analysis-runtime-contract.md` 指向新的 onboarding contract；
- onboarding template/checklist 明确引用 canonical contract 与 plan template。

**Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m pytest -q tests/test_docs_architecture_presence.py tests/test_architecture_doc_paths.py`

Expected: FAIL。

**Step 3: Write minimal implementation**

- 用 contract 明确新域必须交付的 artifact/strategy/specialist/runtime/report/review/eval/rollout/rollback 要素；
- 用 plan template 规范未来 domain extension 的目标、契约、测试和 rollout 验收；
- 将两者接入 runtime contract、onboarding template、checklist 和 docs index。

**Step 4: Run test to verify it passes**

Run: `./.venv/bin/python -m pytest -q tests/test_docs_architecture_presence.py tests/test_architecture_doc_paths.py`

Expected: PASS。

---

### Task 4: Final regression

**Files:**
- Reference: `services/api/routes/analysis_report_routes.py`
- Reference: `frontend/apps/teacher/src/features/workbench/workflow/AnalysisOpsSection.tsx`
- Reference: `docs/reference/analysis-domain-onboarding-contract.md`

**Step 1: Run backend regression**

Run: `./.venv/bin/python -m pytest -q tests/test_analysis_report_ops_routes.py tests/test_analysis_report_service.py tests/test_analysis_report_routes.py tests/test_review_feedback_service.py tests/test_replay_analysis_run.py tests/test_analysis_domain_contract_checker.py tests/test_docs_architecture_presence.py tests/test_architecture_doc_paths.py`

Expected: PASS。

**Step 2: Run frontend regression**

Run: `cd frontend && npm run test:unit -- apps/teacher/src/features/workbench/workflow/AnalysisOpsSection.test.tsx apps/teacher/src/features/workbench/workflow/AnalysisReportSection.test.tsx`

Expected: PASS。

**Step 3: Run teacher build**

Run: `cd frontend && npm run build:teacher`

Expected: PASS。
