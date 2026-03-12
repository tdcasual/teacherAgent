# Agent Design Prioritized Roadmap Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在不把项目扩展成通用 agent 平台的前提下，按优先级补齐当前 agent 设计的执行期安全、路由治理、角色隔离、可观测性和 memory 可维护性短板。

**Architecture:** 继续坚持 `role -> workflow(skill) -> prompt stack -> tool policy -> chat job -> memory side effects -> history persistence` 这条主链路，不新增新的前台 agent 类型，不扩大自由工具自治范围。P0 先补“执行期真实约束”，P1 再补“配置化与角色策略收敛”，P2 最后补“timeline 可观测性”和 “memory core 拆分”，把当前系统从“方向正确”推进到“长期可演进”。

**Tech Stack:** Python 3.13、pytest、FastAPI 应用层、前端 React/TypeScript、现有 `skills/*.yaml`、SSE 事件流、现有 memory proposal / chat job / workbench 体系。

---

> 本计划补充而不是替代既有文档：
> - `docs/plans/2026-03-08-agent-design-review-and-optimization-design.md`
> - `docs/plans/2026-03-08-agent-design-optimization-implementation-plan.md`
>
> 区别在于：本计划只覆盖这次代码审阅中仍然最值得优先落地的 5 条路线，并且把每条路线压成更明确的执行顺序。

### Task 1: 在最终 `tool_dispatch` 层强制执行 skill-aware ACL（P0）

**Why first:** 当前 `tool_dispatch()` 已接收 `skill_id`，但没有把它用于最终授权校验；这是当前 agent 设计最接近“边界只靠上游自觉”的位置，应该优先补齐。

**Files:**
- Modify: `services/api/tool_dispatch_service.py`
- Modify: `services/api/agent_service.py`
- Modify: `services/api/wiring/misc_wiring.py`
- Test: `tests/test_tool_dispatch_service.py`
- Create: `tests/test_tool_dispatch_skill_policy.py`
- Doc: `docs/reference/agent-runtime-contract.md`
- Doc: `docs/architecture/module-boundaries.md`

**Step 1: Write the failing test**
- 在 `tests/test_tool_dispatch_skill_policy.py` 增加测试：
  - `role="teacher"` 且 `skill_id="physics-homework-generator"` 时，允许 `assignment.generate`，拒绝 `exam.get`
  - `role="teacher"` 且 `skill_id="physics-teacher-ops"` 时，允许 `exam.get`
  - 未提供 `skill_id` 时，保留现有 role 级行为，避免破坏历史兼容
  - `chart.exec` / `chart.agent.run` 继续维持 teacher-only 约束

**Step 2: Run test to verify it fails**
- Run: `./.venv/bin/python -m pytest -q tests/test_tool_dispatch_service.py tests/test_tool_dispatch_skill_policy.py`
- Expected: FAIL，因为当前 `tool_dispatch()` 没有用 `skill_id` 参与最终 ACL 判断。

**Step 3: Write minimal implementation**
- 在 `tool_dispatch_service` 中新增一个小型 helper：根据 `role + skill_id` 解析最终允许工具集合。
- 优先复用现有 skill runtime 的 `apply_tool_policy()`，避免在 dispatch 层复制一份 allowlist 真相。
- `tool_dispatch()` 在参数校验后、handler 分发前，做一次最终 `name in allowed_tools` 检查；不通过时返回结构化错误：

```python
return {
    "error": "tool_not_allowed",
    "tool": name,
    "role": role,
    "skill_id": skill_id,
}
```

- 在 `misc_wiring.py` 为 `ToolDispatchDeps` 挂载 skill runtime / allowed tools 所需依赖。

**Step 4: Run tests to verify it passes**
- Run: `./.venv/bin/python -m pytest -q tests/test_tool_dispatch_service.py tests/test_tool_dispatch_skill_policy.py tests/test_skills_first_class.py`
- Expected: PASS。

**Step 5: Update docs**
- 在 `docs/reference/agent-runtime-contract.md` 明确：skill 级 tool policy 不只是 prompt 限制，而是执行期最终授权。
- 在 `docs/architecture/module-boundaries.md` 明确：tool loop 只能请求工具，最终授权真相在 dispatch 层。

**Step 6: Commit**

```bash
git add services/api/tool_dispatch_service.py services/api/agent_service.py services/api/wiring/misc_wiring.py tests/test_tool_dispatch_service.py tests/test_tool_dispatch_skill_policy.py docs/reference/agent-runtime-contract.md docs/architecture/module-boundaries.md
git commit -m "fix(agent): enforce skill-aware tool dispatch acl"
```

---

### Task 2: 把 workflow routing 的真相进一步迁回 skill manifest 与评估集（P1）

**Why next:** 当前路由已经具备解释性，但仍有一部分 tie-break / regex / role-specific scoring 硬编码在 Python 中；短期有效，长期会让新 skill 接入越来越依赖核心维护者。

**Files:**
- Modify: `services/api/skill_auto_router.py`
- Modify: `services/api/skills/auto_route_rules.py`
- Modify: `services/api/skills/spec.py`
- Modify: `skills/physics-teacher-ops/skill.yaml`
- Modify: `skills/physics-homework-generator/skill.yaml`
- Modify: `skills/physics-student-focus/skill.yaml`
- Modify: `skills/physics-student-coach/skill.yaml`
- Test: `tests/test_teacher_workflow_routing_regression.py`
- Modify: `tests/fixtures/teacher_workflow_routing_cases.json`
- Create: `scripts/eval_teacher_workflow_routing.py`

**Step 1: Write the failing test**
- 扩充 `teacher_workflow_routing_cases.json`，新增以下回归样例：
  - 明确负关键词应降权而不是误命中
  - 明确学生画像 vs 学生陪练的边界
  - 明确“作业”普通提及不应该压过考试分析强信号
  - 明确低置信度落回 role default 的场景

**Step 2: Run test to verify it fails**
- Run: `./.venv/bin/python -m pytest -q tests/test_teacher_workflow_routing_regression.py`
- Expected: FAIL，因为现有硬编码评分与新增 fixture 预期不完全一致。

**Step 3: Write minimal implementation**
- 给 `SkillRoutingSpec` 增加少量通用字段（如 `priority_hint` / `tie_break_group` / `regex_keywords` 其一即可，避免 DSL 膨胀）。
- 优先把当前 `auto_route_rules.py` 中最稳定的差异化信号迁回 `skill.yaml`。
- `skill_auto_router.py` 只保留通用评分框架、阈值比较、默认回退和解释性元数据组装。
- 保留少量全局 hard-coded 规则时，要限制在“真正跨 skill 的产品规则”，并写注释说明为什么不能配置化。

**Step 4: Add a lightweight evaluator**
- 新建 `scripts/eval_teacher_workflow_routing.py`：读取 fixture，输出命中率、fallback 比例、低置信度样本。
- 脚本先本地可跑，不急着接 CI。

**Step 5: Run tests to verify it passes**
- Run: `./.venv/bin/python -m pytest -q tests/test_teacher_workflow_routing_regression.py`
- Run: `./.venv/bin/python scripts/eval_teacher_workflow_routing.py`
- Expected: pytest PASS；脚本输出 0 个 hard mismatch。

**Step 6: Commit**

```bash
git add services/api/skill_auto_router.py services/api/skills/auto_route_rules.py services/api/skills/spec.py skills/physics-teacher-ops/skill.yaml skills/physics-homework-generator/skill.yaml skills/physics-student-focus/skill.yaml skills/physics-student-coach/skill.yaml tests/test_teacher_workflow_routing_regression.py tests/fixtures/teacher_workflow_routing_cases.json scripts/eval_teacher_workflow_routing.py
git commit -m "refactor(agent): move workflow routing truth closer to skill manifests"
```

---

### Task 3: 收敛 role-specific runtime 分支为 `RoleRuntimePolicy`（P1）

**Why now:** teacher / student 分支目前散落在 start、processing、runtime、tooling、history side effects 多个模块中；在角色继续扩展前，应先把“角色策略”抽成清晰边界。

**Files:**
- Create: `services/api/role_runtime_policy.py`
- Modify: `services/api/chat_start_service.py`
- Modify: `services/api/chat_job_processing_service.py`
- Modify: `services/api/chat_runtime_service.py`
- Modify: `services/api/agent_service.py`
- Test: `tests/test_chat_start_service.py`
- Test: `tests/test_chat_runtime_service.py`
- Create: `tests/test_role_runtime_policy.py`
- Doc: `docs/reference/agent-runtime-contract.md`

**Step 1: Write the failing test**
- 新增 `tests/test_role_runtime_policy.py`，要求：
  - teacher / student 默认 skill、session 行为、memory side effect 开关可以从统一 policy 读取
  - `chat_start_service` 不再自行分散决定 teacher/student session 细节
  - `chat_runtime_service` 不再自行散落决定 limiter/model path 细节

**Step 2: Run test to verify it fails**
- Run: `./.venv/bin/python -m pytest -q tests/test_chat_start_service.py tests/test_chat_runtime_service.py tests/test_role_runtime_policy.py`
- Expected: FAIL，因为统一 policy 模块尚不存在。

**Step 3: Write minimal implementation**
- 新建 `role_runtime_policy.py`，只沉淀以下稳定真相：

```python
@dataclass(frozen=True)
class RoleRuntimePolicy:
    role: str
    default_skill_id: str
    supports_workflow_explanation: bool
    supports_memory_proposals: bool
    limiter_kind: str
```

- `chat_start_service` 通过 policy 解析默认 skill / session 行为。
- `chat_runtime_service` 通过 policy 选 limiter 与是否走 teacher model config。
- `agent_service` 通过 policy 判断是否展示 workflow 解释、是否走 teacher-only follow-up router。

**Step 4: Run tests to verify it passes**
- Run: `./.venv/bin/python -m pytest -q tests/test_chat_start_service.py tests/test_chat_runtime_service.py tests/test_role_runtime_policy.py tests/test_analysis_followup_router.py`
- Expected: PASS。

**Step 5: Commit**

```bash
git add services/api/role_runtime_policy.py services/api/chat_start_service.py services/api/chat_job_processing_service.py services/api/chat_runtime_service.py services/api/agent_service.py tests/test_chat_start_service.py tests/test_chat_runtime_service.py tests/test_role_runtime_policy.py docs/reference/agent-runtime-contract.md
git commit -m "refactor(agent): centralize role runtime policy"
```

---

### Task 4: 补统一 execution timeline，打通工作台可观测性（P2）

**Why here:** 当前已经有 `workflow.resolved`、`tool.start/finish`、`assistant.delta/done` 等事件，但这些事件更多是流式 UI 消费格式，还不是统一的“执行时间线”产品对象。

**Files:**
- Modify: `services/api/chat_job_processing_service.py`
- Modify: `services/api/chat_start_service.py`
- Modify: `services/api/api_models.py`
- Modify: `frontend/apps/teacher/src/appTypes.ts`
- Modify: `frontend/apps/teacher/src/features/chat/useTeacherChatApi.ts`
- Modify: `frontend/apps/teacher/src/features/workbench/tabs/WorkflowTab.tsx`
- Test: `frontend/apps/teacher/src/features/chat/useTeacherChatApi.stream.test.tsx`
- Create: `tests/test_chat_execution_timeline.py`

**Step 1: Write the failing test**
- 后端测试要求：job 结束后能拿到归一化 timeline，至少包含 `queued`、`processing`、`workflow.resolved`、`tool.*`、`assistant.done`。
- 前端测试要求：`WorkflowTab` 可展示最近一次执行的关键节点，而不是只显示零散状态。

**Step 2: Run test to verify it fails**
- Run: `./.venv/bin/python -m pytest -q tests/test_chat_execution_timeline.py tests/test_chat_stream_route.py`
- Run: `cd frontend && npm test -- useTeacherChatApi.stream.test.tsx`
- Expected: FAIL，因为 timeline 还没有统一的数据结构。

**Step 3: Write minimal implementation**
- 后端统一时间线条目结构：

```python
{
    "type": "workflow.resolved",
    "ts": now_iso,
    "summary": "自动切换到作业生成",
    "meta": {...},
}
```

- 先在 job record 内持久化一个裁剪后的 timeline，不需要做独立存储。
- `WorkflowTab` 只渲染最近一次 job 的关键节点和结果摘要，避免一上来做复杂 replay UI。

**Step 4: Run tests to verify it passes**
- Run: `./.venv/bin/python -m pytest -q tests/test_chat_execution_timeline.py tests/test_chat_stream_route.py`
- Run: `cd frontend && npm test -- useTeacherChatApi.stream.test.tsx`
- Expected: PASS。

**Step 5: Commit**

```bash
git add services/api/chat_job_processing_service.py services/api/chat_start_service.py services/api/api_models.py frontend/apps/teacher/src/appTypes.ts frontend/apps/teacher/src/features/chat/useTeacherChatApi.ts frontend/apps/teacher/src/features/workbench/tabs/WorkflowTab.tsx frontend/apps/teacher/src/features/chat/useTeacherChatApi.stream.test.tsx tests/test_chat_execution_timeline.py
git commit -m "feat(agent): add unified execution timeline for workbench"
```

---

### Task 5: 拆分 `teacher_memory_core`，保留 proposal-first 治理但降低维护成本（P2）

**Why last:** 当前 memory 设计方向是对的，但核心模块体量已经偏大。应在不改变治理模型的前提下，把“自动提案 / 治理规则 / 存储应用”拆开。

**Files:**
- Create: `services/api/teacher_memory_governance_service.py`
- Create: `services/api/teacher_memory_auto_service.py`
- Create: `services/api/teacher_memory_storage_service.py`
- Modify: `services/api/teacher_memory_core.py`
- Modify: `services/api/teacher_memory_record_service.py`
- Test: `tests/test_teacher_memory_core.py`
- Test: `tests/test_teacher_memory_record_service.py`
- Create: `tests/test_teacher_memory_auto_service.py`
- Create: `tests/test_teacher_memory_governance_service.py`
- Doc: `docs/reference/memory-governance.md`

**Step 1: Write the failing test**
- 新增测试要求：
  - 自动提案判定逻辑可脱离 core 独立测试
  - proposal apply / supersede / duplicate / quota 行为不变
  - `teacher_memory_core.py` 只保留 façade 级组合职责

**Step 2: Run test to verify it fails**
- Run: `./.venv/bin/python -m pytest -q tests/test_teacher_memory_core.py tests/test_teacher_memory_record_service.py tests/test_teacher_memory_auto_service.py tests/test_teacher_memory_governance_service.py`
- Expected: FAIL，因为新模块尚不存在。

**Step 3: Write minimal implementation**
- 把自动提案判定迁到 `teacher_memory_auto_service.py`
- 把冲突、去重、配额、supersede 等治理规则迁到 `teacher_memory_governance_service.py`
- 把 proposal 读写、状态更新、apply 存储迁到 `teacher_memory_storage_service.py`
- `teacher_memory_core.py` 仅保留对外 API 与依赖组合。

**Step 4: Run tests to verify it passes**
- Run: `./.venv/bin/python -m pytest -q tests/test_teacher_memory_core.py tests/test_teacher_memory_record_service.py tests/test_teacher_memory_auto_service.py tests/test_teacher_memory_governance_service.py tests/test_teacher_memory_insights_service.py`
- Expected: PASS。

**Step 5: Commit**

```bash
git add services/api/teacher_memory_governance_service.py services/api/teacher_memory_auto_service.py services/api/teacher_memory_storage_service.py services/api/teacher_memory_core.py services/api/teacher_memory_record_service.py tests/test_teacher_memory_core.py tests/test_teacher_memory_record_service.py tests/test_teacher_memory_auto_service.py tests/test_teacher_memory_governance_service.py docs/reference/memory-governance.md
git commit -m "refactor(memory): split teacher memory core by responsibility"
```

---

## Recommended Execution Order

1. **Task 1** — 先补执行期 ACL，立刻提升安全边界。
2. **Task 2** — 再清理 workflow routing 真相，降低接入新 skill 的隐性成本。
3. **Task 3** — 再做 role policy 收敛，防止角色逻辑继续散落。
4. **Task 4** — 然后做 execution timeline，给工作台和运营提供统一可视化。
5. **Task 5** — 最后拆 memory core，控制技术债但不打断主链路。

## Exit Criteria

- `tool_dispatch()` 不再把 `skill_id` 视为无用参数。
- workflow routing 的主要差异化信号优先写在 skill manifest / fixture，而不是散落在 Python 分支。
- teacher / student 角色策略存在统一 policy 真相层。
- 工作台可看到统一 execution timeline，而不是只看到零散状态。
- memory proposal-first 治理不变，但 `teacher_memory_core.py` 不再继续膨胀。

## Non-Goals

- 不引入新的开放式 agent marketplace。
- 不把前台交互改成多 agent 对话。
- 不把 tool loop 升级成业务主编排层。
- 不在这一轮引入新的外部基础设施或重型事件总线。

