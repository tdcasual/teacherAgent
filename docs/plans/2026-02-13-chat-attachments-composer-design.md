# 2026-02-13 教师端/学生端 ChatComposer 附件上传设计

## 1. 背景与目标

当前教师端与学生端聊天输入框仅支持纯文本。目标是在两端输入框增加与 ChatGPT 类似的附件能力，并保持现有聊天队列架构稳定。

本次设计确认的产品约束：
- 上传入口放在聊天输入框，交互接近 ChatGPT。
- 允许文件类型：`markdown(.md/.markdown)`、`xls`、`xlsx`、图片（`image/*`）、`pdf`。
- 限制规则：单文件不超过 10MB；单条消息最多 5 个文件；单条消息总大小不超过 30MB。
- 文件内容默认自动解析并注入聊天上下文（而非仅保存）。
- 采用两段式上传：先上传附件，再在 `/chat/start` 引用附件 ID。

非目标：
- 不引入跨会话附件共享。
- 不做附件长期知识库化。
- 不在本期支持 doc/docx、zip 等额外类型。

## 2. 方案选择与结论

候选方案：
1. 两段式上传（推荐并采用）：`/chat/attachments` 上传，`/chat/start` 引用 `attachment_id`。
2. 直传 multipart `/chat/start`：文本+文件一次提交。
3. 仅在消息里传 URL/Base64。

采用方案 1 的原因：
- 与现有 `/chat/start` 队列、幂等、去重和状态轮询机制兼容。
- 上传和解析失败可细粒度重试，不阻塞聊天主链路。
- 前端可做到“上传即显示卡片、异步解析”，体验最接近 ChatGPT。

## 3. 总体架构

### 3.1 前端层

教师端 `frontend/apps/teacher/src/features/chat/ChatComposer.tsx` 与学生端 `frontend/apps/student/src/features/chat/ChatComposer.tsx` 均新增：
- 附件按钮与隐藏 file input。
- 附件托盘（文件名、大小、类型、状态、删除/重试）。
- 上传状态管理（`uploading -> processing -> ready|failed`）。

共享逻辑建议抽到 `frontend/apps/shared`：
- `useChatAttachments`（上传、状态轮询、删除、重试、约束校验）。
- `AttachmentTray`（统一 UI）。

### 3.2 后端层

新增附件 API 与存储：
- `POST /chat/attachments`：上传附件并创建记录。
- `GET /chat/attachments/status`：批量查询附件状态。
- `DELETE /chat/attachments/{attachment_id}`：发送前移除附件。

并扩展聊天启动请求：
- `POST /chat/start` 请求体新增 `attachments` 字段（attachment 引用列表）。

解析由后台 worker 异步执行，避免上传接口长时阻塞。

### 3.3 存储层

建议目录：`uploads/chat_attachments/{attachment_id}/`
- `meta.json`：归属、状态、错误码、大小、mime、会话绑定。
- `source.bin`（或原始文件名）：原文件。
- `extracted.txt` 或 `extracted.json`：提取结果。

## 4. API 与数据模型设计

### 4.1 POST /chat/attachments

- 请求：`multipart/form-data`
- 字段建议：
  - `role`: `teacher|student`
  - `session_id`: string
  - `request_id`: string（用于链路追踪）
  - `files[]`: file list
  - `teacher_id/student_id`: 按角色提供
- 返回：
  - `attachments: [{ attachment_id, file_name, size_bytes, mime, status }]`
  - `warnings: []`（部分文件失败时返回）

服务端校验：
- 类型白名单（扩展名 + MIME 双重校验）。
- 单文件 <= 10MB。
- 单次文件数 <= 5。
- 单次总大小 <= 30MB。

### 4.2 GET /chat/attachments/status

- 请求参数：`attachment_ids[]`
- 返回：每个附件当前状态及错误信息。
- 用于前端轮询，把 `processing` 刷新为 `ready|failed`。

### 4.3 DELETE /chat/attachments/{attachment_id}

- 语义：仅允许删除当前用户在当前会话下、尚未提交引用的附件。
- 返回：`ok: true`。

### 4.4 POST /chat/start（扩展）

在现有 `ChatStartRequest` 上增加：
- `attachments: [{ attachment_id: string }]`（可选）

后端处理：
- 校验 attachment 归属/会话一致性。
- 仅注入 `ready` 附件。
- 将 `processing|failed` 作为 warnings 返回，聊天请求仍可继续。

## 5. 附件解析与上下文注入

### 5.1 解析策略

- `md/markdown`：直接读取 UTF-8 文本。
- `pdf`：优先文本提取，失败或过短时 OCR fallback。
- `image/*`：OCR 提取。
- `xls/xlsx`：提取表头、前 N 行、基础统计，输出结构化摘要文本。

### 5.2 注入策略

在组装 `messages` 时，向最后一个 user turn 追加“附件上下文块”。

规则：
- 仅使用 `ready` 附件。
- 按用户上传顺序拼接。
- 设总注入预算（例如 12k 字符）；超限截断并记录 `truncated=true`。
- 每个附件加边界标题：`[附件 #n: filename.ext]`，便于模型区分来源。

### 5.3 失败与降级

- 单文件失败不影响其他附件与文本发送。
- 全部附件不可用时，聊天仍可按纯文本执行。
- 在响应中带 `warnings`，前端以轻量提示展示。

## 6. 前端交互细节

### 6.1 Composer 行为

- 选择文件后立即上传，不等点击发送。
- 附件卡片显示状态：
  - `uploading`: 进度/旋转图标
  - `processing`: “解析中”
  - `ready`: 可发送
  - `failed`: 错误文案 + 重试按钮
- 支持单个附件移除。

### 6.2 发送按钮策略

- 满足“有文本”或“有至少一个 ready 附件”即可发送。
- 若仅有 `processing` 附件且无文本，阻止发送并提示“附件解析中，请稍后”。
- 发送成功后清空 `ready` 附件；`failed` 可保留供用户重试或手动删除。

### 6.3 教师端与学生端差异

- 教师端：保持 `pendingChatJob` 时输入禁用语义。
- 学生端：保持“未验证学生身份时禁用发送”语义。
- 两端共享附件逻辑和视觉组件，避免行为漂移。

## 7. 安全与治理

- 文件名净化与路径隔离，防止目录穿越。
- 扩展名与 MIME 双重校验。
- 附件强绑定 owner + session，拒绝跨账号/跨会话引用。
- 限制解析资源占用（并发、超时、单附件字符预算）。
- 错误码标准化：`unsupported_type`、`file_too_large`、`too_many_files`、`total_size_exceeded`、`extract_failed`、`forbidden_attachment`。

## 8. 观测与运维

埋点建议统一前缀 `chat.attachment.*`：
- `chat.attachment.upload.received`
- `chat.attachment.upload.rejected`
- `chat.attachment.parse.done`
- `chat.attachment.parse.failed`
- `chat.start.attachments.injected`

关键指标：
- 上传成功率
- 解析成功率
- 首 token 延迟变化
- 平均注入字符数与截断率

## 9. 测试计划

### 9.1 单元测试
- 类型/体积/数量/总量校验。
- 状态机流转与错误码。
- 上下文注入预算和截断规则。

### 9.2 服务测试
- 上传接口鉴权与会话隔离。
- 解析成功/失败路径。
- `/chat/start` 在 ready/processing/failed 混合状态下语义正确。

### 9.3 前端集成测试
- 上传后卡片状态变化。
- 删除、重试、发送条件校验。
- 移动端附件托盘横向滚动可用。

### 9.4 E2E 测试
- 教师端与学生端完整链路：上传 -> 解析 -> 发送 -> 回答。
- 验证模型输出确实引用附件关键信息。

## 10. 上线计划

采用 Feature Flag 两阶段灰度：
1. 阶段 A：仅教师端灰度，观察上传/解析/延迟指标。
2. 阶段 B：开放学生端，重点关注 OCR 负载与失败码分布。

回滚策略：关闭附件入口 Flag，保留纯文本聊天主链路。

## 11. 实施拆分（建议）

- Slice 1：后端附件 API + 存储 + 基础校验
- Slice 2：解析 worker + 状态查询 + 错误码治理
- Slice 3：`/chat/start` 扩展与注入策略
- Slice 4：教师端 Composer UI + 交互
- Slice 5：学生端 Composer UI + 交互
- Slice 6：测试补齐与灰度开关

