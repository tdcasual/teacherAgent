# HTTP API (Physics Teaching Helper)

本文档描述项目提供的 HTTP 接口（FastAPI）。

## 基础信息
- Base URL：`http://localhost:8000`
- Content-Type：`application/json`（除文件上传/表单接口）

## 实现说明（app.py 模块化）
`services/api/app.py` 作为组合根（composition root），统一通过
`services/api/app_routes.py` 注册各领域路由模块：
- `services/api/routes/chat_routes.py`
- `services/api/routes/student_routes.py`
- `services/api/routes/teacher_routes.py`
- `services/api/routes/skill_routes.py`
- `services/api/routes/assignment_routes.py`

## 架构边界约束（2026-02 更新）
- 模块边界规范：`docs/architecture/module-boundaries.md`
- Ownership 映射：`docs/architecture/ownership-map.md`

当前 API 目录遵循以下边界：
- `routes/*`：仅做 HTTP 协议转换，不做业务编排
- `assignment/application.py`：承载 context 用例编排
- `app.py` + `container.py`：组合根与依赖注入入口

---

## Health
### GET `/health`
返回 `{ "status": "ok" }`

---

## 对话
### POST `/chat`
根据师生角色触发多技能 agent。

**请求**
```json
{
  "role": "teacher",
  "messages": [
    { "role": "user", "content": "列出所有考试" },
    { "role": "assistant", "content": "已收到" }
  ]
}
```

**响应**
```json
{
  "reply": "……",
  "role": "teacher"
}
```

---

## 老师端模型配置与 Provider 管理

### GET `/teacher/model-config`
读取老师模型用途配置（`conversation`、`embedding`、`ocr`、`image_generation`）与可用目录。

### PUT `/teacher/model-config`
更新老师模型用途配置。

### GET `/teacher/provider-registry`
读取老师私有 Provider 列表（脱敏）及共享+私有合并目录。

### POST `/teacher/provider-registry/providers`
新增私有 Provider（OpenAI-Compatible，支持自定义 `base_url`）。
- 请求字段：
  - `teacher_id`（可选，默认 `teacher`）
  - `provider_id`（可选，未填自动生成；不可与共享 provider 同名）
  - `display_name`（可选）
  - `base_url`（必填，例如 `https://proxy.example.com/v1`）
  - `api_key`（必填，仅写入时可见，返回仅掩码）
  - `default_model`（可选）
  - `enabled`（可选，默认 `true`）
- 说明：可直接填写中转/代理地址；生产环境默认仅允许 `https://`。

### PATCH `/teacher/provider-registry/providers/{provider_id}`
更新私有 Provider（支持 key 轮换，不回显明文 key）。
- 可更新字段：`display_name`、`base_url`、`default_model`、`enabled`、`api_key`（轮换）。

### DELETE `/teacher/provider-registry/providers/{provider_id}`
禁用私有 Provider（软删除）。

### POST `/teacher/provider-registry/providers/{provider_id}/probe-models`
探测模型列表（依赖上游 `/models` 兼容性；失败不影响手填模型）。

---

## 技能与列表查询
### GET `/skills`
返回技能列表（从 `skills/*/SKILL.md` 自动扫描）

### GET `/assignments`
返回已有作业列表

### GET `/lessons`
返回已有课程列表

---

## 作业上传（异步 Job）
### POST `/assignment/upload/start`
上传作业试卷（必填）与答案（可选），创建后台解析任务。

**multipart/form-data**
- `assignment_id`（必填）
- `date`（可选）
- `scope`（public/class/student）
- `class_name` / `student_ids`（按 scope 填写）
- `files`（必填，PDF 或图片；可多文件）
- `answer_files`（可选，PDF 或图片；可多文件）

### GET `/assignment/upload/status?job_id=...`
查询解析进度与状态。

### GET `/assignment/upload/draft?job_id=...`
获取作业草稿（题目列表 + 8 点要求）。

### POST `/assignment/upload/draft/save`
保存草稿覆盖（老师编辑 8 点要求/题目后保存）。

### POST `/assignment/upload/confirm`
确认创建作业（写入 `data/assignments/<assignment_id>/`）。

---

## 学生画像
### GET `/student/profile/{student_id}`
读取学生画像 JSON

### POST `/student/profile/update`
**表单字段**
- `student_id`（必填）
- `weak_kp` / `strong_kp` / `medium_kp`（可选）
- `next_focus` / `interaction_note`（可选）

---

## 学生导入
### POST `/student/import`
从成绩 CSV（`file_path` 或 `data/staging` 最新 responses 文件）导入学生名册。

**请求**
```json
{
  "source": "responses_scored",
  "file_path": "",
  "mode": "merge"
}
```

---

## 作业生成与渲染
### POST `/assignment/generate`
**表单字段**
- `assignment_id`（必填）
- `kp`（必填，逗号分隔）
- `per_kp`（默认 5）
- `core_examples`（可选）
- `generate`（布尔，可选）

### POST `/assignment/render`
**表单字段**
- `assignment_id`（必填）

---

## 作业提交
### POST `/student/submit`
**multipart/form-data**
- `student_id`（必填）
- `files`（必填，支持多文件）
- `assignment_id`（必填）
- `auto_assignment`（若为 `true` → 400 `auto_assignment_disabled`）

成功时 HTTP 200。`submitted=false` 表示这次没有记为提交，不是传输失败。`reason=min_graded_total` 为有效评分不足；`reason=progress_unavailable` 为提交后未能读到 progress，不能当成评分不足。

---

## 文件上传
### POST `/upload`
**multipart/form-data**
- `files`（必填，支持多文件）
