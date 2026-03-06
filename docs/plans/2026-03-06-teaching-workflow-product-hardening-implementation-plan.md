# Teaching Workflow Product Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在 4 周内把当前仓库明确收敛为“教学 workflow 产品”，降低 agent/platform 叙事混乱，提升老师/学生/管理员主链路的确定性、可解释性与可回归性。

**Architecture:** 保留单运行时 agent 作为自然语言入口，不继续扩展通用平台能力；先统一产品真相与用户语言，再暴露 workflow 路由解释，把高频老师场景从通用 tool loop 提升为显式 workflow 编排，最后补上 memory 治理与发布门禁。核心原则是“固定 workflow + 静态工具 + 解释性路由 + 可验证副作用”。

**Tech Stack:** Python 3.13, FastAPI, pytest, React 19, TypeScript, Vitest, Playwright, GitHub Actions, Docker Compose, Markdown docs.

---

## Success Gates

在进入新功能开发前，必须同时满足以下条件：

1. 老师端用户可见文案将“技能/平台”收敛为“工作流能力/教学能力”，不再暗示插件市场。
2. 每个 teacher chat job 都能记录 `requested -> effective -> reason -> confidence` 的 workflow 解析结果。
3. 高频老师场景（考试分析、学生重点分析、作业生成、课堂材料采集）具备显式 workflow 编排入口。
4. memory 副作用能区分“实时事实”“会话上下文”“持久化记忆提案”，且默认不自动应用持久化记忆。
5. CI / smoke 覆盖老师、学生、管理员三条主链路的最小可用闭环。

## Non-Goals

- 不恢复动态 skill import / marketplace。
- 不实现动态 tool runtime / 外部 skill 执行平台。
- 不引入多 agent 协作架构。
- 不做一次性大重写；所有改动都必须由现有或新增回归测试驱动。

## Execution Rules

每个任务执行时都遵守同一微循环：

1. 先写或补最小失败测试。
2. 跑单测确认失败原因与任务目标一致。
3. 做最小实现，不顺手扩 scope。
4. 跑任务级验证命令。
5. 通过后立即提交一个小 commit。

---

## Phase A (Week 1): Publish Product Truth

### Task 1: 统一产品定位与运行时契约文档

**Files:**
- Create: `docs/reference/agent-runtime-contract.md`
- Modify: `README.md`
- Modify: `docs/INDEX.md`
- Modify: `docs/reference/model-policy.md`
- Modify: `docs/architecture/module-boundaries.md`

**Checklist:**
1. 在 `docs/reference/agent-runtime-contract.md` 写清 teacher/student/admin 主链路：`role -> workflow(skill) -> prompt stack -> tool policy -> chat job -> memory side effects -> history persistence`。
2. 在 `README.md` 与 `docs/INDEX.md` 中明确项目定位是“教学 workflow 产品”，不是通用 agent 平台。
3. 修正 `docs/reference/model-policy.md` 中与实际运行时不一致的模型/路由叙述，确保与当前 `teacher model config + provider registry + fallback chain` 现实一致。
4. 在 `docs/architecture/module-boundaries.md` 中补充“workflow 编排优先于自由工具循环”的边界说明。
5. 用一个短表格列出内置 workflow：考试分析、学生重点分析、作业生成、课堂材料采集、学生陪练。

**Validation:**
- Run: `python3.13 -m pytest -q tests/test_skill_routes.py tests/test_skills_endpoint.py tests/test_chat_wiring_structure.py`
- Expected: PASS。

**Acceptance:**
- 新人只读 `README.md` 和 `docs/reference/agent-runtime-contract.md`，10 分钟内能说清主链路。
- 文档不再同时出现“平台扩展优先”和“产品收敛优先”两套叙事。

**Commit:**
```bash
git add README.md docs/INDEX.md docs/reference/model-policy.md docs/reference/agent-runtime-contract.md docs/architecture/module-boundaries.md
git commit -m "docs: align product positioning with teaching workflow runtime"
```

### Task 2: 收敛老师端用户可见命名为 workflow 能力

**Files:**
- Modify: `frontend/apps/teacher/src/appTypes.ts`
- Modify: `frontend/apps/teacher/src/features/workbench/TeacherWorkbench.tsx`
- Modify: `frontend/apps/teacher/src/features/workbench/tabs/SkillsTab.tsx`
- Modify: `frontend/apps/teacher/src/features/chat/ChatComposer.tsx`
- Modify: `frontend/apps/teacher/src/features/chat/useTeacherChatApi.ts`
- Modify: `frontend/apps/teacher/src/features/workbench/teacherWorkbenchViewModel.ts`

**Checklist:**
1. 保持内部 `skill_id` 与后端接口不变，只修改老师端用户可见文案、空状态、说明文字与按钮标签。
2. 将“技能列表/技能召唤”表达收敛为“教学能力/工作流入口/能力模板”。
3. 保留高级用户可通过 invocation token 触发 workflow，但文案不暗示“安装/导入第三方能力”。
4. 若本地状态键名带有 `teacherSkill*`，先保持兼容，不在本周做破坏性迁移。
5. 更新任何与该命名强绑定的 view model 文案。

**Validation:**
- Run: `cd frontend && npm run test:unit -- apps/teacher/src/features/chat/useTeacherChatApi.stream.test.tsx apps/teacher/src/features/workbench/tabs/MemoryTab.test.tsx`
- Run: `cd frontend && npm run build:teacher`
- Expected: PASS。

**Acceptance:**
- 老师端所有主要入口都在说“能力/工作流”，而不是“插件/平台/导入技能”。
- 保持现有后端 `skill_id` 接口兼容，不影响 chat 提交。

**Commit:**
```bash
git add frontend/apps/teacher/src/appTypes.ts frontend/apps/teacher/src/features/workbench/TeacherWorkbench.tsx frontend/apps/teacher/src/features/workbench/tabs/SkillsTab.tsx frontend/apps/teacher/src/features/chat/ChatComposer.tsx frontend/apps/teacher/src/features/chat/useTeacherChatApi.ts frontend/apps/teacher/src/features/workbench/teacherWorkbenchViewModel.ts
git commit -m "refactor(teacher-ui): rename skill surfaces to workflow capabilities"
```

---

## Phase B (Week 2): Make Workflow Routing Explainable

### Task 3: 把 workflow 解析结果写入 job 状态与事件流

**Files:**
- Modify: `services/api/skill_auto_router.py`
- Modify: `services/api/chat_job_processing_service.py`
- Modify: `services/api/api_models.py`
- Modify: `services/api/chat_event_stream_service.py`
- Modify: `services/api/routes/chat_route_handlers.py`

**Checklist:**
1. 保持当前 `resolve_effective_skill()` 规则体系不大改，只补强输出字段的一致性和稳定命名。
2. 在 chat job 里持久化 `skill_id_requested`、`skill_id_effective`、`skill_reason`、`skill_confidence`、`skill_candidates`。
3. 如果当前 job/status payload 已有字段，优先扩展而不是新增平行结构。
4. 在 SSE 或 runtime event 中增加轻量 `workflow.resolved` 事件，供老师端调试和 UI 提示使用。
5. 确保 student 端不会收到 teacher-only 解释性噪音。

**Validation:**
- Run: `python3.13 -m pytest -q tests/test_skill_auto_router.py tests/test_chat_job_processing_service.py tests/test_chat_status_flow.py tests/test_chat_stream_route.py`
- Expected: PASS。

**Acceptance:**
- 每个 teacher chat job 都能还原“用户请求了什么 workflow、实际命中了什么、为什么”。
- 自动路由失败时，默认回退路径可解释，而不是静默吞掉。

**Commit:**
```bash
git add services/api/skill_auto_router.py services/api/chat_job_processing_service.py services/api/api_models.py services/api/chat_event_stream_service.py services/api/routes/chat_route_handlers.py
git commit -m "feat(chat): persist workflow routing explanations in job status and events"
```

### Task 4: 建立 workflow 路由回归集并在老师端展示解释

**Files:**
- Create: `tests/fixtures/teacher_workflow_routing_cases.json`
- Create: `tests/test_teacher_workflow_routing_regression.py`
- Modify: `frontend/apps/teacher/src/features/chat/useTeacherChatApi.ts`
- Modify: `frontend/apps/teacher/src/features/chat/ChatComposer.tsx`
- Modify: `frontend/apps/teacher/src/features/workbench/teacherWorkbenchViewModel.ts`
- Modify: `frontend/apps/teacher/src/features/chat/useTeacherChatApi.stream.test.tsx`

**Checklist:**
1. 建一个覆盖高频老师意图的固定样本集：考试分析、学生诊断、生成作业、课堂采集、模糊输入、显式 invocation。
2. 后端回归测试直接读取 fixture，避免把路由判断散落在多个 test 常量里。
3. 老师端只展示低打扰解释：如“已按考试分析 workflow 处理”；不要把调试细节灌进主聊天气泡。
4. 对低置信度或默认回退场景显示轻提示，帮助老师理解系统行为。
5. 保证 invocation 明确指定时，显式 workflow 仍然优先。

**Validation:**
- Run: `python3.13 -m pytest -q tests/test_teacher_workflow_routing_regression.py tests/test_skill_auto_router.py`
- Run: `cd frontend && npm run test:unit -- apps/teacher/src/features/chat/useTeacherChatApi.stream.test.tsx`
- Expected: PASS。

**Acceptance:**
- 20~30 条老师高频输入拥有稳定、可回归的 workflow 结果。
- 老师在 UI 上能理解为何进入某个 workflow，但不会被技术细节打扰。

**Commit:**
```bash
git add tests/fixtures/teacher_workflow_routing_cases.json tests/test_teacher_workflow_routing_regression.py frontend/apps/teacher/src/features/chat/useTeacherChatApi.ts frontend/apps/teacher/src/features/chat/ChatComposer.tsx frontend/apps/teacher/src/features/workbench/teacherWorkbenchViewModel.ts frontend/apps/teacher/src/features/chat/useTeacherChatApi.stream.test.tsx
git commit -m "test(chat): add teacher workflow routing regression coverage"
```

---

## Phase C (Week 3): Promote High-Frequency Flows Into Explicit Orchestration

### Task 5: 新增老师主 workflow 编排层

**Files:**
- Create: `services/api/teacher_workflows/__init__.py`
- Create: `services/api/teacher_workflows/resolution.py`
- Create: `services/api/teacher_workflows/exam_analysis.py`
- Create: `services/api/teacher_workflows/student_focus.py`
- Create: `services/api/teacher_workflows/homework_generation.py`
- Create: `services/api/teacher_workflows/lesson_capture.py`
- Modify: `services/api/chat_job_processing_service.py`
- Modify: `services/api/agent_service.py`
- Modify: `services/api/wiring/chat_wiring.py`

**Checklist:**
1. 新编排层只负责高频老师 workflow 的确定性前置步骤与上下文装配，不复制底层 service 逻辑。
2. 先落四条链：考试分析、学生重点分析、作业生成、课堂材料采集。
3. 让 `chat_job_processing_service.py` 在 teacher 场景优先解析 workflow，再决定是走显式 orchestration 还是通用 agent runtime。
4. 保持 `agent_service.py` 仍是自然语言生成与工具循环入口，但减少它承担“猜业务状态”的责任。
5. 所有新编排必须符合 `routes -> application/workflow -> services` 的依赖方向。

**Validation:**
- Run: `python3.13 -m pytest -q tests/test_chat_job_processing_service.py tests/test_chat_wiring_context.py tests/test_chat_route_flow.py`
- Expected: PASS。

**Acceptance:**
- 四条高频老师链路具备独立编排入口，系统不再完全依赖 prompt + tool loop 猜步骤。
- 现有 chat 提交流程不被破坏。

**Commit:**
```bash
git add services/api/teacher_workflows services/api/chat_job_processing_service.py services/api/agent_service.py services/api/wiring/chat_wiring.py
git commit -m "feat(teacher-workflows): add explicit orchestration layer for core teacher flows"
```

### Task 6: 收紧每个 workflow 的前置校验、工具预算与 skill 配置

**Files:**
- Modify: `services/api/teacher_assignment_preflight_service.py`
- Modify: `services/api/skills/runtime.py`
- Modify: `skills/physics-teacher-ops/skill.yaml`
- Modify: `skills/physics-student-focus/skill.yaml`
- Modify: `skills/physics-homework-generator/skill.yaml`
- Modify: `skills/physics-lesson-capture/skill.yaml`
- Modify: `tests/test_skills_policy_consistency.py`
- Modify: `tests/test_skill_routing_config.py`

**Checklist:**
1. 把“缺 `exam_id` / 缺 student identity / 缺附件上下文”这类高频失败前置为 workflow preflight，而不是丢给模型自由补救。
2. 对四条主 workflow 重新审视 `tools.allow`、`max_tool_rounds`、`max_tool_calls`，尽量缩小。
3. 只在确实需要时才让 teacher workflow 进入通用 tool loop。
4. 校验 skill yaml 的预算与真实 workflow 设计保持一致。
5. 让默认 teacher workflow 承担兜底，但不要吞掉专有 workflow 的显式前置条件。

**Validation:**
- Run: `python3.13 -m pytest -q tests/test_skills_policy_consistency.py tests/test_skill_routing_config.py tests/test_chat_start_service.py tests/test_teacher_workflow_routing_regression.py`
- Expected: PASS。

**Acceptance:**
- 高频老师链路平均 tool rounds 下降。
- 因缺关键上下文导致的反复追问减少。

**Commit:**
```bash
git add services/api/teacher_assignment_preflight_service.py services/api/skills/runtime.py skills/physics-teacher-ops/skill.yaml skills/physics-student-focus/skill.yaml skills/physics-homework-generator/skill.yaml skills/physics-lesson-capture/skill.yaml tests/test_skills_policy_consistency.py tests/test_skill_routing_config.py
git commit -m "refactor(workflows): tighten preflight and tool budgets for teacher flows"
```

---

## Phase D (Week 4): Govern Memory And Release Gates

### Task 7: 建立 memory provenance 与默认安全策略

**Files:**
- Create: `docs/reference/memory-governance.md`
- Modify: `services/api/chat_job_processing_service.py`
- Modify: `services/api/teacher_memory_auto_service.py`
- Modify: `services/api/student_memory_service.py`
- Modify: `services/api/routes/teacher_memory_routes.py`
- Modify: `services/api/routes/teacher_student_memory_routes.py`

**Checklist:**
1. 文档中明确区分三层：实时事实（tool/data）、会话上下文、持久化 memory 提案。
2. teacher/student memory 默认只自动提案，不自动应用；若已有自动应用能力，改成显式配置开关并默认关闭。
3. 在 memory 相关 API 或展示层加入 provenance 字段，说明来源是 tool、session summary 还是 memory proposal。
4. `chat_job_processing_service.py` 中的 post-done side effects 要带上最小来源信息，方便追踪误写入。
5. 只保存教学上长期有价值的摘要，不把原始成绩表/OCR 噪声直接写入 memory。

**Validation:**
- Run: `python3.13 -m pytest -q tests/test_teacher_memory_auto_service.py tests/test_teacher_memory_proposals_api.py tests/test_student_memory_auto.py tests/test_student_memory_proposals_api.py tests/test_chat_job_processing_persistence.py`
- Expected: PASS。

**Acceptance:**
- 任意一条 memory 提案都能回答“它来自哪里、是否已确认、是否已应用”。
- 默认配置下不会静默把不稳定事实写入长期记忆。

**Commit:**
```bash
git add docs/reference/memory-governance.md services/api/chat_job_processing_service.py services/api/teacher_memory_auto_service.py services/api/student_memory_service.py services/api/routes/teacher_memory_routes.py services/api/routes/teacher_student_memory_routes.py
git commit -m "feat(memory): add provenance-first governance for teaching memories"
```

### Task 8: 把 workflow smoke 与发布门禁固化进 CI

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `.github/workflows/teacher-e2e.yml`
- Modify: `scripts/chat_stream_stability_smoke.py`
- Modify: `scripts/student_chat_smoke_load.py`
- Modify: `docs/operations/change-management-and-governance.md`
- Modify: `docs/operations/slo-and-observability.md`
- Modify: `tests/test_ci_smoke_e2e_workflow.py`
- Modify: `tests/test_ci_workflow_quality.py`
- Modify: `tests/test_ci_backend_hardening_workflow.py`

**Checklist:**
1. 在 CI 中明确老师、学生主链路 smoke 的职责边界：老师 workflow、学生学习闭环、管理员最小账号治理。
2. 如果现有 smoke 脚本不足以表达 workflow 成功标准，先补脚本，再接入 CI。
3. 保持 smoke 运行时长可控，避免把完整 E2E 套件塞进每次 PR。
4. 在治理文档里加入“发布前必须查看的 workflow 指标”：回退率、tool 错误率、memory 提案率、teacher/student 关键闭环通过率。
5. 把失败时的排查入口文档化，避免 smoke 红了以后只能靠人工猜。

**Validation:**
- Run: `python3.13 -m pytest -q tests/test_ci_smoke_e2e_workflow.py tests/test_ci_workflow_quality.py tests/test_ci_backend_hardening_workflow.py`
- Run: `cd frontend && npm run e2e:smoke`
- Expected: PASS。

**Acceptance:**
- 每次发布前都能用一组固定 smoke 证明老师、学生链路没有倒退。
- 运营与研发对“上线是否安全”有同一套证据。

**Commit:**
```bash
git add .github/workflows/ci.yml .github/workflows/teacher-e2e.yml scripts/chat_stream_stability_smoke.py scripts/student_chat_smoke_load.py docs/operations/change-management-and-governance.md docs/operations/slo-and-observability.md tests/test_ci_smoke_e2e_workflow.py tests/test_ci_workflow_quality.py tests/test_ci_backend_hardening_workflow.py
git commit -m "ci: promote teaching workflow smoke gates into release policy"
```

---

## Suggested Weekly Cadence

### Week 1 Exit
- 文档真相统一。
- 老师端命名收敛完成。

### Week 2 Exit
- workflow 路由可解释、可回归。
- 老师端能轻量显示 routing 解释。

### Week 3 Exit
- 四条主 workflow 进入显式编排层。
- tool budget 与 preflight 收紧完成。

### Week 4 Exit
- memory provenance 可追踪。
- CI / smoke 真正服务于教学闭环发布。

## Priority Order

1. 文档与运行时真相统一。
2. workflow 路由解释与回归。
3. 高频老师 workflow 显式编排。
4. memory 治理与发布门禁。

## Risks To Watch

- 前端改名过猛，破坏已有 `skill_id` / localStorage 兼容。
- workflow 编排层过度复制现有 service 逻辑，形成第二套业务核心。
- 路由解释字段暴露过多实现细节，影响老师体验。
- memory 治理只写文档、不改默认行为，导致“看起来安全，实际上仍自动写入”。

## First Execution Slice

如果只做第一周最小可交付，按以下顺序执行：

1. `Task 1` 文档与 runtime truth。
2. `Task 2` 老师端命名收敛。
3. 跑 Week 1 全量验证。
4. 产出一份简短审阅纪要，确认再进入 Week 2。
