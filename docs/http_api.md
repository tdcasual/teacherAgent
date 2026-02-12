# HTTP API (Physics Teaching Helper)

本文档描述项目提供的 HTTP 接口（FastAPI）。

## 基础信息
- Base URL：`http://localhost:8000`
- Content-Type：`application/json`（除文件上传/表单接口）

## 实现说明（app.py 模块化）
`services/api/app.py` 作为组合根（composition root），路由通过 deps 工厂委托到 domain API service：
- `services/api/exam_api_service.py`
- `services/api/assignment_api_service.py`
- `services/api/student_profile_api_service.py`
- `services/api/teacher_routing_api_service.py`
- `services/api/chart_api_service.py`
- `services/api/chat_api_service.py`
- `services/api/teacher_memory_api_service.py`
- `services/api/upload_io_service.py`
- `services/api/llm_agent_tooling_service.py`

## 架构边界约束（2026-02 更新）
- 模块边界规范：`docs/architecture/module-boundaries.md`
- Ownership 映射：`docs/architecture/ownership-map.md`

当前 API 目录遵循以下边界：
- `routes/*`：仅做 HTTP 协议转换，不做业务编排
- `exam/application.py`、`assignment/application.py`：承载 context 用例编排
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

## 老师端模型路由与 Provider 管理

### GET `/teacher/llm-routing`
读取当前老师的路由配置、校验结果、历史版本与提案列表。

### POST `/teacher/llm-routing/simulate`
基于当前配置（或传入草稿）进行路由仿真。

### POST `/teacher/llm-routing/proposals`
创建路由配置提案。

### GET `/teacher/llm-routing/proposals/{proposal_id}`
读取提案详情。

### POST `/teacher/llm-routing/proposals/{proposal_id}/review`
审核提案（生效或拒绝）。

### POST `/teacher/llm-routing/rollback`
回滚到历史版本。

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

### GET `/exams`
返回已有考试列表

## 考试（读取与分析）
### GET `/exam/{exam_id}`
返回考试 manifest + 汇总信息（学生数、题目数、总分概览等）。

### GET `/exam/{exam_id}/analysis`
返回考试分析草稿（若不存在则返回最小总分统计）。

### GET `/exam/{exam_id}/students`
返回考试学生列表（含总分与排名）。支持 query `limit`。

### GET `/exam/{exam_id}/student/{student_id}`
返回某个学生在本次考试中的逐题得分明细。

### GET `/exam/{exam_id}/question/{question_id}`
返回某道题的得分分布与统计（平均分/失分率等）。

### GET `/assignments`
返回已有作业列表

### GET `/lessons`
返回已有课程列表

---

## 考试上传（异步 Job）
### POST `/exam/upload/start`
上传考试试卷与成绩表，创建后台解析任务。

**multipart/form-data**
- `exam_id`（可选，不填会自动生成）
- `date`（可选，YYYY-MM-DD）
- `class_name`（可选）
- `paper_files`（必填，PDF 或图片；可多文件）
- `score_files`（必填，xls/xlsx 或 PDF/图片；可多文件）

**响应**
```json
{ "ok": true, "job_id": "job_xxx", "status": "queued", "message": "..." }
```

### GET `/exam/upload/status?job_id=...`
查询解析进度与状态（queued/processing/done/failed/confirmed）。

### GET `/exam/upload/draft?job_id=...`
获取解析草稿（用于老师审核/修改）。

### POST `/exam/upload/draft/save`
保存草稿覆盖（例如修改题目满分、日期、班级等）。

**请求**
```json
{ "job_id": "job_xxx", "meta": { "date": "2026-02-05" }, "questions": [{ "question_id": "Q1", "max_score": 4 }] }
```

### POST `/exam/upload/confirm`
确认创建考试数据与分析草稿（写入 `data/exams/<exam_id>/` 与 `data/analysis/<exam_id>/`）。

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
从考试数据导入学生名册。

**请求**
```json
{
  "source": "responses_scored",
  "exam_id": "A2403_2026-02-04",
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
- `assignment_id`（可选）
- `auto_assignment`（可选，布尔）

---

## 文件上传
### POST `/upload`
**multipart/form-data**
- `files`（必填，支持多文件）
