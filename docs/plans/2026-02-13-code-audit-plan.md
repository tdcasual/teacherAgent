# 全栈代码审计实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 对物理教育平台进行全栈严格代码审计，发现安全漏洞、逻辑 bug、健壮性和性能隐患。

**Architecture:** 风险分层扫描，5 个 Phase 从高危到低危逐层推进。每个模块按 10 条审计规则逐条检查，问题按 H/M/L 分级。审计报告输出到 `docs/plans/2026-02-13-code-audit-findings.md`，确认后修复。

**Tech Stack:** Python/FastAPI 后端, React/TypeScript 前端, Docker/GitHub Actions 基础设施

---

## Phase 1：高危后端模块

### Task 1: 审计 persona 模块（teacher 侧）

**Files:**
- Audit: `services/api/teacher_persona_api_service.py` (376 行)
- Audit: `services/api/routes/teacher_persona_routes.py` (107 行)
- Audit: `services/api/wiring/teacher_wiring.py` (83 行)

**审计规则重点:** R1(输入验证), R6(多租户), R8(API契约)

**Step 1: 阅读 teacher_persona_api_service.py**

逐行检查：
- 输入参数（persona_id, name, avatar 等）是否有格式校验
- 文件上传（头像）路径是否可控、是否有路径遍历风险
- CRUD 操作是否通过 `get_app_core()` 获取租户上下文
- 错误处理是否完整（不吞异常、不泄露内部信息）

**Step 2: 阅读 teacher_persona_routes.py**

检查：
- 路由是否有认证/授权中间件
- 请求体 schema 验证是否严格
- 响应是否泄露敏感字段

**Step 3: 记录发现的问题**

格式：`[H/M/L] 文件:行号 — 问题描述 — 修复方案`

**Step 4: 提交审计记录**

---

### Task 2: 审计 persona 模块（student 侧）

**Files:**
- Audit: `services/api/student_persona_api_service.py` (570 行)
- Audit: `services/api/routes/student_persona_routes.py` (117 行)
- Audit: `services/api/wiring/student_wiring.py` (79 行)

**审计规则重点:** R1(输入验证), R6(多租户), R2(文件I/O)

**Step 1: 阅读 student_persona_api_service.py**

逐行检查：
- 学生是否能访问其他学生的 persona 数据（越权）
- 头像上传的文件类型/大小限制
- persona 切换逻辑的并发安全性
- 数据流：用户输入 → API → 存储，每个转换点的校验

**Step 2: 阅读 student_persona_routes.py**

检查路由认证、参数校验、错误响应。

**Step 3: 记录发现的问题并提交**

---

### Task 3: 审计 chat_attachment_service.py

**Files:**
- Audit: `services/api/chat_attachment_service.py` (428 行)
- Reference: `frontend/apps/shared/useChatAttachments.ts` (333 行)

**审计规则重点:** R1(输入验证), R2(文件I/O安全), R4(错误处理)

**Step 1: 阅读 chat_attachment_service.py**

重点检查：
- 文件上传路径构造：是否可被用户控制导致路径遍历
- 文件类型白名单：是否严格限制允许的 MIME 类型
- 文件大小限制：是否在服务端强制执行
- 临时文件清理：上传失败时是否清理残留文件
- 文件名 sanitize：是否过滤特殊字符（`../`, null bytes 等）

**Step 2: 追踪数据流**

从前端 `useChatAttachments.ts` 的上传调用 → API 路由 → service 处理 → 文件存储，标记每个未校验的转换点。

**Step 3: 记录发现的问题并提交**

---

### Task 4: 审计 exam_upload_parse_service.py

**Files:**
- Audit: `services/api/exam_upload_parse_service.py` (971 行)
- Reference: `services/api/handlers/exam_upload_handlers.py` (85 行)
- Reference: `services/api/routes/exam_upload_routes.py` (48 行)

**审计规则重点:** R1(输入验证), R2(文件I/O), R4(错误处理), R5(数据完整性)

**Step 1: 阅读 exam_upload_parse_service.py**

这是最大的模块之一（971 行），重点检查：
- OCR 解析结果的输入校验（外部 OCR 服务返回的数据是否被信任）
- 文件处理：临时文件创建/清理、大文件内存加载
- 解析逻辑的边界条件：空文件、损坏文件、超大文件
- 错误处理链：OCR 失败、解析失败、部分成功的处理
- 数值解析：分数、页码等数值的类型转换安全

**Step 2: 检查上传入口链**

从 routes → handlers → service 的完整调用链，确认每层的校验。

**Step 3: 记录发现的问题并提交**

---

### Task 5: 审计 agent_service.py

**Files:**
- Audit: `services/api/agent_service.py` (711 行)

**审计规则重点:** R1(输入验证), R3(并发), R4(错误处理), R10(性能)

**Step 1: 阅读 agent_service.py**

重点检查：
- LLM 调用的输入构造：是否有 prompt injection 风险
- 并发控制：多个 agent 调用是否有竞态条件
- 超时处理：LLM 调用是否有超时限制
- 错误处理：LLM 返回异常/空响应/格式错误的处理
- 资源限制：是否限制并发 agent 数量
- 响应解析：LLM 输出的解析是否安全（不执行任意代码）

**Step 2: 记录发现的问题并提交**

---

### Task 6: 审计 chat_job_processing_service.py

**Files:**
- Audit: `services/api/chat_job_processing_service.py` (652 行)
- Reference: `services/api/chat_start_service.py` (367 行)

**审计规则重点:** R3(并发竞态), R4(错误处理), R6(多租户)

**Step 1: 阅读 chat_job_processing_service.py**

重点检查：
- 任务队列的并发安全：同一 job 是否可能被重复处理
- 任务状态机：状态转换是否原子性，是否有中间状态泄漏
- 错误恢复：任务失败后的重试逻辑、死信处理
- 多租户：job 处理是否正确设置租户上下文
- 资源清理：长时间运行的 job 是否有超时机制

**Step 2: 阅读 chat_start_service.py**

检查会话创建的并发安全、锁竞态。

**Step 3: 记录发现的问题并提交**

---

### Task 7: 审计 llm_gateway.py

**Files:**
- Audit: `llm_gateway.py` (587 行)

**审计规则重点:** R1(输入验证), R4(错误处理), R10(性能/超时)

**Step 1: 阅读 llm_gateway.py**

重点检查：
- API key 管理：是否硬编码、是否安全传递
- 请求构造：用户输入是否直接拼入 prompt（injection 风险）
- 超时设置：每个 LLM 调用是否有合理的超时
- 重试逻辑：是否有指数退避、是否限制重试次数
- 错误处理：rate limit、网络错误、API 错误的处理
- 响应验证：LLM 返回的数据是否被校验后再使用
- 并发限制：是否限制同时发出的 LLM 请求数

**Step 2: 记录发现的问题并提交**

---

### Task 8: 审计 chart_executor.py 和 exam_score_processing_service.py

**Files:**
- Audit: `services/api/chart_executor.py` (1,041 行)
- Audit: `services/api/exam_score_processing_service.py` (551 行)

**审计规则重点:** R1(输入验证), R2(文件I/O), R5(数据完整性)

**Step 1: 阅读 chart_executor.py**

上次已做过沙箱加固，本次检查：
- 沙箱逃逸的新向量（import 绕过、文件系统访问）
- 代码扫描规则是否有遗漏
- 资源限制是否可被绕过
- 并发信号量是否正确工作

**Step 2: 阅读 exam_score_processing_service.py**

检查：
- 分数计算的数值边界（除零、溢出、NaN）
- 数据解析的类型安全
- 部分数据缺失时的处理逻辑

**Step 3: 记录发现的问题并提交**

---

### Task 9: 审计上传相关服务集群

**Files:**
- Audit: `services/api/upload_text_service.py` (223 行)
- Audit: `services/api/upload_llm_service.py` (335 行)
- Audit: `services/api/assignment_upload_confirm_service.py` (367 行)
- Audit: `services/api/assignment_upload_parse_service.py` (332 行)
- Audit: `services/api/assignment_upload_legacy_service.py` (203 行)

**审计规则重点:** R1(输入验证), R2(文件I/O), R4(错误处理)

**Step 1: 逐个阅读上传服务**

统一检查：
- 文件路径构造安全性
- 上传文件的类型/大小限制
- 临时文件生命周期管理
- 错误处理和资源清理

**Step 2: 记录发现的问题并提交**

---

### Task 10: Phase 1 汇总报告

**Step 1: 汇总所有 Phase 1 发现**

将 Task 1-9 的所有发现汇总到 `docs/plans/2026-02-13-code-audit-findings.md`，按严重级别排序。

**Step 2: 提交报告，等待用户确认后进入 Phase 2**

---

## Phase 2：前端安全审计

### Task 11: 审计 Student App

**Files:**
- Audit: `frontend/apps/student/src/App.tsx` (469 行)
- Audit: `frontend/apps/student/src/hooks/useStudentState.ts` (277 行)
- Audit: `frontend/apps/student/src/features/chat/useStudentSendFlow.ts` (251 行)
- Audit: `frontend/apps/student/src/features/chat/ChatComposer.tsx` (104 行)
- Audit: `frontend/apps/student/src/features/layout/StudentTopbar.tsx` (263 行)
- Audit: `frontend/apps/student/src/appTypes.ts` (125 行)

**审计规则重点:** R7(前端安全), R8(API契约)

**Step 1: 检查 XSS 风险**

搜索所有 `dangerouslySetInnerHTML`、`innerHTML`、未转义的用户内容渲染。
检查 Markdown 渲染是否有 sanitize。

**Step 2: 检查敏感数据处理**

- localStorage/sessionStorage 中是否存储敏感信息
- API token 的存储和传递方式
- 错误信息是否泄露内部细节

**Step 3: 检查输入处理**

- 用户输入（聊天消息、persona 名称等）是否在发送前校验
- 文件上传的客户端校验

**Step 4: 记录发现的问题并提交**

---

### Task 12: 审计 Teacher App

**Files:**
- Audit: `frontend/apps/teacher/src/App.tsx` (799 行)
- Audit: `frontend/apps/teacher/src/features/routing/RoutingPage.tsx` (1,698 行)
- Audit: `frontend/apps/teacher/src/features/workbench/hooks/useAssignmentWorkflow.ts` (804 行)
- Audit: `frontend/apps/teacher/src/features/chat/useTeacherChatApi.ts` (638 行)
- Audit: `frontend/apps/teacher/src/features/persona/TeacherPersonaManager.tsx` (295 行)
- Audit: `frontend/apps/teacher/src/features/persona/personaApi.ts` (144 行)

**审计规则重点:** R7(前端安全), R8(API契约)

**Step 1: 检查 XSS 风险**

同 Task 11，重点关注 RoutingPage.tsx（1698 行，最大前端文件）。

**Step 2: 检查权限控制 UI**

- 教师操作（删除、修改配置等）是否有确认对话框
- 是否有前端权限检查（虽然不能替代后端，但作为防御层）

**Step 3: 检查 API 调用安全**

- API 调用是否正确处理所有错误状态码
- 是否有未处理的 Promise rejection

**Step 4: 记录发现的问题并提交**

---

### Task 13: 审计 Shared Utils

**Files:**
- Audit: `frontend/apps/shared/useChatAttachments.ts` (333 行)
- Audit: `frontend/apps/shared/markdown.ts` (194 行)
- Audit: `frontend/apps/shared/dialog.tsx` (195 行)
- Audit: `frontend/apps/shared/visibilityBackoffPolling.ts` (122 行)

**审计规则重点:** R7(前端安全), R10(性能)

**Step 1: 重点审计 markdown.ts**

Markdown 渲染是 XSS 的高风险区域：
- 是否使用了安全的 Markdown 库
- 是否有 HTML sanitize
- 是否允许自定义 HTML 标签

**Step 2: 审计 useChatAttachments.ts**

- 文件上传的客户端校验
- 大文件处理（内存占用）
- 上传失败的清理逻辑

**Step 3: 记录发现的问题并提交**

---

### Task 14: Phase 2 汇总报告

汇总前端审计发现，追加到 findings 文档，等待确认。

---

## Phase 3：API 契约一致性

### Task 15: 前后端类型一致性检查

**Files:**
- Compare: `frontend/apps/teacher/src/appTypes.ts` (428 行) vs `services/api/api_models.py` (165 行)
- Compare: `frontend/apps/student/src/appTypes.ts` (125 行) vs `services/api/api_models.py`
- Compare: `frontend/apps/teacher/src/features/routing/routingTypes.ts` (235 行)

**Step 1: 提取前端 TypeScript 类型定义**

列出所有 API 相关的 interface/type。

**Step 2: 提取后端 Python model 定义**

列出所有 Pydantic model / dataclass。

**Step 3: 逐一对比字段名、类型、可选性**

标记不一致的地方。

**Step 4: 记录发现的问题并提交**

---

### Task 16: 端点认证与授权审计

**Files:**
- Audit: `services/api/routes/` 目录下所有 30 个路由文件
- Reference: 认证中间件相关代码

**Step 1: 列出所有 API 端点**

从路由文件中提取所有端点（method + path）。

**Step 2: 检查每个端点的认证要求**

- 是否有认证中间件
- 是否区分教师/学生角色
- 是否有越权访问风险（学生访问教师端点）

**Step 3: 记录发现的问题并提交**

---

### Task 17: Phase 3 汇总报告

汇总 API 契约审计发现，追加到 findings 文档，等待确认。

---

## Phase 4：基础设施与配置

### Task 18: 审计 Docker 配置

**Files:**
- Audit: `docker-compose.yml` (257 行)
- Audit: 各服务的 Dockerfile

**Step 1: 检查安全配置**

- 容器是否以 root 运行
- 端口暴露是否最小化
- secrets 是否通过环境变量安全传递（非硬编码）
- 资源限制是否合理
- 健康检查是否完整

**Step 2: 记录发现的问题并提交**

---

### Task 19: 审计 CI Workflows

**Files:**
- Audit: `.github/workflows/ci.yml` (300 行)
- Audit: `.github/workflows/docker.yml` (100 行)
- Audit: `.github/workflows/teacher-e2e.yml` (69 行)
- Audit: `.github/workflows/mobile-session-menu-e2e.yml` (69 行)

**Step 1: 检查安全配置**

- secrets 使用是否安全（不在日志中暴露）
- 权限范围是否最小化（permissions 字段）
- 第三方 action 是否锁定版本（SHA pinning）
- 缓存是否有投毒风险

**Step 2: 记录发现的问题并提交**

---

### Task 20: 审计 Scripts

**Files:**
- Audit: `scripts/grade_submission.py` (755 行)
- Audit: `scripts/ocr_review_apply.py` (285 行)
- Audit: `scripts/backup/run_backup.sh` (145 行)
- Audit: `scripts/backup/common.sh` (156 行)
- Audit: `scripts/backup/verify_restore.sh` (90 行)

**审计规则重点:** R1(输入验证), R2(文件I/O)

**Step 1: 检查脚本安全**

- 命令注入风险（用户输入拼入 shell 命令）
- 文件操作安全（路径构造、临时文件）
- 备份脚本的权限和加密

**Step 2: 记录发现的问题并提交**

---

### Task 21: Phase 4 汇总报告

汇总基础设施审计发现，追加到 findings 文档，等待确认。

---

## Phase 5：性能与健壮性扫描

### Task 22: 全局性能隐患扫描

**Step 1: 搜索无界列表模式**

在 `services/api/` 中搜索返回列表但无分页的 API 端点。
关键词：`json.loads`, `listdir`, `glob`, 无 `limit`/`offset` 参数的查询。

**Step 2: 搜索大文件内存加载**

搜索 `open().read()`, `Path.read_text()`, `json.load()` 等一次性读取整个文件的模式。
检查是否有文件大小检查。

**Step 3: 搜索缺失的超时设置**

搜索 HTTP 调用（`requests.`, `httpx.`, `aiohttp.`）是否都设置了 timeout。
搜索文件锁等待是否有超时。

**Step 4: 搜索全局状态/缓存无界增长**

检查模块级字典/列表是否有大小限制或过期机制。

**Step 5: 记录发现的问题并提交**

---

### Task 23: 最终汇总报告

**Step 1: 汇总所有 Phase 的发现**

在 `docs/plans/2026-02-13-code-audit-findings.md` 中：
- 按严重级别（H → M → L）排序所有发现
- 统计各级别数量
- 标注修复优先级和工作量估算

**Step 2: 提交最终报告**

```bash
git add docs/plans/2026-02-13-code-audit-findings.md
git commit -m "docs: complete full-stack code audit findings report"
```

**Step 3: 等待用户确认后，按优先级逐个修复**
