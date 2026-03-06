# Project Recovery And Quality Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在 4 周内把当前仓库从“体系成熟但工作区失真”恢复到“可稳定交付、门禁可信、热点可持续治理”的状态。

**Architecture:** 执行顺序固定为：先恢复 importability 与安全回归，再恢复质量门禁可信度，再拆解后端/前端高风险热点，最后把发布与运维证据固化进 CI 和文档。整个过程不做大范围功能扩展，也不通过放宽预算来伪装改进结果。

**Tech Stack:** Python 3.13, FastAPI, pytest, Ruff, mypy, React 19, TypeScript, Vite, Vitest, Playwright, GitHub Actions, Docker Compose.

---

## Success Gates

在开始任何新功能前，必须同时满足以下条件：

1. `services/api`、`frontend`、`tests`、`docs`、`.github` 中无 merge conflict markers。
2. `python3.13 scripts/quality/check_backend_quality_budget.py` 返回 0。
3. `python3.13 scripts/quality/check_complexity_budget.py` 返回 0。
4. `python3.13 -m pytest -q tests/test_tool_dispatch_security.py tests/test_auth_route_guard_regression.py` 返回 0。
5. `cd frontend && npm run typecheck && npm run build:teacher` 返回 0。

## Non-Goals

- 不新增跨模块新功能。
- 不通过调大 `backend_quality_budget.json` 或 `function_complexity_budget.json` 来让 CI 变绿。
- 不做一次性“大重写”；所有重构都必须由现有或新增守卫测试驱动。

## Phase A (Week 1): Restore Repository Truth

### Task 1: 清理核心后端冲突标记并恢复导入能力

**Files:**
- Modify: `services/api/core_service_imports.py`
- Modify: `services/api/core_services_runtime.py`
- Test: `tests/test_tool_dispatch_security.py`
- Test: `tests/test_auth_route_guard_regression.py`

**Step 1: 运行现有失败回归，确认根因是语法损坏**

Run: `python3 -m pytest -q tests/test_tool_dispatch_security.py tests/test_auth_route_guard_regression.py`
Expected: FAIL，并出现 `SyntaxError`，定位到 `services/api/core_service_imports.py` 或 `services/api/core_services_runtime.py`。

**Step 2: 做最小修复，不引入行为漂移**

- 删除两处 merge conflict markers。
- 在 `services/api/core_service_imports.py` 中移除对已不存在文件 `services/api/student_profile_api_service.py` 的陈旧分支引用。
- 在 `services/api/core_services_runtime.py` 中保留 `core: Any | None = None` 版本的运行时包装函数，避免破坏当前 route / multi-tenant 调用链。

**Step 3: 验证无冲突残留**

Run: `rg -n "^(<<<<<<<|=======|>>>>>>>)" services/api`
Expected: no output.

**Step 4: 运行回归验证**

Run: `python3 -m pytest -q tests/test_tool_dispatch_security.py tests/test_auth_route_guard_regression.py`
Expected: PASS.

**Step 5: Commit**

```bash
git add services/api/core_service_imports.py services/api/core_services_runtime.py
git commit -m "fix(core): remove merge conflict debris from backend core wrappers"
```

### Task 2: 为 merge conflict 和本地 Python 版本建立仓库级护栏

**Files:**
- Create: `tests/test_no_merge_conflict_markers.py`
- Create: `.python-version`
- Modify: `.github/workflows/ci.yml`
- Modify: `README.md`
- Modify: `docs/getting-started/quickstart.md`
- Test: `tests/test_ci_workflow_quality.py`

**Step 1: 写失败守卫测试**

新增测试，递归扫描 `services/`、`frontend/`、`tests/`、`docs/`、`.github/`，断言不存在 `<<<<<<<` / `=======` / `>>>>>>>` 标记。

**Step 2: 运行测试确认失败**

Run: `python3 -m pytest -q tests/test_no_merge_conflict_markers.py`
Expected: FAIL（当前仓库存在冲突标记）。

**Step 3: 最小实现**

- 新增 `.python-version`，固定本地开发解释器为 `3.13`。
- 在 CI 中增加 `rg` 扫描步骤，把冲突标记拦在最前面。
- 在 `README.md` 与 `docs/getting-started/quickstart.md` 中明确：非 Docker 本地后端开发应使用 Python 3.13。

**Step 4: 运行验证**

Run: `python3 -m pytest -q tests/test_no_merge_conflict_markers.py tests/test_ci_workflow_quality.py`
Expected: PASS.

**Step 5: Commit**

```bash
git add tests/test_no_merge_conflict_markers.py .python-version .github/workflows/ci.yml README.md docs/getting-started/quickstart.md
git commit -m "ci(repo): guard against conflict markers and pin local python version"
```

### Task 3: 恢复后端质量预算脚本到“可操作、可信、绿色”

**Files:**
- Modify: `services/api/core_services_application.py`
- Modify: `services/api/wiring/student_wiring.py`
- Modify: `scripts/quality/check_backend_quality_budget.py`
- Test: `tests/test_backend_quality_budget.py`
- Test: `tests/test_backend_quality_budget_regression.py`
- Test: `tests/test_backend_quality_budget_check_script.py`

**Step 1: 在 Python 3.13 下运行当前预算采集**

Run: `python3.13 scripts/quality/check_backend_quality_budget.py --print-only --show-tool-output`
Expected: FAIL 或打印出超预算指标；如果工具链不匹配，原始输出必须可见。

**Step 2: 做最小修复**

- 修复 `services/api/core_services_application.py` 与 `services/api/wiring/student_wiring.py` 的 `I001` 导入排序问题。
- 改进 `scripts/quality/check_backend_quality_budget.py` 的失败信息：当 `mypy` 因解释器版本或语法阻断退出时，保留原始输出并给出可执行提示，但不放宽预算阈值。

**Step 3: 先跑静态检查，再跑预算测试**

Run: `python3.13 -m ruff check services/api --statistics`
Expected: `Found 0 errors.` 或不高于预算。

Run: `python3.13 -m mypy --follow-imports=skip services/api`
Expected: `Success: no issues found` 或不高于预算。

Run: `python3.13 -m pytest -q tests/test_backend_quality_budget.py tests/test_backend_quality_budget_regression.py tests/test_backend_quality_budget_check_script.py`
Expected: PASS.

**Step 4: Commit**

```bash
git add services/api/core_services_application.py services/api/wiring/student_wiring.py scripts/quality/check_backend_quality_budget.py tests/test_backend_quality_budget.py tests/test_backend_quality_budget_regression.py tests/test_backend_quality_budget_check_script.py
git commit -m "fix(quality): restore backend quality budget checks to actionable green"
```

## Phase B (Week 2): Burn Down Backend Hotspots

### Task 4: 先拆最靠近请求链路的后端编排热点

**Files:**
- Modify: `services/api/agent_service.py`
- Modify: `services/api/chat_job_processing_service.py`
- Test: `tests/test_agent_service_structure.py`
- Test: `tests/test_chat_job_processing_structure.py`
- Test: `tests/test_complexity_budget_guard.py`

**Step 1: 运行结构预算与复杂度守卫**

Run: `python3 -m pytest -q tests/test_agent_service_structure.py tests/test_chat_job_processing_structure.py tests/test_complexity_budget_guard.py`
Expected: FAIL 或暴露当前函数体过长 / C901 超线。

**Step 2: 以 helper extraction 为唯一手段拆分**

- 将 `run_agent_runtime` 拆成输入标准化、工具选择、结果汇总、失败收敛等私有 helper。
- 将 `process_chat_job` 拆成状态检查、上下文装载、LLM 调用、写回与事件追加等私有 helper。
- 不改对外函数签名，不重排公共 API。

**Step 3: 运行 focused regression**

Run: `python3 -m pytest -q tests/test_agent_service_structure.py tests/test_chat_job_processing_structure.py tests/test_chat_job_processing_service.py tests/test_chat_start_service.py`
Expected: PASS.

**Step 4: 运行复杂度预算**

Run: `python3 scripts/quality/check_complexity_budget.py`
Expected: 比当前结果明显下降，且关键文件不再新增告警。

**Step 5: Commit**

```bash
git add services/api/agent_service.py services/api/chat_job_processing_service.py tests/test_agent_service_structure.py tests/test_chat_job_processing_structure.py
git commit -m "refactor(services): split agent and chat job orchestration hotspots"
```

### Task 5: 收敛剩余后端大热点到预算内

**Files:**
- Create: `tests/test_backend_complexity_targets.py`
- Modify: `services/api/auth_registry_service.py`
- Modify: `services/api/chart_executor.py`
- Modify: `services/api/teacher_memory_core.py`
- Modify: `services/api/exam_upload_parse_service.py`
- Test: `tests/test_service_complexity_hotspots.py`
- Test: `tests/test_complexity_budget_guard.py`

**Step 1: 新增热点目标测试**

新增测试，固定以下文件必须无新的 `C901`：
- `services/api/auth_registry_service.py`
- `services/api/chart_executor.py`
- `services/api/teacher_memory_core.py`
- `services/api/exam_upload_parse_service.py`

**Step 2: 运行测试确认失败**

Run: `python3 -m pytest -q tests/test_backend_complexity_targets.py tests/test_service_complexity_hotspots.py tests/test_complexity_budget_guard.py`
Expected: FAIL.

**Step 3: 分批拆分，不交叉混改**

- `auth_registry_service.py`：拆查询、序列化、版本校验、持久化写回。
- `chart_executor.py`：拆 sandbox 准备、输入校验、执行、结果清洗。
- `teacher_memory_core.py`：拆规则匹配、冲突处理、持久化写回。
- `exam_upload_parse_service.py`：拆解析预检、OCR/结构化、失败回退。

**Step 4: 验证复杂度与回归**

Run: `python3 -m pytest -q tests/test_backend_complexity_targets.py tests/test_service_complexity_hotspots.py tests/test_complexity_budget_guard.py`
Expected: PASS.

Run: `python3 scripts/quality/check_complexity_budget.py`
Expected: PASS.

**Step 5: Commit**

```bash
git add tests/test_backend_complexity_targets.py services/api/auth_registry_service.py services/api/chart_executor.py services/api/teacher_memory_core.py services/api/exam_upload_parse_service.py
git commit -m "refactor(backend): reduce remaining service complexity hotspots"
```

## Phase C (Week 3): Decompose Teacher Frontend Hotspots

### Task 6: 让教师端主入口与高风险 hook 回到可维护区间

**Files:**
- Create: `frontend/apps/teacher/src/features/layout/useTeacherShellState.ts`
- Create: `frontend/apps/teacher/src/features/chat/useTeacherSessionState.ts`
- Create: `frontend/apps/teacher/src/features/workbench/hooks/useTeacherWorkbenchState.ts`
- Modify: `frontend/apps/teacher/src/App.tsx`
- Modify: `frontend/apps/teacher/src/features/chat/useTeacherChatApi.ts`
- Modify: `frontend/apps/teacher/src/features/workbench/hooks/useAssignmentWorkflow.ts`
- Test: `tests/test_teacher_frontend_structure.py`
- Test: `tests/test_frontend_type_hardening.py`

**Step 1: 运行现有前端结构守卫**

Run: `python3 -m pytest -q tests/test_teacher_frontend_structure.py tests/test_frontend_type_hardening.py`
Expected: PASS 或逼近预算边缘；用作拆分回归锚点。

**Step 2: 最小拆分**

- `App.tsx` 只保留路由级状态编排与组件装配。
- 将页面级 shell 状态抽到 `useTeacherShellState.ts`。
- 将会话编排抽到 `useTeacherSessionState.ts`。
- 将工作台聚合状态抽到 `useTeacherWorkbenchState.ts`。
- 在 `useTeacherChatApi.ts` 与 `useAssignmentWorkflow.ts` 中继续下沉私有 helper，避免 hook 内部继续膨胀。

**Step 3: 运行前端验证链路**

Run: `python3 -m pytest -q tests/test_teacher_frontend_structure.py tests/test_frontend_type_hardening.py`
Expected: PASS.

Run: `cd frontend && npm run typecheck && npm run test:unit && npm run build:teacher`
Expected: PASS.

**Step 4: Commit**

```bash
git add frontend/apps/teacher/src/App.tsx frontend/apps/teacher/src/features/layout/useTeacherShellState.ts frontend/apps/teacher/src/features/chat/useTeacherSessionState.ts frontend/apps/teacher/src/features/workbench/hooks/useTeacherWorkbenchState.ts frontend/apps/teacher/src/features/chat/useTeacherChatApi.ts frontend/apps/teacher/src/features/workbench/hooks/useAssignmentWorkflow.ts tests/test_teacher_frontend_structure.py tests/test_frontend_type_hardening.py
git commit -m "refactor(frontend): split teacher shell and workflow hotspots"
```

## Phase D (Week 4): Make Release Gates And Operability Mandatory

### Task 7: 把质量、复杂度、SLO 证据固化进交付闭环

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `scripts/quality/collect_backend_quality.sh`
- Modify: `docs/operations/change-management-and-governance.md`
- Modify: `docs/operations/slo-and-observability.md`
- Test: `tests/test_ci_workflow_quality.py`
- Test: `tests/test_operability_evidence.py`
- Test: `tests/test_docs_governance_baseline.py`

**Step 1: 写失败文档/CI 合同测试**

扩展现有测试，要求：
- CI 必须执行 `check_backend_quality_budget.py` 与 `check_complexity_budget.py`。
- 运维文档必须说明：发布前查看 `/ops/metrics`、`/ops/slo`，并保留审计证据。

**Step 2: 运行测试确认失败**

Run: `python3 -m pytest -q tests/test_ci_workflow_quality.py tests/test_operability_evidence.py tests/test_docs_governance_baseline.py`
Expected: FAIL（直到文档与 workflow 明确补齐）。

**Step 3: 最小实现**

- 在 `collect_backend_quality.sh` 中明确输出质量与复杂度检查结果。
- 在治理文档中加入“发布前门禁”与“回滚后核验”步骤。
- 保持现有 `/ops/metrics`、`/ops/slo` 合同不变，只把其纳入交付流程。

**Step 4: 运行验证**

Run: `python3 -m pytest -q tests/test_ci_workflow_quality.py tests/test_operability_evidence.py tests/test_docs_governance_baseline.py`
Expected: PASS.

**Step 5: Commit**

```bash
git add .github/workflows/ci.yml scripts/quality/collect_backend_quality.sh docs/operations/change-management-and-governance.md docs/operations/slo-and-observability.md tests/test_ci_workflow_quality.py tests/test_operability_evidence.py tests/test_docs_governance_baseline.py
git commit -m "docs(ci): harden release gates around quality and operability evidence"
```

## Final Verification

在声明“仓库恢复到可交付状态”之前，必须一次性运行：

```bash
rg -n "^(<<<<<<<|=======|>>>>>>>)" services frontend tests docs .github
python3.13 scripts/quality/check_backend_quality_budget.py
python3.13 scripts/quality/check_complexity_budget.py
python3.13 -m pytest -q tests/test_tool_dispatch_security.py tests/test_auth_route_guard_regression.py tests/test_complexity_budget_guard.py tests/test_service_complexity_hotspots.py tests/test_teacher_frontend_structure.py tests/test_frontend_type_hardening.py tests/test_operability_evidence.py
cd frontend && npm run typecheck && npm run test:unit && npm run build:teacher && cd ..
```

Expected: all commands return 0, with no conflict markers and no budget violations.
