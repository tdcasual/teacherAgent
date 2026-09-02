# HTTP API

本文档描述项目提供的 HTTP 接口（FastAPI）。产品主线是**作业**（upload → confirm → 学生今日列表 → 显式提交 → progress），不是考试，也不是问卷/班级报告工作台。Exam HTTP 面已卸载：不要调用 `/exam/*`、`/exams` 或任何 exam 编排接口。Survey / class_report / analysis_report 路由同样不注册。

## 基础信息
- Base URL：`http://localhost:8000`
- Content-Type：`application/json`（除文件上传/表单接口）
- 老师端：`http://localhost:3002`
- 学生端：`http://localhost:3001`

## 实现说明（app.py 模块化）
`services/api/app.py` 作为组合根（composition root），统一通过
`services/api/app_routes.py` 注册各领域路由模块：
- `services/api/routes/chat_routes.py`
- `services/api/routes/student_routes.py`
- `services/api/routes/teacher_routes.py`
- `services/api/routes/skill_routes.py`
- `services/api/routes/assignment_routes.py`

身份与认领路由在 `services/api/routes/auth_routes.py`（含 `POST /auth/admin/assignments/{assignment_id}/claim`）。

## 架构边界约束（2026-02 更新）
- 模块边界规范：`docs/architecture/module-boundaries.md`
- Ownership 映射：`docs/architecture/ownership-map.md`

当前 API 目录遵循以下边界：
- `routes/*`：仅做 HTTP 协议转换，不做业务编排
- `assignment/application.py`：承载 context 用例编排
- `app.py` + `container.py`：组合根与依赖注入入口

学科 pack 不走 HTTP，见下文「学科 Pack」。

---

## Health
### GET `/health`
返回 `{ "status": "ok" }`

---

## 对话
### POST `/chat`
根据师生角色触发多技能 agent。老师默认走 assignment 工作流（上传/确认/进度），不要用对话去驱动 exam 工具。

**请求**
```json
{
  "role": "teacher",
  "messages": [
    { "role": "user", "content": "列出我布置的作业" },
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
  - `teacher_id`（必填；未认证或空值返回 `teacher_id_required`）
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

### GET `/teacher/roster`
读取当前老师的任教名册（`teacher_id` + `subject_id` + `class_name`）。老师端上传作业时用它填充学科/班级，而不是硬编码物理。

---

## 技能与列表查询
### GET `/skills`
需要登录。返回当前身份可见的技能：全员作业三件套（`teacher-assignment-ops` / `homework-generator` / `student-coach`），加上该老师名册学科 pack 的 `skill_affiliates`。未任教物理的老师不会看到 `physics-*`。学生没有附属 skill。

### GET `/assignments`
返回当前老师可见的作业列表（分页：`limit`、`cursor`）

### GET `/lessons`
返回已有课程列表

---

## 作业上传（异步 Job）
老师日常主线：`POST /assignment/upload/start` → 轮询 status/draft → `POST /assignment/upload/confirm` → `GET /teacher/assignment/progress`。

### POST `/assignment/upload/start`
上传作业文件（必填）与答案（可选），创建后台解析任务。`teacher_id` 取自登录 principal，不要在表单里传默认 `teacher`。

**multipart/form-data**
- `assignment_id`（必填）
- `subject_id`（必填；空值 → 400 `subject_id_required`。写入 `meta.json` 并决定 pack overlay）
- `date`（可选，`YYYY-MM-DD`）
- `due_at`（可选）
- `scope`（public/class/student）
- `class_name` / `student_ids`（按 scope 填写，可选）
- `files`（必填，PDF 或图片；可多文件）
- `answer_files`（可选，PDF 或图片；可多文件）
- `ocr_mode` / `language`（可选）

### GET `/assignment/upload/status?job_id=...`
查询解析进度与状态。

### GET `/assignment/upload/draft?job_id=...`
获取作业草稿（题目列表 + 8 点要求）。

### POST `/assignment/upload/draft/save`
保存草稿覆盖（老师编辑 8 点要求/题目后保存）。

### POST `/assignment/upload/confirm`
确认创建作业（写入 `data/assignments/<assignment_id>/`）。

**JSON**
- `job_id`（必填）
- `requirements_override`（可选）
- `confirm`（默认 `true`）
- `strict_requirements`（默认 `true`；缺 8 点要求时拒绝创建）

---

## 作业进度、归档与今日列表

### GET `/teacher/assignment/progress?assignment_id=...`
单份作业完成情况（应交 / 完成 / 已评分 / 逾期）。老师端「作业完成情况」面板读这个接口。可选 `include_students`。

### GET `/teacher/assignments/progress?date=YYYY-MM-DD`
当天（或指定日）该老师名下作业进度摘要。

### POST `/assignment/{assignment_id}/archive`
归档作业（老师或管理员；须拥有该作业）。

### POST `/assignment/{assignment_id}/unarchive`
取消归档。

### GET `/assignment/today?student_id=...`
学生「今日任务」。按学生已选科目/任课老师列出已布置作业。`auto_generate=true` 返回 **400** `auto_generate_disabled`——空态是「老师尚未布置」，不会自动生成作业。

### GET `/assignment/{assignment_id}`
作业详情（受可见性/所有权约束）。

### GET `/assignment/{assignment_id}/download?file=...`
下载作业材料（需鉴权；学生只能拿自己可见的文件）。

### GET `/student/assignments/history`
学生「作业记录」（材料 / 官方分 / 未交补交）。与会话侧栏「历史任务」不是同一个入口。

---

## 孤儿作业认领

迁移后没有合法 `teacher_id` / `subject_id` 的作业会变成 `visibility_status=orphan_draft`，不进老师列表，也不进学生今日任务。只有管理员可以认领。

### GET `/auth/admin/assignments/orphans`
列出孤儿作业。需 admin Bearer。老师访问 **403**；无 token **401**（即使 `AUTH_REQUIRED=0` 也不走 `admin_local`）。

**响应**
```json
{
  "ok": true,
  "count": 1,
  "items": [
    {
      "assignment_id": "HW-orphan",
      "teacher_id": "",
      "subject_id": "",
      "visibility_status": "orphan_draft",
      "needs_subject_review": true,
      "needs_roster_review": false,
      "scope": "class"
    }
  ]
}
```

### POST `/auth/admin/assignments/{assignment_id}/claim`
把孤儿作业认领到指定老师 + 学科。需 admin Bearer。

**JSON**
- `teacher_id`（必填；禁止默认 id `teacher` → 400 `default_teacher_id_forbidden`）
- `subject_id`（必填；必须已在 identity graph 中 → 否则 400 `subject_not_found`）
- `visibility_status`（可选，`draft` 或 `published`，默认 `draft`）

认领前该老师在该学科必须已有名册，否则 400 `roster_required`。已认领过的作业再 claim → 409 `not_orphan`。老师自己 claim → 403。

成功时写入 `meta.json` 的 `teacher_id` / `subject_id` / `pack_id` / `visibility_status`，并按名册填充 `expected_students`。

**请求**
```json
{
  "teacher_id": "t_zhang",
  "subject_id": "physics",
  "visibility_status": "published"
}
```

**响应**
```json
{
  "ok": true,
  "assignment_id": "HW-orphan",
  "teacher_id": "t_zhang",
  "subject_id": "physics",
  "visibility_status": "published",
  "expected_students": ["S001"]
}
```

---

## 学科 Pack（文件系统，不是 HTTP）

作业的学科 overlay / 可选 grader 从 pack 目录读取，路径：

```
packs/subjects/<id>/
  pack.yaml
  prompts/student_overlay.md
  prompts/teacher_overlay.md
```

- 默认根目录：仓库 `packs/subjects/`，可用环境变量 `SUBJECT_PACKS_DIR` 覆盖。
- `<id>` 必须匹配 `^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$`。装载器只打开该根下的 `packs/subjects/<id>/pack.yaml`，拒绝路径逃逸。
- 内置示例：`packs/subjects/generic/`、`packs/subjects/physics/`。
- **找不到或损坏的 subject 一律回退 `generic`，永不回退物理。** `generic` pack 缺失则失败（`SubjectPackError`），没有第二默认学科。
- 作业 `meta.pack_id` 优先于 `meta.subject_id`。认领孤儿作业时 `pack_id` 取该学科在 identity graph 里登记的值，缺省则等于 `subject_id`。
- `pack.yaml` 的 `skill_affiliates` 只给任教该 `subject_id` 的老师并入 `GET /skills` 与聊天自动路由。布置作业不依赖附属 skill，只依赖 `subject_id` 与 overlay。
- 聊天 overlay 与提交评分读同一套 pack；不要在 HTTP 里再发明 `/packs` 接口。

装载实现：`services/api/subject_pack_service.py`。

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
这些接口仍可用，但老师日常闭环是上传确认，不是生成试卷。

### POST `/assignment/generate`
**表单字段**
- `assignment_id`（必填）
- `subject_id`（必填；空值 → 400 `subject_id_required`）
- `kp`（必填，逗号分隔）
- `per_kp`（默认 5）
- `core_examples`（可选）
- `generate`（布尔，可选）
- `date` / `due_at` / `class_name` / `student_ids`（可选）

MCP **不**注册 `assignment.generate`。需要生成时走本接口或老师聊天。

### POST `/assignment/render`
**表单字段**
- `assignment_id`（必填）

---

## 作业提交
### POST `/student/submit`
学生端「提交作业」面板调用此接口。聊天附件不会自动记为提交。

**multipart/form-data**
- `student_id`（必填；受登录作用域约束）
- `files`（必填，支持多文件）
- `assignment_id`（必填）
- `auto_assignment`（若为 `true` → 400 `auto_assignment_disabled`）

成功时 HTTP 200。`submitted=false` 表示这次没有记为提交，不是传输失败。`reason=min_graded_total` 为有效评分不足；`reason=progress_unavailable` 为提交后未能读到 progress，不能当成评分不足。学生首页「已提交」只认 progress API，不看聊天完成。

---

## 文件上传
### POST `/upload`
**multipart/form-data**
- `files`（必填，支持多文件）
