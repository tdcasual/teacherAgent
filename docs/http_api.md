# HTTP API (Physics Teaching Helper)

本文档描述项目提供的 HTTP 接口（FastAPI）。

## 基础信息
- Base URL：`http://localhost:8000`
- Content-Type：`application/json`（除文件上传/表单接口）

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

## 技能与列表查询
### GET `/skills`
返回技能列表（从 `skills/*/SKILL.md` 自动扫描）

### GET `/exams`
返回已有考试列表

### GET `/assignments`
返回已有作业列表

### GET `/lessons`
返回已有课程列表

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

