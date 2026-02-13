# 全栈代码审计发现报告（执行中）

日期: 2026-02-13  
分支: `codex/code-audit-batch1`  
状态: Phase 3 Batch 5 已完成（Task 13-15）

## Batch 1 覆盖范围（Task 1-3）

- Task 1（teacher persona）:
  - `services/api/teacher_persona_api_service.py`
  - `services/api/routes/teacher_persona_routes.py`
  - `services/api/wiring/teacher_wiring.py`
- Task 2（student persona）:
  - `services/api/student_persona_api_service.py`
  - `services/api/routes/student_persona_routes.py`
  - `services/api/wiring/student_wiring.py`
- Task 3（chat attachments）:
  - `services/api/chat_attachment_service.py`
  - `frontend/apps/shared/useChatAttachments.ts`
  - 入口链路补充核查：`services/api/routes/chat_routes.py`、`services/api/chat_start_service.py`

覆盖率（本批目标）:
- scanned_files / total_files = 10 / 10
- deep_audited_files / total_files = 10 / 10

---

## 发现列表（按严重级别）

### [H] `teacher_persona_routes.py:85` 与 `student_persona_routes.py:94` — 头像上传先整文件读入内存，再做大小校验，存在内存 DoS 风险

**问题描述**
- 路由层直接执行 `content = await file.read()`，会把上传文件整体加载到内存。
- 实际 2MB 限制在 service 的 `_validate_avatar_file()` 才执行，触发时已发生内存分配。
- 攻击者可反复提交超大文件，放大 API 进程内存压力，影响可用性。

**修复建议**
- 路由层改为流式保存（复用 `save_upload_file` 一类分块写入能力）。
- 在读取前做硬上限检查（`Content-Length` + 流式累计字节数双保险）。
- service 接口改为接收 `Path` 或流对象，避免 `bytes` 全量驻留内存。

---

### [H] `chat_attachment_service.py:187-209` — 多文件上传在后续文件超限时提前抛错，已写入的前序附件不会回滚，存在存储耗尽风险

**问题描述**
- 处理多文件时逐个落盘并累计 `total_written`。
- 当第 N 个文件触发总量限制时，仅删除当前 `attachment_dir` 后抛错；前 N-1 个附件仍保留在磁盘。
- 请求最终返回错误，客户端拿不到前序 `attachment_id`，这些文件变成“不可引用的垃圾数据”。
- 可通过重复构造“最后一个文件触发失败”的请求导致磁盘持续膨胀。

**修复建议**
- 实现事务式写入：
  - 先落到 request 级临时目录；
  - 全部校验通过后再原子迁移到正式附件目录。
- 或在任何异常路径统一清理本次请求已创建的全部 `attachment_dir`。

---

### [M] `teacher_persona_api_service.py:65-68`、`student_persona_api_service.py:70-73` — JSON 持久化缺少原子写入与并发锁，存在丢更新/文件损坏风险

**问题描述**
- 当前 `_write_json` 直接 `write_text` 覆盖文件。
- create/update/assign/activate/delete 等流程均是“读-改-写”，并发请求会产生 last-write-wins 丢更新。
- 在进程崩溃或中断场景下，直接覆盖写更容易留下部分写入文件。

**修复建议**
- 统一改为 `_atomic_write_json`（tmp + fsync + replace）。
- 对同一资源（teacher persona 文件、student profile 文件、assignment 文件）加文件锁或进程锁。
- 为并发更新补充回归测试（并发写同一 persona/profile）。

---

### [M] `teacher_persona_api_service.py:133-141`、`student_persona_api_service.py:242-250` — 关键文本字段仅做非空校验，缺少长度上限，存在资源耗尽隐患

**问题描述**
- `name`/`summary`/`style_rules`/`few_shot_examples` 无字符长度上限。
- 仅限制“列表项数量”，但单项可非常大，易导致 JSON 文件膨胀、序列化耗时上升、响应体增大。

**修复建议**
- 对字段引入 max length（例如 name<=80、summary<=500、rule/example 单条<=300）。
- 在路由层使用 Pydantic 模型做 schema 限制，拒绝超长输入。

---

### [L] `teacher_persona_api_service.py:58-62`、`student_persona_api_service.py:63-67` — JSON 解析异常静默吞掉，降低可观测性

**问题描述**
- 读取失败直接回 `{}`，不记录日志。
- 线上出现数据损坏时，行为会退化为“空数据”，排障困难。

**修复建议**
- 至少记录 warning 级日志（含文件路径、异常类型），避免静默退化。

---

## 本批未发现的问题（关键核查项）

- 未发现 teacher/student persona 的显性路径遍历漏洞（`resolve()` + parent 检查已覆盖核心路径）。
- 未发现通过路由直接绕过学生/教师身份作用域的明显越权路径（依赖 `resolve_teacher_scope` / `resolve_student_scope`）。

## 验证记录

- 基线测试（与 Task 1-3 相关）:
  - `python3 -m pytest tests/test_teacher_persona_api_service.py tests/test_student_persona_api_service.py tests/test_chat_attachment_flow.py -q`
  - 结果: `12 passed`

---

## Batch 2 覆盖范围（Task 4-6）

- Task 4（exam upload parse）:
  - `services/api/exam_upload_parse_service.py`
  - `services/api/handlers/exam_upload_handlers.py`
  - `services/api/routes/exam_upload_routes.py`
  - 入口链路补充核查：`services/api/exam_upload_start_service.py`、`services/api/exam_upload_job_service.py`、`services/api/exam_upload_api_service.py`、`services/api/exam_upload_confirm_service.py`、`services/api/upload_text_service.py`
- Task 5（agent runtime）:
  - `services/api/agent_service.py`
  - 关联核查：`services/api/skills/spec.py`、`services/api/skills/loader.py`
- Task 6（chat job processing）:
  - `services/api/chat_job_processing_service.py`
  - `services/api/chat_start_service.py`
  - 锁与队列补充核查：`services/api/chat_lock_service.py`、`services/api/job_repository.py`、`services/api/workers/chat_worker_service.py`

覆盖率（本批目标）:
- scanned_files / total_files = 15 / 15
- deep_audited_files / total_files = 15 / 15

## Batch 2 新增发现（按严重级别）

### [H] `exam_upload_routes.py:16-19`、`exam_upload_start_service.py:21-29`、`upload_text_service.py:40-65` — 考试上传链缺少服务端文件数量/类型/大小上限，存在磁盘耗尽与资源滥用风险

**问题描述**
- 路由层接收 `list[UploadFile]`，未限制每类文件最大数量。
- `start_exam_upload()` 直接调用 `_save_uploads()` 全量落盘，写入前未校验 MIME/后缀白名单、未校验单文件/总字节。
- `save_upload_file()` 仅分块复制，不做字节上限控制；攻击者可提交大量超大文件持续占用磁盘与 I/O。

**修复建议**
- 在路由或 service 入口增加硬限制：每类文件数量上限、单文件上限、请求总字节上限。
- 引入后缀+MIME 白名单（如 `pdf/png/jpg/jpeg/xls/xlsx/md/txt`），不在白名单直接拒绝。
- 将限额校验并入流式写入过程，达到阈值立即中止并清理当前请求临时文件。

---

### [H] `chat_lock_service.py:63-74`、`chat_job_processing_service.py:567-570`、`chat_worker_service.py:71-72` — claim 锁 TTL 回收会删除“仍存活进程”的锁，可能触发同一 job 并发重复处理

**问题描述**
- 锁文件已存在时，逻辑先检查 PID；即使 PID 存活，后续仍按 `mtime + ttl` 执行 `unlink` 回收。
- `chat_worker` 会周期性重扫并重新入队 `status in {"queued","processing"}` 的 job。
- 当单次处理耗时超过 TTL（默认 600s）时，其他 worker 可能回收锁并重新执行同一 job，导致重复写入会话/重复副作用。

**修复建议**
- 不能仅凭 TTL 删除“PID 仍存活”的锁；优先基于进程存活与 owner token 校验回收。
- 将 claim 锁改为持有型文件锁（`flock`/`fcntl` + 持续持有 fd），避免 `unlink + 重试` 的竞态窗口。
- 若保留 TTL，需配套心跳刷新与 owner 校验，且避免对 `processing` job 无条件重入队。

---

### [M] `agent_service.py:208-211`、`skills/spec.py:363-367`、`skills/loader.py:308-317` — 技能自定义 budget 可无上限覆盖全局 tool 限额，存在成本/时延放大风险

**问题描述**
- `agent_service` 会将 `skill_runtime.max_tool_rounds/max_tool_calls` 直接覆盖全局默认，仅做 `>=1` 下限保护。
- `SKILL.md`/spec 中 `budgets` 字段可被解析注入 runtime，当前解析链未设置硬上限。
- 导入或配置异常技能时，可把调用轮次/次数抬高到极端值，放大 LLM/tool 调用成本并拖慢 worker。

**修复建议**
- 对 runtime 生效值加硬上限（例如 `max_tool_rounds <= 8`、`max_tool_calls <= 24`）。
- 在 skill 解析阶段拒绝越界 budget，并记录可观测告警。
- 增加回归测试覆盖“超大 budget 被裁剪/拒绝”的行为。

## Batch 2 验证记录

- 相关测试:
  - `python3 -m pytest tests/test_exam_upload_start_service.py tests/test_exam_upload_parse_service.py tests/test_exam_upload_flow.py tests/test_agent_service.py tests/test_chat_lock_service.py tests/test_chat_lock_service_more.py tests/test_chat_job_processing_service.py tests/test_chat_start_service.py tests/test_job_repository_lockfile.py -q`
  - 结果: `66 passed, 2 skipped`

---

## Batch 3 覆盖范围（Task 7-9）

- Task 7（llm gateway）:
  - `llm_gateway.py`
- Task 8（chart executor / exam score processing）:
  - `services/api/chart_executor.py`
  - `services/api/exam_score_processing_service.py`
  - 沙箱与工具链补充核查：`services/api/chart_sandbox.py`、`services/api/chat_support_service.py`、`services/common/tool_registry.py`、`services/api/tool_dispatch_service.py`
- Task 9（assignment/upload service cluster）:
  - `services/api/upload_text_service.py`
  - `services/api/upload_llm_service.py`
  - `services/api/assignment_upload_confirm_service.py`
  - `services/api/assignment_upload_parse_service.py`
  - `services/api/assignment_upload_legacy_service.py`
  - 入口链路补充核查：`services/api/routes/assignment_upload_routes.py`、`services/api/assignment_upload_start_service.py`

覆盖率（本批目标）:
- scanned_files / total_files = 14 / 14
- deep_audited_files / total_files = 14 / 14

## Batch 3 新增发现（按严重级别）

### [H] `chart_executor.py:716-724`、`chart_sandbox.py:123-128`、`tool_registry.py:433-445` — `chart.exec` 默认走 `trusted` 执行档位，且该工具路径无法显式切到 `sandboxed`

**问题描述**
- `execute_chart_exec()` 在未传 `execution_profile` 时默认 `trusted`，仅 `sandboxed` 档位才执行代码模式扫描。
- `chart.exec` 工具 schema 未暴露 `execution_profile` 参数，LLM 工具调用默认无法切换到 `sandboxed`。
- 教师工具白名单允许 `chart.exec`（`chat_support_service.py:303-305`），导致模型生成的 Python 代码在较宽松档位执行（无代码扫描、无文件系统 guard 注入）。

**修复建议**
- 将 `chart.exec` 默认档位改为 `sandboxed`，仅在受控内部调用场景显式使用 `template/trusted`。
- 对 `chart.exec` 增加服务端强制策略（例如 role+来源校验），禁止外部请求绕过到 `trusted`。
- 即使非 `sandboxed`，也应保留最小危险模式拦截（至少阻断 `subprocess`/`os.system`/`exec`/`eval` 等）。

---

### [H] `assignment_upload_routes.py:20-21,46-47`、`assignment_upload_start_service.py:55-73`、`assignment_upload_legacy_service.py:68-89`、`upload_text_service.py:40-65` — 作业上传链缺少服务端文件数量/类型/大小上限，存在磁盘耗尽与资源滥用风险

**问题描述**
- 路由层接受 `list[UploadFile]` / `Optional[list[UploadFile]]`，未限制文件数量。
- start/legacy 两条上传路径均逐个保存文件，写入前未做 MIME/后缀白名单、单文件上限、请求总字节上限检查。
- `save_upload_file()` 仅分块复制，不执行最大字节阈值控制；可被大量或超大文件请求持续放大磁盘和 I/O 压力。

**修复建议**
- 在入口统一施加硬限制：每类文件数量、单文件大小、总上传大小上限。
- 建立后缀 + MIME 双白名单，不匹配即拒绝。
- 将限额校验下沉到流式保存过程，超限立即中断并清理当前请求已写入文件。

---

### [M] `llm_gateway.py:380-387`、`llm_gateway.py:470-477`、`llm_gateway.py:180-185,220-224,256-260,292-296` — 超时可被配置为 `None`（无限等待），上游挂起时会长期阻塞工作线程

**问题描述**
- `LLM_TIMEOUT_SEC` 和 `target_override.timeout_sec` 都支持 `0/none/inf/null` 转换为 `None`。
- 各 provider adapter 直接把该值传给 `requests.post(timeout=...)`；`None` 将导致无限等待。
- 在上游连接卡死或半开连接场景下，请求可能长期占用 worker，触发吞吐下降甚至队列堆积。

**修复建议**
- 禁止 `None` 超时，强制使用有限区间（例如 1-300 秒）并对非法值回退默认值。
- 区分 connect/read 超时（tuple），避免单侧无限等待。
- 增加监控与告警（超时分布、长尾请求、熔断计数），并对慢目标启用隔离/熔断。

## Batch 3 本批未发现的问题（关键核查项）

- `exam_score_processing_service.py` 未发现高置信度的数值安全/除零/NaN 传播漏洞；关键路径已有 `math.isfinite` 与类型兜底。
- `llm_gateway.py` 的重试策略具备次数上限与退避机制，未发现“无限重试”类缺陷（本批主要风险集中在 timeout 可被禁用）。

## Batch 3 验证记录

- 相关测试:
  - `python3 -m pytest tests/test_llm_gateway.py tests/test_llm_gateway_retry.py tests/test_chart_executor.py tests/test_chart_sandbox.py tests/test_chart_exec_tool.py tests/test_exam_score_processing.py tests/test_exam_score_processing_more.py tests/test_assignment_upload_start_service.py tests/test_assignment_upload_parse_service.py tests/test_assignment_upload_confirm_service.py tests/test_assignment_upload_legacy_service.py tests/test_upload_text_service.py tests/test_upload_text_service_more.py tests/test_upload_llm_service.py -q`
  - 结果: `221 passed`

---

## Task 10：Phase 1 汇总（Task 1-9）

### 严重级别统计

- 高危（H）: 6
- 中危（M）: 4
- 低危（L）: 1

### 优先修复建议（按顺序）

1. 上传链路限额缺失（exam + assignment，2 个 H）
2. chart 代码执行默认 `trusted`（1 个 H）
3. chat 锁 TTL 竞态导致重复处理（1 个 H）
4. persona/chat 附件内存与磁盘耗尽问题（2 个 H）
5. timeout/并发写入/budget 上限等中危稳态问题（4 个 M）

---

## Batch 4 覆盖范围（Task 10-12）

- Task 10（Phase 1 汇总）:
  - `docs/plans/2026-02-13-code-audit-findings.md`
- Task 11（Student App）:
  - `frontend/apps/student/src/App.tsx`
  - `frontend/apps/student/src/hooks/useStudentState.ts`
  - `frontend/apps/student/src/features/chat/useStudentSendFlow.ts`
  - `frontend/apps/student/src/features/chat/ChatComposer.tsx`
  - `frontend/apps/student/src/features/layout/StudentTopbar.tsx`
  - `frontend/apps/student/src/appTypes.ts`
  - 补充核查：`frontend/apps/student/src/features/chat/ChatMessages.tsx`、`frontend/apps/student/src/features/chat/SessionSidebarLearningSection.tsx`
- Task 12（Teacher App）:
  - `frontend/apps/teacher/src/App.tsx`
  - `frontend/apps/teacher/src/features/routing/RoutingPage.tsx`
  - `frontend/apps/teacher/src/features/workbench/hooks/useAssignmentWorkflow.ts`
  - `frontend/apps/teacher/src/features/chat/useTeacherChatApi.ts`
  - `frontend/apps/teacher/src/features/persona/TeacherPersonaManager.tsx`
  - `frontend/apps/teacher/src/features/persona/personaApi.ts`
  - 补充核查：`frontend/apps/teacher/src/features/chat/ChatMessages.tsx`、`frontend/apps/shared/markdown.ts`、`frontend/apps/teacher/src/features/routing/routingApi.ts`

覆盖率（本批目标）:
- scanned_files / total_files = 18 / 18
- deep_audited_files / total_files = 18 / 18

## Batch 4 新增发现（按严重级别）

### [M] `RoutingPage.tsx:775-779`、`shared/markdown.ts:182-193`、`useTeacherChatApi.ts:163-165`、`teacher ChatMessages.tsx:52` — `apiBase` 未做 URL/字符约束即拼接进 HTML 属性，存在 DOM XSS 注入面

**问题描述**
- 教师端允许在 UI 直接编辑 `apiBase`（`RoutingPage`）。
- `absolutizeChartImageUrls()` 用字符串替换把 `apiBase` 直接注入 `<img src>` / `<a href>`，未做 HTML 属性转义。
- 渲染链最终通过 `dangerouslySetInnerHTML` 落地；当 `apiBase` 包含引号与事件属性片段时，可破坏属性边界并注入事件处理器。

**修复建议**
- 对 `apiBase` 做严格 schema 校验（仅 `http/https`，拒绝引号、空白控制字符、javascript/data 协议）。
- 不要使用正则拼接 HTML；改为 DOM 级解析后 `setAttribute` 写入 URL。
- 在渲染层增加 defense-in-depth：对最终 HTML 再做一次属性级净化或 CSP 限制内联事件。

---

### [M] `student App.tsx:173-176,250-253,289-292`、`useStudentSendFlow.ts:188-190,207`、`useTeacherChatApi.ts:182-185,452-453,509-510`、`personaApi.ts:24-27` — 前端直接回显后端原始错误文本，存在内部实现细节泄露风险

**问题描述**
- 多处请求失败后直接读取 `res.text()`（或 `detail` 全量 JSON）并包装成 `Error` 回显到 UI。
- 若后端或网关返回调试栈、内部路径、SQL/OCR/路由细节，这些信息会直接暴露给终端用户。
- 当前模式缺少“用户可见错误”与“内部诊断错误”分层。

**修复建议**
- 建立统一错误映射：UI 仅展示通用文案（按错误码映射），详细信息写入日志/诊断通道。
- 对 `detail` 仅提取白名单字段（如 `code`, `message`），禁止原样透传对象或文本。
- 对 5xx 默认降级为固定提示，避免泄露内部实现细节。

---

### [L] `ChatComposer.tsx:88-92`、`StudentTopbar.tsx:235-247`、`TeacherPersonaManager.tsx:265-273`、`useAssignmentWorkflow.ts:546-567` — 上传前缺少客户端文件大小/数量预检，异常请求全部压到服务端

**问题描述**
- 聊天附件、学生/教师角色头像、作业上传在前端几乎仅依赖 `accept` 或无预检即直接发送。
- 没有统一的单文件大小、总大小、文件数量前置限制，用户在浏览器侧拿不到及时反馈。
- 在弱网或超大文件场景会放大失败重试与等待成本，也加剧后端压力。

**修复建议**
- 在前端统一实现上传预校验（数量、单文件大小、总大小、扩展名+MIME）。
- 校验失败时阻断上传并给出可执行提示（允许格式、大小上限、替代方案）。
- 与后端限额配置对齐，避免前后端规则漂移。

## Batch 4 本批未发现的问题（关键核查项）

- Student/Teacher 主要聊天渲染链已使用 `rehype-sanitize`，未发现直接渲染原始 Markdown HTML 的显性 XSS 点（本批风险集中在 `apiBase` 后处理拼接）。
- 未发现在前端代码中持久化 API token/密钥到 `localStorage` 的路径。

## Batch 4 验证记录

- 前端静态验证命令（尝试执行）:
  - `npm run lint`
  - `npm run typecheck`
- 结果:
  - 当前环境缺少前端依赖（`eslint`/`tsc` 命令不可用，`node_modules` 未安装），因此无法完成本批前端命令级验证。

---

## Task 14：Phase 2 汇总（Task 11-13）

### 严重级别统计

- 高危（H）: 0
- 中危（M）: 3
- 低危（L）: 1

### 优先修复建议（按顺序）

1. 修复 `apiBase` 注入 HTML 属性链路（DOM XSS 注入面）
2. 为聊天轮询加入请求超时与取消控制，避免挂死后停止轮询
3. 统一前端错误映射，禁止后端原始错误细节直出
4. 补齐上传前置校验（数量/大小/格式）并与后端限额保持一致

---

## Batch 5 覆盖范围（Task 13-15）

- Task 13（Shared Utils）:
  - `frontend/apps/shared/useChatAttachments.ts`
  - `frontend/apps/shared/markdown.ts`
  - `frontend/apps/shared/dialog.tsx`
  - `frontend/apps/shared/visibilityBackoffPolling.ts`
  - 调用链补充核查：`frontend/apps/student/src/hooks/useChatPolling.ts`、`frontend/apps/teacher/src/features/chat/useTeacherChatApi.ts`
- Task 14（Phase 2 汇总）:
  - `docs/plans/2026-02-13-code-audit-findings.md`
- Task 15（前后端类型一致性）:
  - `frontend/apps/teacher/src/appTypes.ts`
  - `frontend/apps/student/src/appTypes.ts`
  - `frontend/apps/teacher/src/features/routing/routingTypes.ts`
  - `services/api/api_models.py`
  - 补充核查：`services/api/student_ops_api_service.py`、`frontend/apps/student/src/hooks/useVerification.ts`

覆盖率（本批目标）:
- scanned_files / total_files = 11 / 11
- deep_audited_files / total_files = 11 / 11

## Batch 5 新增发现（按严重级别）

### [M] `visibilityBackoffPolling.ts:39,71-79,102`、`useChatPolling.ts:217`、`useTeacherChatApi.ts:507` — 轮询请求无超时/取消机制，单次挂起会卡死轮询状态机

**问题描述**
- 轮询器用 `inFlight` 防重入；仅在 `poll()` 返回后才在 `finally` 把 `inFlight` 复位。
- 学生/教师轮询回调都直接 `await fetch(...)`，没有 `AbortController` 或超时控制。
- 一旦某次请求长期挂起（连接半开、代理卡死），`inFlight` 持续为 `true`，后续 `run()` 全部短路，聊天状态可能长期停在“处理中”。

**修复建议**
- 为每次轮询请求强制超时（如 10-20 秒）并在超时后 `abort()`。
- 轮询器层支持“最大 in-flight 时长”熔断，超时自动复位并继续退避重试。
- 在回调签名中注入 `AbortSignal`，统一由轮询器管理取消与可见性切换。

---

### [L] `student appTypes.ts:120-125`、`student_ops_api_service.py:81-86`、`useVerification.ts:34-45` — 学生验证响应类型缺失 `candidates` 字段，前后端契约已漂移

**问题描述**
- 后端在同名冲突时返回 `candidates` 候选列表（含可用于前端二次确认的数据）。
- 前端 `VerifyResponse` 类型未声明该字段，`useVerification` 逻辑也仅显示固定文案“同名学生，请补充班级”。
- 结果是后端提供了可用信息但前端无法类型安全消费，契约一致性不足且影响后续扩展。

**修复建议**
- 补齐前端 `VerifyResponse` 类型定义（含 `candidates` 结构）。
- 在验证 UI 增加候选选择或辅助提示（至少展示候选班级列表）。
- 为该接口增加契约测试（OpenAPI schema 快照或前后端类型同步检查）。

## Batch 5 本批未发现的问题（关键核查项）

- `shared/markdown.ts` 现有 `rehype-sanitize` 主链可阻断常见 Markdown 内嵌 HTML 注入；未发现新的高置信度绕过点（已在 Batch 4 记录 `apiBase` 拼接链风险）。
- `routingTypes.ts` 与路由配置请求模型（`RoutingSimulateRequest`/`RoutingProposal*`）本批未发现高置信度字段名或可选性冲突。

## Batch 5 验证记录

- 后端与契约相关回归测试:
  - `python3 -m pytest tests/test_api_models.py tests/test_llm_routing_types.py tests/test_teacher_llm_routing_service.py tests/test_teacher_provider_registry_service.py tests/test_teacher_provider_registry_endpoints.py tests/test_llm_routing_endpoints.py tests/test_chat_attachment_flow.py -q`
  - 结果: `47 passed`

---

## Batch 6 覆盖范围（Task 16-18）

- Task 16（端点认证与授权审计）:
  - `services/api/routes/*.py`（共 30 个路由文件，88 个端点）
  - 认证链路核查：`services/api/app.py`、`services/api/auth_service.py`
  - 下游实现抽样/深挖：
    - 学生侧：`services/api/routes/student_history_routes.py`、`services/api/routes/student_profile_routes.py`、`services/api/routes/student_ops_routes.py`
    - 教师技能：`services/api/routes/skill_crud_routes.py`、`services/api/routes/skill_import_routes.py`、`services/api/teacher_skill_service.py`
    - 作业/考试：`services/api/routes/assignment_*_routes.py`、`services/api/routes/exam_*_routes.py`、`services/api/handlers/assignment_handlers.py`、`services/api/handlers/assignment_upload_handlers.py`、`services/api/exam_upload_api_service.py`、`services/api/exam_overview_service.py`、`services/api/exam_detail_service.py`
- Task 17（Phase 3 汇总）:
  - `docs/plans/2026-02-13-code-audit-findings.md`
- Task 18（Docker 配置审计）:
  - `docker-compose.yml`
  - `services/api/Dockerfile`
  - `services/mcp/Dockerfile`
  - `services/backup/Dockerfile`
  - `frontend/Dockerfile`
  - `frontend/Dockerfile.student`
  - `frontend/Dockerfile.teacher`

覆盖率（本批目标）:
- scanned_files / total_files = 21 / 21
- deep_audited_files / total_files = 21 / 21

## Batch 6 新增发现（按严重级别）

### [H] `student_history_routes.py:10-55`、`student_profile_routes.py:10-36`、`student_ops_routes.py:24-37` — 学生端多个接口直接信任请求里的 `student_id`，缺少 `resolve_student_scope` 绑定，存在 IDOR 越权

**问题描述**
- `/student/history/sessions`、`/student/session/view-state`（GET/PUT）、`/student/history/session`、`/student/profile/{student_id}`、`/student/profile/update`、`/student/submit` 都直接使用调用方提供的 `student_id`。
- 路由层未调用 `resolve_student_scope(...)`；下游实现仅校验非空，不校验“当前 principal 是否就是该 student”：
  - `session_history_api_service.py:32-87`
  - `student_profile_api_service.py:12-13`
  - `student_submit_service.py:21-57`
- 全局中间件仅完成 token 解析并注入 principal（`app.py:122-132`），不会按端点自动做角色/主体绑定。

**修复建议**
- 为上述学生端路由统一引入 `_scoped_student_id`（复用 `resolve_student_scope`）。
- 优先从 principal 派生 student_id；对外部传入的 student_id 仅允许 admin 场景并显式审计。
- 增加越权回归测试：学生 A token 访问/更新学生 B 数据应返回 `403 forbidden_student_scope`。

---

### [H] `skill_crud_routes.py:11-43`、`skill_import_routes.py:12-45`、`teacher_skill_service.py:75-183,571-614` — `/teacher/skills*` 缺少教师角色校验，低权限主体可执行教师技能管理与依赖安装

**问题描述**
- 技能 CRUD / import / deps / install-deps 端点未做 `require_principal(roles=...)` 或 `resolve_teacher_scope`。
- 下游 `teacher_skill_service` 直接落盘到 `TEACHER_SKILLS_DIR`，并允许触发 `pip install`（`install_skill_dependencies`）。
- 在“有 token 但非 teacher”的情况下（例如 student token），可调用教师技能管理接口，属于权限边界突破。

**修复建议**
- 在 `/teacher/skills*` 路由统一强制 `teacher/admin` 角色校验。
- 将技能存储改为按 teacher scope 隔离目录（至少按 teacher_id 分层），避免共享命名空间。
- 对 `install-deps` 增加更高权限门槛与审计日志（操作者、包名、来源）。

---

### [H] `assignment_*_routes.py` 与 `exam_*_routes.py`（如 `assignment_listing_routes.py:17-38`、`assignment_upload_routes.py:13-79`、`assignment_generation_routes.py:11-67`、`exam_query_routes.py:11-42`、`exam_upload_routes.py:11-48`）— 作业/考试敏感端点缺少角色边界，任意已认证主体可读写教师侧数据

**问题描述**
- 作业链路中包含明显教师语义端点（如 `/teacher/assignment/progress`、上传/生成/确认）但未做教师角色校验。
- 考试链路（列表、分析、学生明细、上传草稿保存/确认）同样无角色约束。
- 下游处理层也未补充 principal 校验（示例：`assignment_handlers.py:35-127`、`assignment_upload_handlers.py:37-135`、`exam_upload_api_service.py:51-174`、`exam_overview_service.py:283-443`、`exam_detail_service.py:23-200`）。

**修复建议**
- 建立统一端点访问矩阵：
  - teacher-only：考试上传/确认、作业上传/生成/进度、全班分析。
  - student-only：`assignment/today`（且必须 `resolve_student_scope`）。
  - admin：仅在显式参数+审计下可跨主体访问。
- 对 job_id 类接口（upload status/draft/confirm）绑定 owner（teacher_id/student_id）并在读取时强制校验 owner。

---

### [M] `docker-compose.yml:14,25,76,98,103,107` — 生产不安全默认值：认证默认关闭 + Redis 默认弱口令并暴露宿主端口

**问题描述**
- `AUTH_REQUIRED=${AUTH_REQUIRED:-0}` 使认证默认关闭。
- `REDIS_PASSWORD` 使用固定默认值 `physics_edu_2026`，且同时将 Redis 暴露到宿主机端口（`${REDIS_PORT:-6379}:6379`）。
- 若直接以默认 compose 启动到可达网络，存在未授权访问和弱口令滥用风险。

**修复建议**
- 生产配置强制 `AUTH_REQUIRED=1`，缺失关键 secret 时启动失败（fail-fast）。
- 移除 Redis 对宿主机端口暴露（仅内部网络可达），或至少改为仅绑定 `127.0.0.1`。
- 禁止默认弱口令；要求通过 secret/env 显式注入强口令。

---

### [M] `docker-compose.yml:149-255` — 备份与 qdrant 服务缺少资源限制/健康检查，故障隔离能力不足

**问题描述**
- `backup_scheduler` / `backup_daily_full` / `backup_verify_weekly` 未配置 `mem_limit`、`cpus`、`healthcheck`。
- `qdrant` 服务也缺少 `restart`、`healthcheck` 与资源约束。
- 在备份脚本异常或存储抖动时，可能导致资源争抢并降低主业务稳定性。

**修复建议**
- 为上述服务补齐 `mem_limit`、`cpus`、`healthcheck`、`restart` 策略。
- 备份任务增加超时/失败退避，避免无限循环高频失败重试。

---

### [L] `frontend/Dockerfile:13-17` — 通用前端镜像未切换非 root 用户运行 Nginx

**问题描述**
- `frontend/Dockerfile` 最终阶段未显式 `USER nginx`，默认以 root 运行 Nginx。
- `frontend/Dockerfile.student` 与 `frontend/Dockerfile.teacher` 已显式降权（`USER nginx`），该通用文件与其策略不一致。

**修复建议**
- 参照 student/teacher Dockerfile，补齐目录权限调整并显式 `USER nginx`。
- 在 CI 增加 Dockerfile 安全基线检查（禁止 root runtime）。

## Batch 6 本批未发现的问题（关键核查项）

- 教师核心路由（history/memory/llm-routing/provider/persona）已统一使用 `scoped_teacher_id`/`scoped_payload_teacher_id` 进行主体绑定，本批未发现高置信越权。
- 聊天主链路 `chat`/`chat_start` 通过 `bind_chat_request_to_principal` 绑定角色主体，附件接口也对 teacher/student scope 做了显式绑定。
- `services/api/Dockerfile`、`services/mcp/Dockerfile`、`services/backup/Dockerfile`、`frontend/Dockerfile.student`、`frontend/Dockerfile.teacher` 均已切换非 root 运行。

## Batch 6 验证记录

- 路由与认证相关回归测试:
  - `python3 -m pytest tests/test_auth_service.py tests/test_student_routes.py tests/test_teacher_routes.py tests/test_skill_routes.py tests/test_skills_endpoint.py tests/test_assignment_routes.py tests/test_exam_routes.py tests/test_exam_endpoints.py tests/test_misc_routes.py tests/test_app_routes_registration.py -q`
  - 结果: `58 passed, 1 warning`

---

## Task 17：Phase 3 汇总（Task 15-16）

### 严重级别统计

- 高危（H）: 3
- 中危（M）: 1
- 低危（L）: 1

### 优先修复建议（按顺序）

1. 修复学生侧 `student_id` IDOR（历史/画像/提交接口统一 scope 绑定）
2. 修复 `/teacher/skills*` 角色绕过（teacher/admin 强制校验 + 高风险操作审计）
3. 收紧作业/考试端点角色边界并为 job_id 查询加入 owner 校验
4. 回补前后端验证契约漂移（`VerifyResponse.candidates`）并增加契约测试

---

## Batch 7 覆盖范围（Task 19-21）

- Task 19（CI Workflows 审计）:
  - `.github/workflows/ci.yml`
  - `.github/workflows/docker.yml`
  - `.github/workflows/teacher-e2e.yml`
  - `.github/workflows/mobile-session-menu-e2e.yml`
- Task 20（Scripts 审计）:
  - `scripts/grade_submission.py`
  - `scripts/ocr_review_apply.py`
  - `scripts/backup/run_backup.sh`
  - `scripts/backup/common.sh`
  - `scripts/backup/verify_restore.sh`
  - 调用链补充核查：`services/api/student_submit_service.py`
- Task 21（Phase 4 汇总）:
  - `docs/plans/2026-02-13-code-audit-findings.md`

覆盖率（本批目标）:
- scanned_files / total_files = 11 / 11
- deep_audited_files / total_files = 11 / 11

## Batch 7 新增发现（按严重级别）

### [H] `scripts/grade_submission.py:452,473,479,714`、`services/api/student_submit_service.py:44-45,51-53` — `student_id/assignment_id` 未做路径约束即参与路径拼接，存在路径穿越写入风险

**问题描述**
- `grade_submission.py` 直接使用外部参数构造路径：
  - `Path(args.out_dir) / args.student_id / ...`
  - `Path(args.out_dir) / assignment_id / args.student_id / ...`
  - `Path("data/assignments") / assignment_id / "questions.csv"`
  - `Path("data/student_profiles") / f"{args.student_id}.json"`
- `student_submit_service.py` 会把请求中的 `student_id` 与 `assignment_id` 原样作为脚本参数传入（无 sanitize）。
- 当传入 `../`、绝对路径片段或分隔符变体时，可能导致读取/写入越出预期目录边界（覆盖 profile 或落盘到非预期位置）。

**修复建议**
- 对 `student_id`、`assignment_id` 强制使用安全 ID 规范（白名单字符 + 长度上限）。
- 在脚本内统一做 `resolve()` + parent 校验；任何越界路径直接拒绝。
- 将路径构造收敛到安全 helper（例如 `safe_student_id/safe_assignment_id`），并补充穿越回归测试。

---

### [M] `.github/workflows/ci.yml`、`.github/workflows/docker.yml`、`.github/workflows/teacher-e2e.yml`、`.github/workflows/mobile-session-menu-e2e.yml` — 第三方 GitHub Action 均按可变 tag 引用，未做 SHA pin

**问题描述**
- 多个 workflow 使用 `actions/checkout@v4`、`actions/setup-node@v4`、`actions/setup-python@v5`、`docker/*@v3-v6`、`actions/upload-artifact@v4` 等 tag 形式引用。
- tag 可随上游发布移动，供应链基线不可复现；发生上游账号/发布链路事件时，存在被动引入恶意变更风险。

**修复建议**
- 将关键第三方 action 固定到 commit SHA（可保留注释说明对应语义版本）。
- 配置自动化依赖更新（Dependabot/Renovate）定期滚动 SHA。
- 对高权限 workflow（如 `docker.yml` 的 `packages: write`）优先完成 SHA pin。

## Batch 7 本批未发现的问题（关键核查项）

- `docker.yml` 已对 `workflow_run` 做成功态与 `main` 分支门禁，未发现“PR 直接触发发布”类高置信度风险。
- 本批审计的 backup 脚本未发现高置信度命令注入点（关键命令参数均为引用传参，`target` 有白名单校验）。
- `ocr_review_apply.py` 未发现高置信度远程命令执行路径；主要风险仍集中在其输入来源可信边界管理。

## Batch 7 验证记录

- Workflow 与脚本相关回归测试:
  - `python3 -m pytest tests/test_docker_publish_workflow.py tests/test_ci_workflow_quality.py tests/test_ci_backend_hardening_workflow.py tests/test_ci_smoke_e2e_workflow.py tests/test_student_submit_service.py -q`
  - 结果: `12 passed`

---

## Task 21：Phase 4 汇总（Task 18-20）

### 严重级别统计

- 高危（H）: 1
- 中危（M）: 3
- 低危（L）: 1

### 优先修复建议（按顺序）

1. 修复 `grade_submission` 路径穿越（`student_id/assignment_id` 全链路 sanitize + 路径边界校验）
2. 收紧生产默认安全配置（`AUTH_REQUIRED=1`、去除 Redis 弱口令默认值与对外暴露）
3. 将 CI/CD 第三方 action 全量改为 SHA pin，优先 `docker.yml`
4. 为 backup/qdrant 补齐资源限制与 healthcheck；统一前端镜像非 root 运行策略

---

## Batch 8 覆盖范围（Task 22-23）

- Task 22（全局性能与健壮性扫描）:
  - `services/api/rate_limit.py`
  - `services/api/routes/assignment_listing_routes.py`
  - `services/api/routes/exam_query_routes.py`
  - `services/api/assignment_catalog_service.py`
  - `services/api/exam_catalog_service.py`
  - `services/api/content_catalog_service.py`
  - `llm_gateway.py`
- Task 23（最终汇总）:
  - `docs/plans/2026-02-13-code-audit-findings.md`

覆盖率（本批目标）:
- scanned_files / total_files = 7 / 7
- deep_audited_files / total_files = 7 / 7

## Batch 8 新增发现（按严重级别）

### [M] `services/api/rate_limit.py:20,24-27,41-43,52` — 速率限制桶按客户端 key 无界增长，且直接信任 `X-Forwarded-For`，存在内存放大风险

**问题描述**
- `_buckets` 以客户端 key 为索引永久保留，窗口过期后仅清空时间戳，不删除空桶。
- key 优先取请求头 `X-Forwarded-For`，缺少可信代理校验；攻击者可构造大量伪造 IP 值制造海量桶。
- 结果是内存占用随伪造 key 数量持续增长，形成低成本 DoS 面。

**修复建议**
- 在桶清空后删除空 key；为 `_buckets` 增加全局上限与淘汰策略（LRU/TTL）。
- 仅在可信反向代理链路下读取 `X-Forwarded-For`，否则使用 `request.client.host`。
- 为异常 key 基数设置监控告警（每分钟新增 key 数、总桶数）。

---

### [M] `services/api/routes/assignment_listing_routes.py:13-15`、`services/api/routes/exam_query_routes.py:11-13`、`services/api/assignment_catalog_service.py:89-121`、`services/api/exam_catalog_service.py:14-38` — 列表接口缺少分页/上限，目录规模扩大时响应与 I/O 成本线性失控

**问题描述**
- `/assignments` 与 `/exams` 不接受 `limit/offset(cursor)` 参数，服务端遍历目录后返回全量列表。
- 当作业/考试目录增长到高基数时，请求延迟、内存与序列化成本将线性上升，易产生长尾抖动。
- 当前实现也缺少结果大小保护（如最大返回条数），对批量抓取与误调用不够稳健。

**修复建议**
- 为列表接口引入分页参数（`limit`、`cursor/offset`）并设置服务端硬上限（例如 `limit<=100`）。
- 默认仅返回最近 N 条（按 `updated_at`/`generated_at` 排序），提供显式翻页获取历史数据。
- 增加分页契约测试与性能基线测试（大目录下 p95 响应时间）。

## Batch 8 本批未发现的问题（关键核查项）

- 本批扫描范围内未发现新的“HTTP 外呼缺失 timeout”高置信问题（`llm_gateway.py` 的 timeout 问题已在 Batch 3 记录）。
- 未发现新的“全局缓存无上限且可外部直接放大”的高置信问题（除本批已记录的 rate-limit 桶增长）。
- `content_catalog_service.py` 现阶段列表规模预期较小，本批未记录高置信性能缺陷（建议后续与业务规模阈值联动评估）。

## Batch 8 验证记录

- 性能相关模块回归测试:
  - `python3 -m pytest tests/test_rate_limit.py tests/test_assignment_catalog_service.py tests/test_exam_catalog_service.py tests/test_misc_routes.py -q`
  - 结果: `19 passed`

---

## Task 23：最终汇总报告

### 全量严重级别统计（Phase 1-5）

- 高危（H）: 10
- 中危（M）: 13
- 低危（L）: 4

### 按优先级的修复工作包（含粗略工作量）

1. P0（1-2 天）: 访问控制与身份作用域修复  
   覆盖学生 IDOR、`/teacher/skills*` 角色校验、作业/考试端点角色边界与 job owner 绑定。
2. P0（0.5-1 天）: 上传/脚本路径与资源滥用防护  
   覆盖 `grade_submission` 路径穿越、上传链路大小/数量/类型限额与失败回滚。
3. P1（0.5-1 天）: 运行时稳定性与可用性  
   覆盖 rate-limit 桶无界增长、轮询无超时、chat 锁 TTL 竞态、LLM timeout 禁用。
4. P1（0.5-1 天）: 配置与供应链基线  
   覆盖 Docker 生产默认安全项、CI action SHA pin、backup/qdrant 资源与健康检查。
5. P2（0.5 天）: 契约与前端稳态改进  
   覆盖 `VerifyResponse.candidates` 契约漂移、前端错误映射与上传前置校验。

### 交付状态

- `docs/plans/2026-02-13-code-audit-findings.md` 已完成 Phase 1-5 审计记录与分阶段汇总。
- 已进入修复提交阶段，按 P0 → P1 → P2 顺序持续修复并回归验证。
- 已推送修复提交：
  - `1f44f64` `fix(security): harden frontend api base/errors and pin ci actions`
  - `8a1e549` `fix(security): cap skill budgets and harden backup services baseline`

---

## 修复进展（2026-02-13）

### 已完成（P0）

1. 学生身份作用域越权（IDOR）修复  
   - 修复点：`/student/history/*`、`/student/profile/*`、`/student/submit` 统一接入 `resolve_student_scope`。  
   - 涉及文件：`services/api/routes/student_history_routes.py`、`services/api/routes/student_profile_routes.py`、`services/api/routes/student_ops_routes.py`。  
   - 验证：新增 `tests/test_security_auth_hardening.py` 跨学生访问拒绝用例并通过。

2. `/teacher/skills*` 角色绕过修复  
   - 修复点：对 create/update/delete/import/preview/deps/install-deps 路由增加 `require_principal(roles=("teacher","admin"))`。  
   - 涉及文件：`services/api/routes/skill_crud_routes.py`、`services/api/routes/skill_import_routes.py`。  
   - 验证：新增 `tests/test_security_auth_hardening.py` 学生角色拒绝访问用例并通过。

3. `grade_submission` 路径穿越修复  
   - 修复点：`student_id/assignment_id` 白名单校验，`resolve_under(...)` 边界校验，关键路径统一落在受控根目录下。  
   - 同时在 `student_submit_service` 增加 `student_id/assignment_id` 前置校验，拒绝非法 token。  
   - 涉及文件：`scripts/grade_submission.py`、`services/api/student_submit_service.py`。  
   - 验证：新增 `tests/test_grade_submission_security.py`、扩展 `tests/test_student_submit_service.py` 穿越拒绝用例并通过。

4. `chat_attachment` 失败回滚修复  
   - 修复点：上传处理加入请求级事务清理；任一异常触发时统一清理本次请求已创建的全部 `attachment_dir`。  
   - 涉及文件：`services/api/chat_attachment_service.py`。  
   - 验证：新增 `tests/test_chat_attachment_service.py`，覆盖“后续文件超限导致失败时前序目录必须回滚”。

5. assignment/exam 上传链路限额修复  
   - 修复点：在 `assignment_upload_start_service`、`assignment_upload_legacy_service`、`exam_upload_start_service` 增加服务端硬限制：  
     - 每字段文件数量上限（20）  
     - 单文件大小上限（20MB）  
     - 单次请求总上传上限（80MB）  
     - 扩展名白名单校验  
   - 修复点补充：start 类型异步任务在上传阶段失败时清理整个 job 目录，避免垃圾落盘。  
   - 涉及文件：`services/api/assignment_upload_start_service.py`、`services/api/assignment_upload_legacy_service.py`、`services/api/exam_upload_start_service.py`。  
   - 验证：扩展 `tests/test_assignment_upload_start_service.py`、`tests/test_assignment_upload_legacy_service.py`、`tests/test_exam_upload_start_service.py` 非法后缀拒绝用例并通过。

6. assignment/exam 角色边界与 upload job owner 绑定修复  
   - 修复点（角色边界）：对 assignment/exam 教师侧敏感端点统一增加 `require_principal(roles=("teacher","admin"))`，并将 `assignment/today` 收敛为学生作用域（`resolve_student_scope`）。  
   - 修复点（owner 绑定）：  
     - assignment/exam upload start 记录 `teacher_id` 到 job；  
     - status/draft/save/confirm 读取 `job_id` 时强制执行 `enforce_upload_job_access`，拒绝跨教师访问。  
   - 涉及文件：`services/api/routes/assignment_listing_routes.py`、`services/api/routes/assignment_generation_routes.py`、`services/api/routes/assignment_upload_routes.py`、`services/api/routes/assignment_delivery_routes.py`、`services/api/routes/exam_query_routes.py`、`services/api/routes/exam_upload_routes.py`、`services/api/assignment_upload_start_service.py`、`services/api/exam_upload_start_service.py`、`services/api/assignment_upload_query_service.py`、`services/api/assignment_upload_draft_save_service.py`、`services/api/handlers/assignment_upload_handlers.py`、`services/api/exam_upload_api_service.py`、`services/api/auth_service.py`。  
   - 验证：扩展 `tests/test_security_auth_hardening.py`（student 访问 teacher 端点拒绝、assignment/exam job 跨教师访问拒绝）并通过。

7. P1：rate-limit 桶增长与 assignment/exam 列表分页上限修复  
   - 修复点（rate-limit）：  
     - 增加桶自动回收（窗口外空桶清理 + 陈旧桶扫除）；  
     - 增加全局桶上限（`RATE_LIMIT_MAX_BUCKETS`）与基于最近访问时间的淘汰；  
     - `X-Forwarded-For` 默认不信任，仅在显式开启并满足可信代理条件时使用。  
   - 修复点（列表分页）：  
     - `/assignments` 与 `/exams` 增加 `limit/cursor` 参数；  
     - 服务端硬上限 `limit<=100`，返回 `total/has_more/next_cursor` 分页元数据。  
   - 涉及文件：`services/api/rate_limit.py`、`services/api/assignment_catalog_service.py`、`services/api/exam_catalog_service.py`、`services/api/routes/assignment_listing_routes.py`、`services/api/routes/exam_query_routes.py`、`services/api/assignment/application.py`、`services/api/exam/application.py`、`services/api/assignment/deps.py`、`services/api/exam/deps.py`、`services/api/handlers/assignment_handlers.py`、`services/api/wiring/assignment_wiring.py`、`services/api/context_application_facade.py`。  
   - 验证：扩展 `tests/test_rate_limit.py`、`tests/test_assignment_catalog_service.py`、`tests/test_exam_catalog_service.py` 并通过。

8. P1/P2：前端稳态与供应链基线修复（Batch C）  
   - 修复点（前端）：  
     - 新增 `frontend/apps/shared/apiBase.ts`，对 `apiBase` 做 `http/https`、危险字符、凭据字段约束；  
     - `shared/markdown.ts` 的 `absolutizeChartImageUrls` 改用安全 `normalizeApiBase`；  
     - 新增 `frontend/apps/shared/errorMessage.ts`，统一错误码映射与敏感细节过滤，避免直接回显后端原始错误文本。  
   - 修复点（CI/容器）：  
     - `.github/workflows/ci.yml`、`.github/workflows/docker.yml`、`.github/workflows/teacher-e2e.yml`、`.github/workflows/mobile-session-menu-e2e.yml` 第三方 Action 全量 SHA pin；  
     - `docker-compose.yml` 收紧默认：`AUTH_REQUIRED=1`、`REDIS_PASSWORD` 必填、Redis 端口仅本机绑定；  
     - `frontend/Dockerfile` 切换 `USER nginx` 非 root 运行。  
   - 涉及文件：`frontend/apps/shared/apiBase.ts`、`frontend/apps/shared/errorMessage.ts`、`frontend/apps/shared/markdown.ts`、`frontend/apps/student/src/hooks/useStudentState.ts`、`frontend/apps/teacher/src/features/chat/useTeacherChatApi.ts`、`frontend/apps/teacher/src/features/routing/routingApi.ts`、`frontend/apps/teacher/src/features/persona/personaApi.ts`、`.github/workflows/ci.yml`、`.github/workflows/docker.yml`、`.github/workflows/teacher-e2e.yml`、`.github/workflows/mobile-session-menu-e2e.yml`、`docker-compose.yml`、`frontend/Dockerfile` 等。  
   - 验证：新增 `tests/test_batch_c_frontend_security_hardening.py`、`tests/test_ci_actions_sha_pin.py`、`tests/test_docker_security_baseline.py` 并通过。

9. P1：技能预算上限与 backup/qdrant 运行时基线补齐  
   - 修复点（技能预算）：`services/api/agent_service.py` 中 skill runtime 的 `max_tool_rounds/max_tool_calls` 仅允许收紧全局上限，禁止放大预算。  
   - 修复点（运维基线）：`docker-compose.yml` 为 `backup_scheduler`、`backup_daily_full`、`backup_verify_weekly`、`qdrant` 补齐 `mem_limit`、`cpus`、`healthcheck`，并为 `qdrant` 增加 `restart`。  
   - 涉及文件：`services/api/agent_service.py`、`docker-compose.yml`。  
   - 验证：扩展 `tests/test_agent_service.py`、`tests/test_docker_security_baseline.py` 并通过。

10. P1：chat claim 锁竞态与 owner 校验加固  
   - 修复点：  
     - `services/api/chat_lock_service.py` 增加锁 owner token，`release_lockfile` 仅在 owner 匹配时删除锁文件；  
     - 增加进程内持有态注册（同进程重入直接拒绝）；  
     - 在“锁文件已存在”路径加入非阻塞 `flock` 探测，避免在活跃持有期误回收锁文件。  
   - 涉及文件：`services/api/chat_lock_service.py`。  
   - 验证：扩展 `tests/test_chat_lock_service.py`（owner 写入/owner 不匹配保护）并通过；`tests/test_chat_lock_service_more.py`、`tests/test_job_repository_lockfile.py`、`tests/test_chat_job_processing_service.py` 回归通过。

11. P2：学生验证契约漂移修复（`candidates`）  
   - 修复点：  
     - `frontend/apps/student/src/appTypes.ts` 增加 `StudentVerifyCandidate`，并在 `VerifyResponse` / `StudentIdentifyResponse` 显式声明 `candidates`；  
     - `frontend/apps/student/src/hooks/useVerification.ts` 增加同名冲突候选班级提示（从后端 `candidates` 聚合展示）。  
   - 涉及文件：`frontend/apps/student/src/appTypes.ts`、`frontend/apps/student/src/hooks/useVerification.ts`。  
   - 验证：新增 `tests/test_student_verify_contract_drift.py` 并通过；`frontend` TypeScript typecheck 通过。

12. P2：前端上传前置预检补齐（头像/附件/作业上传）  
   - 修复点：  
     - 新增 `frontend/apps/shared/uploadValidation.ts`，统一文件数量/单文件大小/总大小/后缀校验逻辑；  
     - `frontend/apps/shared/useChatAttachments.ts` 增加附件单文件大小（10MB）与后缀白名单预检；  
     - `frontend/apps/teacher/src/features/workbench/hooks/useAssignmentWorkflow.ts` 增加作业与答案文件的数量/大小/后缀及总上传大小（80MB）前置校验；  
     - `frontend/apps/teacher/src/features/persona/TeacherPersonaManager.tsx`、`frontend/apps/student/src/features/layout/StudentTopbar.tsx` 增加头像文件前置校验（2MB + 后缀白名单）。  
   - 涉及文件：`frontend/apps/shared/uploadValidation.ts`、`frontend/apps/shared/useChatAttachments.ts`、`frontend/apps/teacher/src/features/workbench/hooks/useAssignmentWorkflow.ts`、`frontend/apps/teacher/src/features/persona/TeacherPersonaManager.tsx`、`frontend/apps/student/src/features/layout/StudentTopbar.tsx`。  
   - 验证：新增 `tests/test_frontend_upload_precheck.py` 并通过；`frontend` TypeScript typecheck 通过。

13. P1：`llm_gateway` 非有限超时值回退策略加固  
   - 修复点：  
     - `llm_gateway.py` 中 `_parse_timeout_candidate` 显式拦截 `nan/+inf/-inf` 与非有限值，统一回退到默认超时策略；  
     - `_clamp_timeout_seconds` 增加 `math.isfinite` 守卫，确保最终 connect/read timeout 始终为有限正数。  
   - 涉及文件：`llm_gateway.py`。  
   - 验证：扩展 `tests/test_llm_gateway.py` 覆盖 `nan/inf` 与极值夹紧场景并通过；`tests/test_llm_gateway_retry.py` 回归通过。

### 最近一次回归结果

- `python3 -m pytest tests/test_grade_submission_security.py tests/test_student_submit_service.py tests/test_student_ops_api_service.py tests/test_security_auth_hardening.py tests/test_student_history_flow.py tests/test_student_routes.py tests/test_skill_routes.py tests/test_student_history_routes_types.py tests/test_student_profile_routes_types.py -q`  
  结果：`25 passed, 1 warning`
- `python3 -m pytest tests/test_student_submit_service.py tests/test_student_ops_api_service.py tests/test_skills_endpoint.py -q`  
  结果：`8 passed, 1 warning`
- `python3 -m pytest tests/test_chat_attachment_service.py tests/test_chat_attachment_flow.py -q`  
  结果：`3 passed, 1 warning`
- `python3 -m pytest tests/test_assignment_upload_start_service.py tests/test_assignment_upload_parse_service.py tests/test_assignment_upload_confirm_service.py tests/test_assignment_upload_legacy_service.py tests/test_upload_text_service.py tests/test_upload_text_service_more.py tests/test_exam_upload_start_service.py tests/test_exam_upload_parse_service.py tests/test_exam_upload_flow.py -q`  
  结果：`54 passed, 1 warning`
- `python3 -m pytest tests/test_chat_attachment_service.py tests/test_chat_attachment_flow.py tests/test_assignment_upload_start_service.py tests/test_assignment_upload_legacy_service.py tests/test_exam_upload_start_service.py tests/test_assignment_upload_parse_service.py tests/test_assignment_upload_confirm_service.py tests/test_exam_upload_parse_service.py tests/test_exam_upload_flow.py tests/test_grade_submission_security.py tests/test_student_submit_service.py tests/test_security_auth_hardening.py tests/test_student_history_flow.py tests/test_student_routes.py tests/test_skill_routes.py tests/test_student_history_routes_types.py tests/test_student_profile_routes_types.py -q`  
  结果：`61 passed, 1 warning`
- `python3 -m pytest tests/test_security_auth_hardening.py tests/test_assignment_upload_query_service.py tests/test_assignment_upload_draft_save_service.py tests/test_exam_upload_api_service.py tests/test_assignment_upload_start_service.py tests/test_exam_upload_start_service.py -q`  
  结果：`39 passed, 1 warning`
- `python3 -m pytest tests/test_chat_attachment_service.py tests/test_chat_attachment_flow.py tests/test_assignment_upload_start_service.py tests/test_assignment_upload_legacy_service.py tests/test_exam_upload_start_service.py tests/test_assignment_upload_parse_service.py tests/test_assignment_upload_confirm_service.py tests/test_exam_upload_parse_service.py tests/test_exam_upload_flow.py tests/test_grade_submission_security.py tests/test_student_submit_service.py tests/test_security_auth_hardening.py tests/test_student_history_flow.py tests/test_student_routes.py tests/test_skill_routes.py tests/test_student_history_routes_types.py tests/test_student_profile_routes_types.py tests/test_assignment_routes.py tests/test_exam_routes.py tests/test_exam_endpoints.py -q`  
  结果：`71 passed, 1 warning`
- `python3 -m pytest tests/test_rate_limit.py tests/test_assignment_catalog_service.py tests/test_exam_catalog_service.py tests/test_assignment_routes.py tests/test_exam_routes.py tests/test_misc_routes.py -q`  
  结果：`29 passed`
- `python3 -m pytest tests/test_chat_attachment_service.py tests/test_chat_attachment_flow.py tests/test_assignment_upload_start_service.py tests/test_assignment_upload_legacy_service.py tests/test_exam_upload_start_service.py tests/test_assignment_upload_parse_service.py tests/test_assignment_upload_confirm_service.py tests/test_exam_upload_parse_service.py tests/test_exam_upload_flow.py tests/test_grade_submission_security.py tests/test_student_submit_service.py tests/test_security_auth_hardening.py tests/test_student_history_flow.py tests/test_student_routes.py tests/test_skill_routes.py tests/test_student_history_routes_types.py tests/test_student_profile_routes_types.py tests/test_assignment_routes.py tests/test_exam_routes.py tests/test_exam_endpoints.py tests/test_rate_limit.py tests/test_assignment_catalog_service.py tests/test_exam_catalog_service.py tests/test_misc_routes.py -q`  
  结果：`96 passed, 1 warning`
- `python3 -m pytest tests/test_frontend_type_hardening.py tests/test_ci_workflow_quality.py tests/test_ci_backend_hardening_workflow.py tests/test_ci_smoke_e2e_workflow.py tests/test_docker_publish_workflow.py tests/test_batch_c_frontend_security_hardening.py tests/test_ci_actions_sha_pin.py tests/test_docker_security_baseline.py -q`  
  结果：`30 passed`
- `npm --prefix frontend run typecheck`  
  结果：`通过`
- `python3 -m pytest tests/test_security_auth_hardening.py tests/test_chat_job_processing_service.py tests/test_chat_lock_service.py tests/test_teacher_persona_api_service.py tests/test_student_persona_api_service.py tests/test_frontend_type_hardening.py -q`  
  结果：`51 passed, 1 warning`
- `python3 -m pytest tests/test_agent_service.py tests/test_docker_security_baseline.py -q`  
  结果：`15 passed`
- `python3 -m pytest tests/test_agent_service.py tests/test_ci_workflow_quality.py tests/test_ci_backend_hardening_workflow.py tests/test_ci_smoke_e2e_workflow.py tests/test_docker_publish_workflow.py tests/test_docker_security_baseline.py tests/test_batch_c_frontend_security_hardening.py tests/test_ci_actions_sha_pin.py tests/test_frontend_type_hardening.py -q`  
  结果：`43 passed`
- `python3 -m pytest tests/test_chat_lock_service.py tests/test_chat_lock_service_more.py tests/test_job_repository_lockfile.py tests/test_chat_job_processing_service.py tests/test_agent_service.py tests/test_docker_security_baseline.py tests/test_batch_c_frontend_security_hardening.py tests/test_ci_actions_sha_pin.py tests/test_frontend_type_hardening.py -q`  
  结果：`67 passed, 2 skipped`
- `python3 -m pytest tests/test_chat_lock_service.py tests/test_chat_lock_service_more.py tests/test_job_repository_lockfile.py tests/test_chat_job_processing_service.py tests/test_agent_service.py tests/test_docker_security_baseline.py tests/test_student_verify_contract_drift.py tests/test_frontend_type_hardening.py tests/test_batch_c_frontend_security_hardening.py tests/test_ci_actions_sha_pin.py -q`  
  结果：`69 passed, 2 skipped`
- `npm --prefix frontend run typecheck`  
  结果：`通过`
- `python3 -m pytest tests/test_chat_lock_service.py tests/test_chat_lock_service_more.py tests/test_job_repository_lockfile.py tests/test_chat_job_processing_service.py tests/test_frontend_upload_precheck.py tests/test_student_verify_contract_drift.py tests/test_agent_service.py tests/test_docker_security_baseline.py tests/test_ci_actions_sha_pin.py tests/test_frontend_type_hardening.py -q`  
  结果：`70 passed, 2 skipped`
- `npm --prefix frontend run typecheck`  
  结果：`通过`
- `python3 -m pytest tests/test_chat_lock_service.py tests/test_chat_lock_service_more.py tests/test_job_repository_lockfile.py tests/test_chat_job_processing_service.py tests/test_frontend_upload_precheck.py tests/test_student_verify_contract_drift.py tests/test_llm_gateway.py tests/test_llm_gateway_retry.py tests/test_agent_service.py tests/test_docker_security_baseline.py tests/test_ci_actions_sha_pin.py tests/test_frontend_type_hardening.py -q`  
  结果：`78 passed, 2 skipped, 1 warning`
