# Survey Multi-Agent Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在保留现有教学 workflow 主链的前提下，为“问卷系统自动推送结果 -> 统一证据包 -> specialist agent 分析 -> 老师可读报告”建立一条可控、可扩展、可回放的多 Agent 执行链路，并为后续学生分层、风险识别、自动动作生成与多模态作业接入打好基础。

**Architecture:** 保留当前 `role -> workflow -> tool policy -> chat job -> memory/history` 控制平面，只在 workflow 内部新增 `delegation/handoff` 执行层。第一阶段先打通 `Webhook Intake -> Survey Job -> Evidence Bundle -> Survey Analyst Agent -> Report Delivery` 的后台垂直切片，再把 `Coordinator` 的 survey 查询与受控 handoff 接入现有 teacher chat。所有新能力以受控 registry、显式 contract、结构化 artifact 为核心，不把系统扩展成开放式多 Agent 平台。

**Tech Stack:** Python 3.13, FastAPI, Pydantic, pytest, existing queue backends (inline/RQ), teacher chat SSE pipeline, React 19, TypeScript, Vitest, Markdown docs.

---

## Preconditions

在开始实现前，先统一以下工程前提：

1. 阅读设计文档：`docs/plans/2026-03-06-survey-multi-agent-design.md`
2. 在独立 worktree 中执行本计划，避免与当前主开发线互相污染。
3. 所有新增 survey 相关后端文件统一放在 `services/api/` 下，优先复用 `application / deps / routes / wiring / workers` 现有分层。
4. 所有 specialist-agent 相关契约统一走新 registry，不要临时把逻辑散落在 `chat_job_processing_service.py` 和 `agent_service.py` 中。
5. 每个任务必须先补最小失败测试，再做最小实现。

## Success Gates

在宣布 V1 完成前，必须同时满足以下条件：

1. Webhook 推送可通过验签、幂等、归属校验进入 survey job，并能在 inline/RQ 两种队列路径运行。
2. 系统能把结构化问卷数据、PDF 报告、截图、网页导出统一为 `survey_evidence_bundle`，并显式记录 `parse_confidence` 与 `missing_fields`。
3. `Survey Analyst Agent` 能基于 bundle 稳定输出 `analysis_artifact`，至少包含 `executive_summary`、`key_signals`、`group_differences`、`teaching_recommendations`、`confidence_and_gaps`。
4. 老师可通过 API 和最小 UI 读取问卷分析报告，并能区分“分析完成”“部分成功”“进入 review queue”三种状态。
5. `Coordinator` 在 teacher chat 中可查询问卷报告，并在需要时走受控 handoff，而不是自由多 Agent 互聊。
6. 关键链路具有状态机、事件、回放与 fallback synthesis；失败不会直接污染 teacher memory。
7. 新增测试、文档与评测样例能覆盖 survey V1 纵向闭环。

## Non-Goals

- 不实现开放式多 Agent marketplace。
- 不在 V1 做学生级名单、风险画像写回与自动作业生成。
- 不引入新的外部编排系统或消息队列中间件。
- 不把 survey specialist agent 暴露为老师可随意安装/导入的“技能”。
- 不因为 survey V1 改写现有 exam / assignment / chat 主链行为。

## Execution Rules

每个任务执行时遵守同一微循环：

1. 先写或补最小失败测试。
2. 跑目标测试确认失败原因与任务目标一致。
3. 做最小实现，不顺手扩 scope。
4. 跑任务级验证命令。
5. 通过后立即提交一个小 commit。
6. 若任务跨后端/前端/文档三层，必须以后端契约先稳定，再接 UI。

---

## Phase A: Contracts and Runtime Slots

### Task 1: 建立 survey 领域入口、配置开关与路由骨架

**Files:**
- Create: `services/api/survey/__init__.py`
- Create: `services/api/survey/application.py`
- Create: `services/api/survey/deps.py`
- Create: `services/api/routes/survey_routes.py`
- Create: `services/api/wiring/survey_wiring.py`
- Modify: `services/api/api_models.py`
- Modify: `services/api/settings.py`
- Modify: `services/api/app_routes.py`
- Modify: `services/api/routes/__init__.py`
- Test: `tests/test_survey_types.py`
- Test: `tests/test_survey_routes.py`

**Steps:**
1. 在 `tests/test_survey_types.py` 中先写失败测试，固定新增 request/response 模型、feature flag accessor 和路由注册行为。
2. 在 `services/api/api_models.py` 中新增 survey V1 需要的最小模型：webhook ack、teacher report summary/detail、rerun request、review queue item summary。
3. 在 `services/api/settings.py` 中新增受控配置项：`SURVEY_ANALYSIS_ENABLED`、`SURVEY_WEBHOOK_SECRET`、`SURVEY_SHADOW_MODE`、`SURVEY_MAX_ATTACHMENT_BYTES`、`SURVEY_REVIEW_CONFIDENCE_FLOOR`。
4. 按 `exam/assignment` 现有风格建立 `services/api/survey/application.py` 与 `services/api/survey/deps.py`，先只保留空实现/最小代理函数。
5. 创建 `services/api/routes/survey_routes.py` 并在 `services/api/app_routes.py` 注册 survey router；路由前缀保持独立，不塞进现有 chat/teacher 路由文件。
6. 重新运行目标测试，确认类型和路由骨架稳定通过。

**Validation:**
- Run: `python3.13 -m pytest -q tests/test_survey_types.py tests/test_survey_routes.py`
- Expected: PASS。

**Acceptance:**
- 新 survey 能力已有独立 application/deps/routes/wiring 入口。
- 配置项与 API 契约已固定，后续任务不再反复改命名。

**Commit:**
```bash
git add services/api/api_models.py services/api/settings.py services/api/app_routes.py services/api/routes/__init__.py services/api/routes/survey_routes.py services/api/survey/__init__.py services/api/survey/application.py services/api/survey/deps.py services/api/wiring/survey_wiring.py tests/test_survey_types.py tests/test_survey_routes.py
git commit -m "feat(survey): add survey domain entrypoints and route skeleton"
```

### Task 2: 建立 survey 存储布局、job 仓储与状态机

**Files:**
- Create: `services/api/survey_repository.py`
- Create: `services/api/survey_job_state_machine.py`
- Modify: `services/api/paths.py`
- Modify: `services/api/job_repository.py`
- Test: `tests/test_survey_repository.py`
- Test: `tests/test_survey_job_state_machine.py`

**Steps:**
1. 先写 `tests/test_survey_repository.py` 与 `tests/test_survey_job_state_machine.py`，覆盖路径安全、原子写入、状态迁移与 review queue 写入。
2. 在 `services/api/paths.py` 增加 survey 专用路径 helpers：`survey_job_path()`、`survey_raw_payload_dir()`、`survey_bundle_path()`、`survey_report_path()`、`survey_review_queue_path()`。
3. 在 `services/api/job_repository.py` 里参照 upload/exam 模式补 `load_survey_job()` / `write_survey_job()`。
4. 新建 `services/api/survey_job_state_machine.py`，定义 survey V1 的后台状态：`webhook_received -> intake_validated -> normalized -> bundle_ready -> analysis_running -> analysis_ready -> teacher_notified | review | failed`。
5. 新建 `services/api/survey_repository.py` 封装 survey job、raw payload、bundle、report、review queue 的读写入口，避免后续业务服务直接拼路径。
6. 跑目标测试，确认 survey I/O 和状态机具备稳定契约。

**Validation:**
- Run: `python3.13 -m pytest -q tests/test_survey_repository.py tests/test_survey_job_state_machine.py`
- Expected: PASS。

**Acceptance:**
- survey 的文件系统布局和状态规则已经独立，不复用 chat/exam job 文件。
- 后续任何 survey 服务都通过 repository 访问存储。

**Commit:**
```bash
git add services/api/paths.py services/api/job_repository.py services/api/survey_repository.py services/api/survey_job_state_machine.py tests/test_survey_repository.py tests/test_survey_job_state_machine.py
git commit -m "feat(survey): add survey repository and state machine"
```

---

## Phase B: Intake and Background Job Flow

### Task 3: 实现 webhook intake、验签、幂等与入队

**Files:**
- Create: `services/api/survey_webhook_service.py`
- Modify: `services/api/survey/application.py`
- Modify: `services/api/survey/deps.py`
- Modify: `services/api/routes/survey_routes.py`
- Modify: `services/api/wiring/survey_wiring.py`
- Test: `tests/test_survey_webhook_service.py`
- Test: `tests/test_survey_webhook_routes.py`

**Steps:**
1. 在测试中先固定三类行为：签名正确可入队、重复 webhook 幂等返回、归属缺失/签名错误直接拒绝。
2. 在 `services/api/survey_webhook_service.py` 实现 intake 逻辑：验签、请求体落盘、幂等键生成、teacher/class 归属、附件元数据登记。
3. 在 `services/api/survey/application.py` / `deps.py` 接入 intake service，返回稳定 ack 响应，不在 webhook 路由里直接写业务逻辑。
4. 在 `services/api/routes/survey_routes.py` 暴露 provider webhook endpoint，并显式区分外部 webhook 与教师读取接口。
5. 通过 wiring 注入 queue enqueue 函数、repository、settings 与 diag logger。
6. 跑目标测试，确认 webhook path 的失败与成功输出稳定。

**Validation:**
- Run: `python3.13 -m pytest -q tests/test_survey_webhook_service.py tests/test_survey_webhook_routes.py`
- Expected: PASS。

**Acceptance:**
- Webhook 请求不会直接触发 LLM。
- Intake 成功后至少落下：job.json、raw payload、ingest metadata。

**Commit:**
```bash
git add services/api/survey_webhook_service.py services/api/survey/application.py services/api/survey/deps.py services/api/routes/survey_routes.py services/api/wiring/survey_wiring.py tests/test_survey_webhook_service.py tests/test_survey_webhook_routes.py
git commit -m "feat(survey): add webhook intake with signature and idempotency"
```

### Task 4: 把 survey job 接入现有 queue/runtime/worker 体系

**Files:**
- Create: `services/api/workers/survey_worker_service.py`
- Modify: `services/api/queue/queue_backend.py`
- Modify: `services/api/queue/queue_inline_backend.py`
- Modify: `services/api/queue/queue_backend_rq.py`
- Modify: `services/api/runtime/queue_runtime.py`
- Modify: `services/api/workers/rq_tasks.py`
- Modify: `services/api/wiring/worker_wiring.py`
- Test: `tests/test_survey_worker_service.py`
- Test: `tests/test_queue_runtime_types.py`

**Steps:**
1. 先在测试中为 queue protocol 增加 survey 方法断言，避免只改 inline 路径忘了 RQ 路径。
2. 给 `QueueBackend`、`InlineQueueBackend`、`RqQueueBackend` 增加 `enqueue_survey_job()` 与 `scan_pending_survey_jobs()`。
3. 在 `services/api/workers/survey_worker_service.py` 实现 scan / enqueue / process worker 逻辑，风格保持与 chat/exam/upload 一致。
4. 在 `services/api/workers/rq_tasks.py` 和 `services/api/runtime/queue_runtime.py` 中接通 survey runtime 方法。
5. 在 `services/api/wiring/worker_wiring.py` 中为 survey worker 注入 core、repository、orchestrator 占位依赖。
6. 跑目标测试，确保 inline 与 protocol 层先稳定，再继续后续 bundle/agent 逻辑。

**Validation:**
- Run: `python3.13 -m pytest -q tests/test_survey_worker_service.py tests/test_queue_runtime_types.py`
- Expected: PASS。

**Acceptance:**
- Survey job 可以像 upload/exam/chat 一样进入统一后台运行时。
- 新增 queue 方法不会破坏现有 protocol 与 runtime 类型测试。

**Commit:**
```bash
git add services/api/workers/survey_worker_service.py services/api/queue/queue_backend.py services/api/queue/queue_inline_backend.py services/api/queue/queue_backend_rq.py services/api/runtime/queue_runtime.py services/api/workers/rq_tasks.py services/api/wiring/worker_wiring.py tests/test_survey_worker_service.py tests/test_queue_runtime_types.py
git commit -m "feat(queue): wire survey jobs into runtime backends"
```

---

## Phase C: Evidence Pipeline

### Task 5: 定义 `survey_evidence_bundle` 并打通结构化 payload 归一化

**Files:**
- Create: `services/api/survey_bundle_models.py`
- Create: `services/api/survey_normalize_structured_service.py`
- Modify: `services/api/survey_repository.py`
- Modify: `services/api/survey/deps.py`
- Test: `tests/test_survey_bundle_models.py`
- Test: `tests/test_survey_normalize_structured_service.py`

**Steps:**
1. 先写 bundle 模型测试，固定 `survey_meta`、`audience_scope`、`question_summaries`、`group_breakdowns`、`free_text_signals`、`attachments`、`parse_confidence`、`missing_fields`、`provenance` 的结构约束。
2. 在 `services/api/survey_bundle_models.py` 用 Pydantic/dataclass 明确定义 bundle 与 question/group/text signal 子结构。
3. 在 `services/api/survey_normalize_structured_service.py` 把结构化问卷 payload 映射到 bundle；缺字段时只记录 `missing_fields`，不要直接抛异常。
4. 在 `services/api/survey_repository.py` 增加 bundle 持久化和版本化读写方法。
5. 通过 `services/api/survey/deps.py` 暴露 structured normalize 依赖，供 worker/orchestrator 调用。
6. 跑目标测试，确保 bundle 契约稳定再接非结构化报告解析。

**Validation:**
- Run: `python3.13 -m pytest -q tests/test_survey_bundle_models.py tests/test_survey_normalize_structured_service.py`
- Expected: PASS。

**Acceptance:**
- 系统能仅依赖结构化 payload 产出完整 bundle。
- bundle 是稳定 schema，而不是临时拼的 prompt 文本。

**Commit:**
```bash
git add services/api/survey_bundle_models.py services/api/survey_normalize_structured_service.py services/api/survey_repository.py services/api/survey/deps.py tests/test_survey_bundle_models.py tests/test_survey_normalize_structured_service.py
git commit -m "feat(survey): add evidence bundle schema and structured normalization"
```

### Task 6: 支持 PDF/截图/网页导出的解析与 partial bundle 合并

**Files:**
- Create: `services/api/survey_report_parse_service.py`
- Create: `services/api/survey_bundle_merge_service.py`
- Modify: `services/api/survey/deps.py`
- Modify: `services/api/upload_text_service.py`
- Test: `tests/test_survey_report_parse_service.py`
- Test: `tests/test_survey_bundle_merge_service.py`
- Test: `tests/test_survey_bundle_partial_confidence.py`

**Steps:**
1. 先写失败测试，覆盖 PDF 表格抽取不完整、截图 OCR 噪声、网页导出字段缺失时的 partial bundle 行为。
2. 在 `services/api/survey_report_parse_service.py` 统一封装非结构化输入解析：文本抽取、表格片段、统计摘要与附件 provenance。
3. 在 `services/api/survey_bundle_merge_service.py` 实现 structured / parsed bundle 合并，规则是“保留 provenance、累计 missing_fields、向下取最小 confidence”。
4. 只在 `services/api/upload_text_service.py` 做复用型小改动，不要把 survey 规则写死在通用 upload service 里。
5. 在 deps 中暴露 parse/merge 两个 service，供 worker 先后执行。
6. 跑目标测试，确认 partial bundle 会进入后续分析或 review queue，而不是一律失败。

**Validation:**
- Run: `python3.13 -m pytest -q tests/test_survey_report_parse_service.py tests/test_survey_bundle_merge_service.py tests/test_survey_bundle_partial_confidence.py`
- Expected: PASS。

**Acceptance:**
- 非结构化报告输入能稳定落到同一 bundle schema。
- 低质量解析结果仍可作为 partial bundle 进入后续决策。

**Commit:**
```bash
git add services/api/survey_report_parse_service.py services/api/survey_bundle_merge_service.py services/api/survey/deps.py services/api/upload_text_service.py tests/test_survey_report_parse_service.py tests/test_survey_bundle_merge_service.py tests/test_survey_bundle_partial_confidence.py
git commit -m "feat(survey): parse unstructured reports into partial evidence bundles"
```

### Task 7: 暴露 teacher 读取 bundle/report 的查询接口

**Files:**
- Create: `services/api/survey_report_service.py`
- Modify: `services/api/survey/application.py`
- Modify: `services/api/survey/deps.py`
- Modify: `services/api/routes/survey_routes.py`
- Modify: `services/api/wiring/survey_wiring.py`
- Test: `tests/test_survey_report_service.py`
- Test: `tests/test_survey_report_routes.py`

**Steps:**
1. 先写列表、详情、按教师过滤、按状态过滤、rerun 占位接口的失败测试。
2. 在 `services/api/survey_report_service.py` 封装 teacher 可见读模型：report summary、detail、bundle status、analysis status、review flags。
3. 在 application/deps 层补 `list_survey_reports()`、`get_survey_report()`、`rerun_survey_report()` 最小入口。
4. 在 `services/api/routes/survey_routes.py` 中新增 teacher 侧读取接口，例如 `/teacher/surveys/reports` 与 `/teacher/surveys/reports/{report_id}`。
5. 保持外部 webhook 路由与 teacher 查询路由分离，避免权限模型混杂。
6. 跑目标测试，确保老师端已经有稳定的读取契约，再接 specialist agent 与 UI。

**Validation:**
- Run: `python3.13 -m pytest -q tests/test_survey_report_service.py tests/test_survey_report_routes.py`
- Expected: PASS。

**Acceptance:**
- 老师可按 teacher_id 读取 survey 结果。
- API 契约已经能支撑最小前端列表/详情页。

**Commit:**
```bash
git add services/api/survey_report_service.py services/api/survey/application.py services/api/survey/deps.py services/api/routes/survey_routes.py services/api/wiring/survey_wiring.py tests/test_survey_report_service.py tests/test_survey_report_routes.py
git commit -m "feat(survey): add teacher report query APIs"
```

---

## Phase D: Specialist-Agent Subsystem

### Task 8: 建立 specialist agent registry 与 handoff contract

**Files:**
- Create: `services/api/specialist_agents/__init__.py`
- Create: `services/api/specialist_agents/contracts.py`
- Create: `services/api/specialist_agents/registry.py`
- Create: `services/api/specialist_agents/runtime.py`
- Test: `tests/test_specialist_agent_contracts.py`
- Test: `tests/test_specialist_agent_registry.py`

**Steps:**
1. 先用测试固定 registry 行为：注册 agent、按 artifact/task kind 查询、budget/takeover policy 暴露、未知 agent 失败方式。
2. 在 `contracts.py` 定义通用 handoff/request/response schema，包括 `handoff_id`、`from_agent`、`to_agent`、`task_kind`、`artifact_refs`、`goal`、`constraints`、`budget`、`return_schema`、`status`。
3. 在 `registry.py` 定义 specialist agent 声明结构：`agent_id`、`roles`、`accepted_artifacts`、`task_kinds`、`tool_allowlist`、`budgets`、`memory_policy`、`output_schema`、`evaluation_suite`。
4. 在 `runtime.py` 提供最小运行入口，约束所有 specialist agent 都通过同一接口执行，而不是各自发明调用方式。
5. 保持 registry 为内部受控配置面，不复用用户可见的 skills marketplace 叙事。
6. 跑目标测试，确认以后新增 specialist agent 是注册问题，不是架构重写问题。

**Validation:**
- Run: `python3.13 -m pytest -q tests/test_specialist_agent_contracts.py tests/test_specialist_agent_registry.py`
- Expected: PASS。

**Acceptance:**
- 新增 specialist agent 已有统一 contract。
- handoff 成为显式对象，而不是任意 dict。

**Commit:**
```bash
git add services/api/specialist_agents/__init__.py services/api/specialist_agents/contracts.py services/api/specialist_agents/registry.py services/api/specialist_agents/runtime.py tests/test_specialist_agent_contracts.py tests/test_specialist_agent_registry.py
git commit -m "feat(agents): add specialist agent registry and handoff contracts"
```

### Task 9: 实现 `Survey Analyst Agent` 与 `analysis_artifact` 输出

**Files:**
- Create: `services/api/specialist_agents/survey_analyst.py`
- Create: `services/api/survey_report_render_service.py`
- Create: `prompts/v1/teacher/agents/survey_analyst.md`
- Modify: `services/api/wiring/survey_wiring.py`
- Test: `tests/test_survey_analyst_agent.py`
- Test: `tests/test_survey_report_render_service.py`

**Steps:**
1. 先写失败测试，固定 `Survey Analyst Agent` 的输入、输出 schema 和 evidence 引用行为；至少要验证它不会输出学生级名单和自动动作计划。
2. 在 `prompts/v1/teacher/agents/survey_analyst.md` 写受控分析提示，强调只做班级洞察、教学建议、置信度与 gaps。
3. 在 `services/api/specialist_agents/survey_analyst.py` 中实现 agent：输入 `survey_evidence_bundle + teacher_context + task_goal`，输出 `analysis_artifact`。
4. 在 `services/api/survey_report_render_service.py` 将 artifact 渲染成老师可读 markdown / JSON 双形态，避免后续 UI 直接拼 LLM 原始输出。
5. 在 `services/api/wiring/survey_wiring.py` 中注入 `call_llm`、diag logger、teacher context builder、registry/runtime 依赖。
6. 跑目标测试，确认 specialist agent 与 report render 可以独立通过。

**Validation:**
- Run: `python3.13 -m pytest -q tests/test_survey_analyst_agent.py tests/test_survey_report_render_service.py`
- Expected: PASS。

**Acceptance:**
- Survey Analyst Agent 已能稳定产出 V1 所需 artifact。
- 报告渲染逻辑从 agent 本体解耦。

**Commit:**
```bash
git add services/api/specialist_agents/survey_analyst.py services/api/survey_report_render_service.py prompts/v1/teacher/agents/survey_analyst.md services/api/wiring/survey_wiring.py tests/test_survey_analyst_agent.py tests/test_survey_report_render_service.py
git commit -m "feat(survey): add survey analyst specialist agent"
```

### Task 10: 实现 survey orchestrator、delivery 与 review queue

**Files:**
- Create: `services/api/survey_orchestrator_service.py`
- Create: `services/api/survey_delivery_service.py`
- Create: `services/api/survey_review_queue_service.py`
- Modify: `services/api/workers/survey_worker_service.py`
- Modify: `services/api/survey_repository.py`
- Modify: `services/api/survey_job_state_machine.py`
- Test: `tests/test_survey_orchestrator_service.py`
- Test: `tests/test_survey_delivery_service.py`
- Test: `tests/test_survey_review_queue_service.py`

**Steps:**
1. 先写失败测试，覆盖 bundle_ready -> analysis_running -> analysis_ready -> teacher_notified 的正常流，以及 low-confidence -> review 的降级流。
2. 在 `services/api/survey_orchestrator_service.py` 编排 worker 内部阶段：load job -> normalize -> build handoff -> run Survey Analyst Agent -> render report -> persist output。
3. 在 `services/api/survey_delivery_service.py` 中实现交付层：保存 report artifact、更新 teacher 可见摘要、可选写入 teacher session 系统提示/通知占位。
4. 在 `services/api/survey_review_queue_service.py` 中把低置信度 bundle/report 放入 review queue，供后续人工处理或 rerun。
5. 更新 worker 和 state machine，使失败都经过受控 fallback，而不是把 traceback 暴露给老师。
6. 跑目标测试，确认 orchestrator 的成功/失败/partial 流都可回放。

**Validation:**
- Run: `python3.13 -m pytest -q tests/test_survey_orchestrator_service.py tests/test_survey_delivery_service.py tests/test_survey_review_queue_service.py`
- Expected: PASS。

**Acceptance:**
- survey job 已具备端到端后台闭环。
- review queue 能承接低置信度结果，不污染正式报告。

**Commit:**
```bash
git add services/api/survey_orchestrator_service.py services/api/survey_delivery_service.py services/api/survey_review_queue_service.py services/api/workers/survey_worker_service.py services/api/survey_repository.py services/api/survey_job_state_machine.py tests/test_survey_orchestrator_service.py tests/test_survey_delivery_service.py tests/test_survey_review_queue_service.py
git commit -m "feat(survey): orchestrate analysis delivery and review queue"
```

---

## Phase E: Coordinator and User-Facing Surfaces

### Task 11: 让 `Coordinator` 能查询 survey 报告并进行受控 handoff

**Files:**
- Modify: `services/common/tool_registry.py`
- Modify: `services/api/tool_dispatch_service.py`
- Modify: `services/api/agent_service.py`
- Modify: `services/api/chat_job_processing_service.py`
- Modify: `services/api/wiring/chat_wiring.py`
- Test: `tests/test_tool_dispatch_types.py`
- Test: `tests/test_survey_chat_handoff.py`
- Test: `tests/test_chat_route_flow.py`

**Steps:**
1. 先写失败测试，固定 teacher chat 可以列出 survey 报告、读取单份报告，并在需要 deeper analysis 时构造 handoff，而不是让多个 agent 自由对话。
2. 在 `services/common/tool_registry.py` 与 `services/api/tool_dispatch_service.py` 中新增 survey 工具：`survey.report.list`、`survey.report.get`、`survey.report.rerun`。
3. 在 `services/api/agent_service.py` 中增加受控 handoff 入口：遇到 survey artifact 查询或需要专门洞察时，通过 specialist agent runtime 执行，而不是直接把原始 bundle 丢给主对话模型。
4. 在 `services/api/chat_job_processing_service.py` 中把 survey handoff 结果纳入现有事件与 job 更新路径，保持 `Coordinator` 为唯一前台输出者。
5. 在 `services/api/wiring/chat_wiring.py` 中注入 registry、survey report service、orchestrator/read-model 依赖。
6. 跑目标测试，确认 survey 能力进入 chat，但不破坏原有 teacher workflow 解析与 SSE。

**Validation:**
- Run: `python3.13 -m pytest -q tests/test_tool_dispatch_types.py tests/test_survey_chat_handoff.py tests/test_chat_route_flow.py`
- Expected: PASS。

**Acceptance:**
- Teacher chat 能查询 survey 分析结果。
- handoff 是 Coordinator 内部执行策略，不是用户可见多 agent 切换。

**Commit:**
```bash
git add services/common/tool_registry.py services/api/tool_dispatch_service.py services/api/agent_service.py services/api/chat_job_processing_service.py services/api/wiring/chat_wiring.py tests/test_tool_dispatch_types.py tests/test_survey_chat_handoff.py tests/test_chat_route_flow.py
git commit -m "feat(chat): integrate survey reports into coordinator handoff flow"
```

### Task 12: 为老师端增加 survey 报告最小可见面

**Files:**
- Create: `frontend/apps/teacher/src/features/workbench/hooks/useSurveyReports.ts`
- Create: `frontend/apps/teacher/src/features/workbench/workflow/SurveyAnalysisSection.tsx`
- Create: `frontend/apps/teacher/src/features/workbench/workflow/SurveyAnalysisSection.test.tsx`
- Modify: `frontend/apps/teacher/src/features/workbench/tabs/WorkflowTab.tsx`
- Modify: `frontend/apps/teacher/src/features/workbench/teacherWorkbenchViewModel.ts`
- Modify: `frontend/apps/teacher/src/types/workflow.ts`
- Modify: `frontend/apps/shared/featureFlags.ts`

**Steps:**
1. 先写前端单测，固定空状态、loading、成功列表、low-confidence 标记、详情展开与 rerun 入口的基础展示。
2. 在 `useSurveyReports.ts` 中封装 teacher survey report list/detail 的 API 调用与轮询/刷新策略。
3. 在 `SurveyAnalysisSection.tsx` 中添加最小 UI：最新报告摘要、状态标签、进入 review queue 标记、详情跳转或展开。
4. 在 `WorkflowTab.tsx` / `teacherWorkbenchViewModel.ts` / `workflow.ts` 接入 survey section，不影响现有 assignment/exam workflow 展示。
5. 在 `featureFlags.ts` 中加前端 gating，允许 shadow mode 与 beta rollout。
6. 跑目标测试与 teacher build，确保最小 UI 先稳定，不追求一次性做复杂交互。

**Validation:**
- Run: `cd frontend && npm run test:unit -- apps/teacher/src/features/workbench/workflow/SurveyAnalysisSection.test.tsx`
- Run: `cd frontend && npm run build:teacher`
- Expected: PASS。

**Acceptance:**
- 老师端能看到 survey 报告列表/摘要。
- 前端由 feature flag 控制，不影响默认主界面稳定性。

**Commit:**
```bash
git add frontend/apps/teacher/src/features/workbench/hooks/useSurveyReports.ts frontend/apps/teacher/src/features/workbench/workflow/SurveyAnalysisSection.tsx frontend/apps/teacher/src/features/workbench/workflow/SurveyAnalysisSection.test.tsx frontend/apps/teacher/src/features/workbench/tabs/WorkflowTab.tsx frontend/apps/teacher/src/features/workbench/teacherWorkbenchViewModel.ts frontend/apps/teacher/src/types/workflow.ts frontend/apps/shared/featureFlags.ts
git commit -m "feat(teacher-ui): surface survey analysis reports in workbench"
```

---

## Phase F: Hardening, Evaluation, and Rollout

### Task 13: 增加 review queue、评测样例、文档与发布门禁

**Files:**
- Create: `docs/reference/survey-analysis-contract.md`
- Create: `scripts/survey_bundle_eval.py`
- Create: `tests/fixtures/surveys/structured/basic_payload.json`
- Create: `tests/fixtures/surveys/unstructured/pdf_report_excerpt.json`
- Create: `tests/fixtures/surveys/unstructured/screenshot_ocr_excerpt.json`
- Modify: `docs/INDEX.md`
- Modify: `services/api/settings.py`
- Test: `tests/test_docs_architecture_presence.py`
- Test: `tests/test_survey_bundle_eval.py`
- Test: `tests/test_ci_backend_hardening_workflow.py`

**Steps:**
1. 先写失败测试，固定文档存在、eval 脚本可跑、fixtures 可被加载。
2. 在 `docs/reference/survey-analysis-contract.md` 中写清 webhook、bundle、artifact、review queue、teacher report 的契约。
3. 准备最小评测样例 fixture，覆盖结构化、PDF、截图 OCR 三类输入。
4. 在 `scripts/survey_bundle_eval.py` 中实现轻量离线评测脚本，先输出 coverage、missing field rate、confidence buckets、artifact completeness。
5. 在 `services/api/settings.py` 中收尾 rollout 配置：shadow mode、beta allowlist、review threshold。
6. 更新 `docs/INDEX.md`，把设计文档与 survey contract 文档挂上索引；然后跑目标测试和一轮 survey 相关全量测试。

**Validation:**
- Run: `python3.13 -m pytest -q tests/test_docs_architecture_presence.py tests/test_survey_bundle_eval.py tests/test_ci_backend_hardening_workflow.py`
- Run: `python3.13 -m pytest -q tests/test_survey_*.py`
- Run: `python3.13 scripts/survey_bundle_eval.py --help`
- Expected: PASS。

**Acceptance:**
- survey V1 已具备离线评测和文档契约。
- 后续 V2/V3 扩展时可沿用同一评测框架与 artifact schema。

**Commit:**
```bash
git add docs/reference/survey-analysis-contract.md docs/INDEX.md scripts/survey_bundle_eval.py tests/fixtures/surveys services/api/settings.py tests/test_docs_architecture_presence.py tests/test_survey_bundle_eval.py tests/test_ci_backend_hardening_workflow.py
git commit -m "docs(survey): add contracts fixtures and rollout evaluation"
```

---

## Suggested Delivery Order

如果需要按最小可用闭环交付，推荐按以下里程碑推进：

1. `M1`: Task 1-4
   - 得到可入队、可运行、可持久化的 survey webhook 后台骨架
2. `M2`: Task 5-7
   - 得到稳定 `survey_evidence_bundle` 与 teacher 可查询 read model
3. `M3`: Task 8-10
   - 得到 specialist agent、analysis artifact、delivery 与 review queue
4. `M4`: Task 11-12
   - 得到 Coordinator chat 查询能力与 teacher workbench 最小 UI
5. `M5`: Task 13
   - 得到文档、评测和 rollout 门禁

## Final Verification

全部任务完成后，执行一次最小全链路验证：

**Backend targeted:**
```bash
python3.13 -m pytest -q \
  tests/test_survey_types.py \
  tests/test_survey_routes.py \
  tests/test_survey_repository.py \
  tests/test_survey_job_state_machine.py \
  tests/test_survey_webhook_service.py \
  tests/test_survey_webhook_routes.py \
  tests/test_survey_worker_service.py \
  tests/test_survey_bundle_models.py \
  tests/test_survey_normalize_structured_service.py \
  tests/test_survey_report_parse_service.py \
  tests/test_survey_bundle_merge_service.py \
  tests/test_survey_report_service.py \
  tests/test_survey_report_routes.py \
  tests/test_specialist_agent_contracts.py \
  tests/test_specialist_agent_registry.py \
  tests/test_survey_analyst_agent.py \
  tests/test_survey_report_render_service.py \
  tests/test_survey_orchestrator_service.py \
  tests/test_survey_delivery_service.py \
  tests/test_survey_review_queue_service.py \
  tests/test_survey_chat_handoff.py \
  tests/test_tool_dispatch_types.py
```

**Frontend targeted:**
```bash
cd frontend && npm run test:unit -- apps/teacher/src/features/workbench/workflow/SurveyAnalysisSection.test.tsx
cd frontend && npm run build:teacher
```

**Smoke / docs / eval:**
```bash
python3.13 scripts/survey_bundle_eval.py --help
python3.13 -m pytest -q tests/test_docs_architecture_presence.py
```

## Acceptance Criteria

- Webhook 到 report 的后台链路完整可回放。
- `survey_evidence_bundle` 与 `analysis_artifact` 契约稳定。
- 低置信度结果进入 review queue，而非直接失败或直接对老师展示不可靠结论。
- Coordinator 仍然是唯一前台 Agent，specialist agent 不直接抢占用户会话。
- 老师端能看到自动生成的问卷分析结果，并可在 chat 中查询同一批报告。
- survey V1 的新路径不破坏现有 exam / assignment / chat 主链。

